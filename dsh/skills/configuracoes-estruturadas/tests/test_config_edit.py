import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/config_edit.py"


class ConfigEditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def invoke(self, content, suffix, operations, expected_code=0):
        source = self.root / ("source" + suffix)
        target = self.root / ("result" + suffix)
        source.write_text(content, encoding="utf-8")
        spec = self.root / "spec.json"
        spec.write_text(json.dumps({"operations": operations}), encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--output", str(target), "--spec", str(spec)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, expected_code, result.stderr)
        self.assertEqual(source.read_text(), content)
        return target, json.loads(result.stdout or result.stderr)

    def change(self, path=None, expected=8080, value=9000):
        return {"op": "set", "path": path or ["server", "port"], "expected": expected, "expected_type": "integer", "value": value, "value_type": "integer"}

    def test_json_nested_arrays_delete_create_and_redaction(self):
        content = '{"server":{"port":8080,"password":"SECRET-DO-NOT-PRINT"},"a":[1,2]}'
        ops = [self.change(), {"op": "delete", "path": ["a", 0], "expected": 1, "expected_type": "integer"}, {"op": "set", "path": ["new"], "expected_absent": True, "value": True, "value_type": "boolean"}]
        target, result = self.invoke(content, ".json", ops)
        actual = json.loads(target.read_text())
        self.assertEqual(actual["a"], [2]); self.assertEqual(actual["server"]["port"], 9000)
        self.assertTrue(actual["new"]); self.assertTrue(result["roundtrip_validated"])
        self.assertNotIn("SECRET-DO-NOT-PRINT", json.dumps(result))
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML unavailable")
    def test_yaml_with_unicode(self):
        target, _ = self.invoke("server:\n  port: 8080\n  cidade: Fortaleza\n", ".yaml", [self.change()])
        import yaml
        self.assertEqual(yaml.safe_load(target.read_text())["server"], {"port": 9000, "cidade": "Fortaleza"})

    def test_toml_roundtrip_dates_arrays_inline_tables(self):
        content = '# comments not preserved\nwhen = 2026-09-13T12:00:00Z\nempty = {}\n[[people]]\nname = "á"\n[server]\nport = 8080\n'
        target, _ = self.invoke(content, ".toml", [self.change()])
        original = tomllib.loads(content); original["server"]["port"] = 9000
        self.assertEqual(tomllib.loads(target.read_text()), original)

    def test_stale_expected_is_rejected_without_output(self):
        target, result = self.invoke('{"server":{"port":80}}', ".json", [self.change()], 2)
        self.assertFalse(target.exists()); self.assertIn("pré-condição", result["error"])

    def test_boolean_does_not_match_integer(self):
        target, _ = self.invoke('{"server":{"port":true}}', ".json", [self.change(expected=1)], 2)
        self.assertFalse(target.exists())

    def test_invalid_source_never_echoes_secret(self):
        target, result = self.invoke('{"secret":"CONFIDENTIAL", INVALID}', ".json", [self.change()], 2)
        self.assertNotIn("CONFIDENTIAL", json.dumps(result)); self.assertFalse(target.exists())

    def test_duplicate_json_keys_are_rejected(self):
        target, _ = self.invoke('{"server":{"port":80,"port":8080}}', ".json", [self.change()], 2)
        self.assertFalse(target.exists())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML unavailable")
    def test_duplicate_yaml_keys_are_rejected(self):
        target, _ = self.invoke('server:\n  port: 80\n  port: 8080\n', ".yaml", [self.change()], 2)
        self.assertFalse(target.exists())

    def test_toml_null_is_rejected(self):
        op = self.change(); op.update(value=None, value_type="null")
        target, _ = self.invoke('[server]\nport=8080\n', ".toml", [op], 2)
        self.assertFalse(target.exists())

    def test_existing_output_is_preserved(self):
        (self.root / "result.json").write_text("keep")
        target, _ = self.invoke('{"server":{"port":8080}}', ".json", [self.change()], 2)
        self.assertEqual(target.read_text(), "keep")


if __name__ == "__main__": unittest.main()
