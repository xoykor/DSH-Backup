import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "run_journey.py"
spec = importlib.util.spec_from_file_location("run_journey", MODULE)
journey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journey)


class FakeBridge:
    existing = False
    matched = True
    calls = []

    def __init__(self, endpoint, deadline):
        self.page = self.existing

    def remaining(self):
        return 5

    def require_own_page(self, page_id):
        if not self.page:
            raise journey.JourneyError("page missing")

    def call(self, operation, action=None, timeout=10):
        self.calls.append(operation)
        if operation == "health":
            return {"ready": True, "pages": [{"id": 1}] if self.page else []}
        if operation == "new":
            self.page = True
            return {"id": 1}
        if operation == "evaluate":
            return {"result": {"matched": self.matched}}
        if operation == "close-page":
            self.page = False
        if operation == "screenshot":
            raise journey.JourneyError("no screenshot in fake")
        return {"ok": True}


class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        FakeBridge.calls = []
        FakeBridge.existing = False
        FakeBridge.matched = True

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self):
        return {"step_timeout_seconds": .2, "steps": [{"action": "goto", "url": "data:text/html,<p>OK</p>"},
                         {"action": "assert-text", "selector": "p", "equals": "OK"}]}

    def test_interactions_require_explicit_scope_and_assertions(self):
        for spec in [{"steps": [{"action": "click", "selector": "button"}]},
                     {"steps": [{"action": "click", "selector": "button"}, {"action": "assert-url", "contains": "ok"}]}]:
            with self.assertRaises(ValueError):
                journey.validate(spec)

    def test_existing_tabs_not_closed_or_changed(self):
        FakeBridge.existing = True
        with patch.object(journey, "Bridge", FakeBridge):
            result = journey.run(self.plan(), self.root / "out", "http://localhost:8731")
        self.assertEqual(result["status"], "failed_infrastructure")
        self.assertEqual(FakeBridge.calls, ["health"])

    def test_pass_and_close_own_page(self):
        with patch.object(journey, "Bridge", FakeBridge):
            result = journey.run(self.plan(), self.root / "out", "http://localhost:8731")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["assertions"], 1)
        self.assertEqual(FakeBridge.calls[-1], "close-page")
        self.assertEqual(json.loads((self.root / "out/report.json").read_text())["status"], "passed")

    def test_failed_assertion_never_replays_click(self):
        FakeBridge.matched = False
        plan = self.plan()
        plan["allow_interactions"] = True
        plan["steps"].insert(1, {"action": "click", "selector": "button"})
        with patch.object(journey, "Bridge", FakeBridge):
            result = journey.run(plan, self.root / "out", "http://localhost:8731")
        self.assertEqual(result["status"], "failed_assertion")
        self.assertEqual(FakeBridge.calls.count("click"), 1)
        self.assertEqual(FakeBridge.calls[-1], "close-page")

    def test_output_collision(self):
        with self.assertRaises(FileExistsError):
            journey.run(self.plan(), self.root, "http://localhost:8731")

    def test_extra_javascript_rejected(self):
        plan = self.plan()
        plan["steps"][1]["expression"] = "alert(1)"
        with self.assertRaises(ValueError):
            journey.validate(plan)


if __name__ == "__main__":
    unittest.main()
