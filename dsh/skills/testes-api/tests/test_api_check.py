#!/usr/bin/env python3
"""Deterministic HTTP API runner tests using a local synthetic server."""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "api_check.py"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/slow"):
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            try:
                for _ in range(20):
                    self.wfile.write(b"x"); self.wfile.flush(); time.sleep(.1)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", "/health")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path.startswith("/nested"):
            body = b'{"rows":[{"token":["hidden-one","hidden-two"],"status":7}],"password":123456}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        elif self.path.startswith("/health"):
            body = b'{"status":"ok","access_token":"do-not-leak"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        elif self.path.startswith("/missing"):
            body = b'{"error":"not found","token":"do-not-leak"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
        elif self.path.startswith("/bad-json"):
            body = b'{invalid json'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            body = b"unknown"
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        pass


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def run_spec(self, spec: dict[str, object], *extra: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spec.json"
            path.write_text(json.dumps(spec), encoding="utf-8")
            proc = subprocess.run(["python3", str(SCRIPT), "--spec", str(path), *extra], capture_output=True, text=True, check=False)
            return proc, json.loads(proc.stdout)

    def test_status_headers_fields_and_http_error_are_testable(self) -> None:
        proc, report = self.run_spec({"requests": [
            {"name": "health", "url": self.base + "/health", "expect": {"status": {"equals": 200}, "headers": {"content-type": {"contains": "application/json"}}, "body": {"fields": {"status": {"equals": "ok"}}}}},
            {"name": "missing", "url": self.base + "/missing", "expect": {"status": {"equals": 404}, "body": {"contains": "not found"}}},
        ]})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["requests"][1]["transport"], "http_error_response")
        self.assertNotIn("do-not-leak", proc.stdout)

    def test_invalid_json_and_mutation_gate(self) -> None:
        proc, report = self.run_spec({"requests": [{"url": self.base + "/bad-json", "expect": {"body": {"fields": {"status": {"equals": "ok"}}}}}]})
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["requests"][0]["status"], "failed_assertion")
        self.assertIn("invalid_json", report["requests"][0]["json_error"])
        proc, report = self.run_spec({"requests": [{"method": "POST", "url": self.base + "/mutate"}]})
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(report["status"], "blocked_mutation")

    def test_mutation_requires_two_explicit_opt_ins(self) -> None:
        proc, report = self.run_spec({"allow_mutations": True, "requests": [{"method": "POST", "url": self.base + "/mutate", "expect": {"status": {"equals": 204}}}]}, "--allow-mutations")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report["status"], "passed")

    def test_nested_redaction_does_not_change_asserted_values(self):
        proc, report = self.run_spec({"requests": [{"url": self.base + "/nested?access_token=hidden-url", "expect": {"body": {"fields": {"rows.0.token.0": {"equals": "hidden-one"}, "password": 123456}}}}]})
        self.assertEqual(proc.returncode, 0, proc.stdout)
        for secret in ("hidden-one", "hidden-two", "hidden-url", "123456"):
            self.assertNotIn(secret, proc.stdout)

    def test_total_deadline_includes_slow_body(self):
        start = time.monotonic()
        proc, report = self.run_spec({"requests": [{"url": self.base + "/slow", "timeout": 5}]}, "--total-timeout", "0.3")
        self.assertLess(time.monotonic() - start, 1.5)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["requests"][0]["status"], "failed_transport")

    def test_redirect_is_tested_without_following(self):
        proc, report = self.run_spec({"requests": [{"url": self.base + "/redirect", "expect": {"status": 302}}]})
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(report["requests"][0]["status_code"], 302)

    def test_numeric_contains_is_not_false_success(self):
        proc, report = self.run_spec({"requests": [{"url": self.base + "/nested", "expect": {"body": {"fields": {"rows.0.status": {"contains": 7}}}}}]})
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(report["requests"][0]["status"], "failed_assertion")


if __name__ == "__main__":
    unittest.main()
