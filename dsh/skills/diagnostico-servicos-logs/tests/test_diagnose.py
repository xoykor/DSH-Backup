#!/usr/bin/env python3
"""Deterministic tests for bounded diagnostic collection."""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "diagnose.py"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b'{"status":"ok","access_token":"do-not-leak"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        pass


class DiagnoseTests(unittest.TestCase):
    def test_log_groups_redacts_and_reports_unavailable_docker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "app.log"
            log.write_text(
                "2026-09-13T12:00:00Z timeout contacting upstream token=secret-token\n"
                "2026-09-13T12:01:00Z timeout contacting upstream token=secret-token\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                ["python3", str(SCRIPT), "--log-file", str(log), "--container", "app", "--docker-bin", str(Path(directory) / "missing-docker"), "--timeout", "5"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 1, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertEqual(report["status"], "incomplete")
            self.assertTrue(any(t["kind"] == "log_file" for t in report["targets"]))
            target = next(t for t in report["targets"] if t["kind"] == "log_file")
            signature = target["observations"][0]["log_signatures"][0]
            self.assertEqual(signature["count"], 2)
            self.assertEqual(signature["first_line"], 1)
            self.assertEqual(signature["last_line"], 2)
            self.assertNotIn("secret-token", proc.stdout)

    def test_structured_log_secret_arrays_and_fifo(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "secrets.log"
            log.write_text('{"rows":[{"token":["secret-one","secret-two"]}]}\n')
            proc = subprocess.run(["python3", str(SCRIPT), "--log-file", str(log)], capture_output=True, text=True, timeout=5)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertNotIn("secret-one", proc.stdout)
            self.assertNotIn("secret-two", proc.stdout)
            fifo = Path(directory) / "blocked-pipe"
            os.mkfifo(fifo)
            proc = subprocess.run(["python3", str(SCRIPT), "--log-file", str(fifo)], capture_output=True, text=True, timeout=5)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("not_regular_file", proc.stdout)

    def test_bracket_timestamp_logs_remain_useful(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "bracket.log"
            log.write_text('[2026-09-13 18:00:00] Connection refused token=hidden-value\n[ERROR] Worker exited\n')
            proc = subprocess.run(["python3", str(SCRIPT), "--log-file", str(log)], capture_output=True, text=True, timeout=5)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn('Connection refused', proc.stdout)
            self.assertIn('Worker exited', proc.stdout)
            self.assertNotIn('hidden-value', proc.stdout)

    def test_url_status_and_body_are_redacted(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            proc = subprocess.run(
                ["python3", str(SCRIPT), "--url", f"http://127.0.0.1:{server.server_port}/health?token=secret-token", "--timeout", "5"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            observation = report["targets"][0]["observations"][0]
            self.assertEqual(observation["http_status"], 200)
            self.assertNotIn("do-not-leak", proc.stdout)
            self.assertNotIn("secret-token", proc.stdout)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
