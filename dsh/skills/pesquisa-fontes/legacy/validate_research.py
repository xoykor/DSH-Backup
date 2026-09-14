#!/usr/bin/env python3
"""Validate a local claim-to-source evidence record; never performs network I/O."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

URL = re.compile(r"^https?://[^\s]+$", re.I)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, type=Path)
    args = ap.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    errors: list[str] = []
    claims = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get("question"), str) or not data["question"].strip():
        errors.append("question_required")
    if not isinstance(claims, list) or not claims:
        errors.append("claims_required")
        claims = []
    source_count = 0
    for index, claim in enumerate(claims):
        prefix = f"claims[{index}]"
        if not isinstance(claim, dict) or not isinstance(claim.get("text"), str) or not claim["text"].strip():
            errors.append(f"{prefix}.text_required")
            continue
        if claim.get("kind") not in {"fact", "inference"}:
            errors.append(f"{prefix}.kind_must_be_fact_or_inference")
        sources = claim.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{prefix}.source_required")
            continue
        for source_index, source in enumerate(sources):
            source_count += 1
            sp = f"{prefix}.sources[{source_index}]"
            if not isinstance(source, dict) or not isinstance(source.get("url"), str) or not URL.match(source["url"]):
                errors.append(f"{sp}.valid_http_url_required")
            if not isinstance(source, dict) or not isinstance(source.get("title"), str) or not source["title"].strip():
                errors.append(f"{sp}.title_required")
            if not isinstance(source, dict) or not isinstance(source.get("evidence"), str) or len(source["evidence"].strip()) < 20:
                errors.append(f"{sp}.evidence_text_required")
    result = {"status": "ok" if not errors else "invalid", "question": data.get("question") if isinstance(data, dict) else None, "claims": len(claims), "sources": source_count, "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
