import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/sqlite_read.py"


class SQLiteReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.db = self.root / "db?#.sqlite"
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE people (id INTEGER, city TEXT, payload BLOB)")
            conn.executemany("INSERT INTO people VALUES (?,?,?)", [(1, "Fortaleza", b"abc"), (2, "Recife", b"def"), (3, "Fortaleza", b"ghi")])

    def call(self, sql=None, params=None, code=0, extra=None, **limits):
        cmd = [sys.executable, str(SCRIPT), "--database", str(self.db)]
        if sql is not None:
            spec = self.root / "query.json"
            spec.write_text(json.dumps({"sql": sql, "params": [] if params is None else params, **limits}))
            cmd += ["--mode", "query", "--spec", str(spec)]
        cmd += extra or []
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, code, result.stderr)
        return json.loads(result.stdout or result.stderr)

    def test_schema_and_parameterized_query_blob(self):
        schema = self.call()
        self.assertEqual(schema["rows"][0][1], "people")
        result = self.call("SELECT id, payload FROM people WHERE city=:city ORDER BY id", {"city": "Fortaleza"})
        self.assertEqual(result["rows"], [[1, {"type": "blob", "base64": "YWJj"}], [3, {"type": "blob", "base64": "Z2hp"}]])
        self.assertTrue(result["read_only"])

    def test_parameter_injection_is_a_value(self):
        result = self.call("SELECT id FROM people WHERE city=?", ["Fortaleza' OR 1=1 --"])
        self.assertEqual(result["returned_rows"], 0)

    def test_truncation_and_duplicate_column_names(self):
        result = self.call("SELECT id AS x, city AS x FROM people ORDER BY id", max_rows=2)
        self.assertTrue(result["truncated"]); self.assertEqual(result["columns"], ["x", "x"])
        self.assertEqual(len(result["rows"]), 2)

    def test_write_attach_extension_and_mutant_pragma_blocked(self):
        statements = ["UPDATE people SET city='changed'", "DELETE FROM people", "CREATE TABLE nope (id)",
                      "ATTACH DATABASE ':memory:' AS evil", "PRAGMA user_version=3", "PRAGMA writable_schema=ON",
                      "SELECT load_extension('/tmp/not-real')", "VACUUM", "SELECT 1; SELECT 2"]
        for sql in statements:
            with self.subTest(sql=sql): self.call(sql, code=2)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM people").fetchone()[0], 3)
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_readonly_pragma_is_allowed(self):
        result = self.call("PRAGMA table_info(people)")
        self.assertEqual(result["returned_rows"], 3)

    def test_timeout_stops_expensive_recursive_query(self):
        start = time.monotonic()
        self.call("WITH RECURSIVE cnt(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM cnt WHERE x<100000000) SELECT sum(x) FROM cnt", timeout_seconds=0.1, code=2)
        self.assertLess(time.monotonic() - start, 3)

    def test_large_cell_and_limits_are_rejected(self):
        self.call("SELECT zeroblob(70000)", code=2)
        self.call("SELECT 1", max_rows=0, code=2)

    def test_export_and_existing_output_preserved(self):
        target = self.root / "out.csv"
        result = self.call("SELECT id,city FROM people ORDER BY id", extra=["--output", str(target)])
        self.assertNotIn("rows", result); self.assertIn("Fortaleza", target.read_text())
        before = target.read_bytes()
        self.call("SELECT 1", extra=["--output", str(target)], code=2)
        self.assertEqual(target.read_bytes(), before)

    def test_reads_committed_wal_without_main_file_hash(self):
        writer = sqlite3.connect(self.db); self.addCleanup(writer.close)
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("INSERT INTO people VALUES (4, 'Natal', NULL)"); writer.commit()
        self.assertTrue(Path(str(self.db) + "-wal").exists())
        result = self.call("SELECT count(*) FROM people")
        self.assertEqual(result["rows"], [[4]])
        self.assertNotIn("sha256", result)


if __name__ == "__main__": unittest.main()
