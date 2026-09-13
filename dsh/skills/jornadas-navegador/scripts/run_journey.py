#!/usr/bin/env python3
"""Bounded declarative browser journeys through the existing DSH HTTP bridge."""
from __future__ import annotations

import argparse
import base64
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class JourneyError(Exception):
    pass


class AssertionFailed(JourneyError):
    pass


ASSERTIONS = {"assert-text", "assert-value", "assert-visible", "assert-title", "assert-url"}
ACTIONS = ASSERTIONS | {"goto", "fill", "click"}


def bounded_number(value, lo, hi, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f"{field} must be between {lo} and {hi}")
    return float(value)


def validate(spec):
    if not isinstance(spec, dict) or set(spec) - {"steps", "timeout_seconds", "step_timeout_seconds", "allow_interactions"}:
        raise ValueError("invalid plan fields")
    bounded_number(spec.get("timeout_seconds", 120), 1, 600, "timeout_seconds")
    bounded_number(spec.get("step_timeout_seconds", 10), .2, 60, "step_timeout_seconds")
    if "allow_interactions" in spec and not isinstance(spec["allow_interactions"], bool):
        raise ValueError("allow_interactions must be boolean")
    steps = spec.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 40:
        raise ValueError("steps must contain 1..40 entries")
    if not any(isinstance(s, dict) and s.get("action") in ASSERTIONS for s in steps):
        raise ValueError("at least one assertion is required")
    for step in steps:
        if not isinstance(step, dict) or step.get("action") not in ACTIONS:
            raise ValueError("unknown action")
        action = step["action"]
        fields = {"action"}
        if action == "goto":
            fields.add("url")
            url = step.get("url")
            if not isinstance(url, str) or not (urllib.parse.urlsplit(url).scheme in {"http", "https"} or url.startswith("data:text/html")):
                raise ValueError("goto requires an HTTP(S) or data:text/html URL")
        if action in {"fill", "click", "assert-text", "assert-value", "assert-visible"}:
            fields.add("selector")
            if not isinstance(step.get("selector"), str) or not step["selector"] or len(step["selector"]) > 2048:
                raise ValueError("a nonempty CSS selector is required")
        if action in {"fill", "click"} and spec.get("allow_interactions") is not True:
            raise ValueError("interactions require allow_interactions: true")
        if action == "fill":
            fields.add("value")
            if not isinstance(step.get("value"), str):
                raise ValueError("fill requires a string value")
        if action in ASSERTIONS - {"assert-visible"}:
            fields.update({"equals", "contains"})
            if ("equals" in step) == ("contains" in step) or not isinstance(step.get("equals", step.get("contains")), str):
                raise ValueError("assertion requires exactly one string equals or contains")
        if action == "assert-visible":
            fields.add("visible")
            if not isinstance(step.get("visible", True), bool):
                raise ValueError("visible must be boolean")
        if set(step) - fields:
            raise ValueError("unknown step fields")
    return spec


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Bridge:
    def __init__(self, endpoint, deadline):
        parsed = urllib.parse.urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("invalid bridge endpoint")
        self.endpoint = endpoint.rstrip("/")
        self.deadline = deadline
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def remaining(self):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise JourneyError("total timeout exceeded")
        return left

    def call(self, operation, action=None, timeout=10):
        timeout = max(.001, min(timeout, self.remaining()))
        request = urllib.request.Request(self.endpoint + "/" + operation,
            data=None if operation == "health" else json.dumps({"action": action or {}}).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(12 * 1024 * 1024 + 1)
            self.remaining()
            if len(raw) > 12 * 1024 * 1024:
                raise JourneyError("bridge response too large")
            result = json.loads(raw)
            if not isinstance(result, dict) or "error" in result:
                raise JourneyError("bridge returned an error")
            return result
        except urllib.error.HTTPError as exc:
            raise JourneyError(f"bridge HTTP {exc.code}") from exc
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise JourneyError("bridge transport or JSON error") from exc

    def require_own_page(self, page_id):
        state = self.call("health", timeout=3)
        if state.get("ready") is not True or not isinstance(state.get("pages"), list):
            raise JourneyError("bridge not ready")
        if [p.get("id") for p in state["pages"]] != [page_id]:
            raise JourneyError("bridge tab ownership changed; exclusive use required")


def expression_for(step):
    # Only generated reads; data literals are JSON-escaped, never executable plan text.
    data = json.dumps(step, ensure_ascii=True)
    return """(() => { const s = %s; let v; const a=s.action;
      if (a === 'assert-url') v=location.href;
      else if (a === 'assert-title') v=document.title;
      else { const nodes=document.querySelectorAll(s.selector);
        if (a === 'assert-visible' && nodes.length===0) return {matched:s.visible===false};
        if (nodes.length!==1) return {matched:false};
        const e=nodes[0];
        if (a==='assert-visible') { const r=e.getBoundingClientRect(), c=getComputedStyle(e);
          v=r.width>0 && r.height>0 && c.visibility!=='hidden' && c.visibility!=='collapse' && c.display!=='none';
          return {matched:v === (s.visible!==false)}; }
        v=a==='assert-value' ? e.value : e.textContent;
      }
      return {matched:typeof v==='string' && (Object.hasOwn(s,'equals') ? v===s.equals : v.includes(s.contains))};
    })()""" % data


def run(spec, output_dir, endpoint):
    validate(spec)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    timeout = spec.get("timeout_seconds", 120)
    bridge = Bridge(endpoint, start + timeout)
    report = {"status": "failed_infrastructure", "steps": [], "assertions": 0}
    page_id = None
    try:
        state = bridge.call("health", timeout=5)
        if state.get("ready") is not True or not isinstance(state.get("pages"), list):
            raise JourneyError("bridge not ready")
        if state["pages"]:
            raise JourneyError("bridge has existing tabs; use an exclusive empty bridge")
        page_id = bridge.call("new", timeout=5).get("id")
        if type(page_id) is not int or page_id < 1:
            page_id = None
            raise JourneyError("bridge did not return a valid page id")
        for i, step in enumerate(spec["steps"], 1):
            entry = {"step": i, "action": step["action"], "status": "running"}
            report["steps"].append(entry)
            step_start = time.monotonic()
            bridge.require_own_page(page_id)
            step_timeout = min(spec.get("step_timeout_seconds", 10), bridge.remaining())
            deadline = time.monotonic() + step_timeout
            if step["action"] in ASSERTIONS:
                while True:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise AssertionFailed("assertion condition not met before timeout")
                    bridge.require_own_page(page_id)
                    result = bridge.call("evaluate", {"id": page_id, "expression": expression_for(step)}, timeout=left).get("result")
                    if not isinstance(result, dict) or type(result.get("matched")) is not bool:
                        raise JourneyError("bridge did not evaluate the assertion; check CSS selector")
                    if result["matched"]:
                        report["assertions"] += 1
                        break
                    time.sleep(min(.2, max(0, deadline - time.monotonic())))
            else:
                action = {k: v for k, v in step.items() if k != "action"}
                action.update({"id": page_id, "timeout": max(1, int((step_timeout - .05) * 1000))})
                if step["action"] == "goto":
                    action["waitUntil"] = "domcontentloaded"
                bridge.call(step["action"], action, timeout=step_timeout)
            entry.update(status="passed", duration_seconds=round(time.monotonic() - step_start, 3))
        report["status"] = "passed"
    except (JourneyError, OSError) as exc:
        report["status"] = "failed_assertion" if isinstance(exc, AssertionFailed) else "failed_infrastructure"
        report["error"] = str(exc)
        if report["steps"] and report["steps"][-1]["status"] == "running":
            report["steps"][-1]["status"] = report["status"]
        if page_id is not None:
            try:
                bridge.require_own_page(page_id)
                shot = bridge.call("screenshot", {"id": page_id, "fullPage": False}, timeout=3)
                png = base64.b64decode(shot.get("png", ""), validate=True)
                if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("invalid PNG")
                with (output_dir / "failure.png").open("xb") as stream:
                    stream.write(png)
                report["screenshot"] = str((output_dir / "failure.png").resolve())
            except (JourneyError, OSError, ValueError):
                report["screenshot_status"] = "unavailable"
    finally:
        if page_id is not None:
            try:
                bridge.call("close-page", {"id": page_id}, timeout=3)
                report["cleanup"] = "closed_own_page"
            except JourneyError:
                report["cleanup"] = "pending"
                if report["status"] == "passed":
                    report["status"] = "failed_infrastructure"
        report["duration_seconds"] = round(time.monotonic() - start, 3)
        with (output_dir / "report.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8731")
    args = parser.parse_args()
    try:
        if args.spec.stat().st_size > 1024 * 1024:
            raise ValueError("plan too large")
        report = run(json.loads(args.spec.read_text()), args.output_dir, args.endpoint)
        print(json.dumps(report, ensure_ascii=False))
        return {"passed": 0, "failed_assertion": 1}.get(report["status"], 2)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
