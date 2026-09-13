import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "table_transform.py"


class TableTransformTest(unittest.TestCase):
    def test_explicit_operations_preserve_unicode_ids_empty_and_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "entrada.csv"
            source.write_text("id,status,note\n001,active,  café\t au lait  \n001,active,duplicate\n002,inactive,\n003,active,other\n", encoding="utf-8")
            original = source.read_bytes()
            operations = root / "ops.json"
            operations.write_text(json.dumps({"operations": [
                {"op": "clean", "trim_strings": True, "collapse_whitespace": True},
                {"op": "filter", "where": {"status": {"eq": "active"}}},
                {"op": "dedupe", "keys": ["id"], "keep": "first"},
            ]}), encoding="utf-8")
            output = root / "resultado.tsv"
            completed = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output), "--operations", str(operations)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual((report["rows_before"], report["rows_after"], report["removed_rows"]), (4, 2, 2))
            self.assertEqual(source.read_bytes(), original)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            self.assertEqual([row["id"] for row in rows], ["001", "003"])
            self.assertEqual(rows[0]["note"], "café au lait")

    def test_nested_dedupe_and_invalid_not_empty_are_structured_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "entrada.json"
            source.write_text(json.dumps([{"id": {"a": 1}, "ok": "x"}, {"id": {"a": 1}, "ok": ""}], ensure_ascii=False), encoding="utf-8")
            ops = root / "ops.json"
            ops.write_text(json.dumps({"operations": [{"op": "dedupe", "keys": ["id"]}]}), encoding="utf-8")
            output = root / "out.json"
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output), "--operations", str(ops)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(output.read_text(encoding="utf-8"))), 1)
            ops.write_text(json.dumps({"operations": [{"op": "filter", "where": {"ok": {"not_empty": "yes"}}}]}), encoding="utf-8")
            bad = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--output", str(root / "bad.json"), "--operations", str(ops)], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("not_empty", bad.stderr)

    def test_hardlink_output_is_rejected_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "entrada.csv"
            source.write_text("id\n001\n", encoding="utf-8")
            linked = root / "linked.csv"
            os.link(source, linked)
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--output", str(linked)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("overwrite", result.stderr)
            self.assertEqual(source.read_text(encoding="utf-8"), "id\n001\n")


if __name__ == "__main__":
    unittest.main()
