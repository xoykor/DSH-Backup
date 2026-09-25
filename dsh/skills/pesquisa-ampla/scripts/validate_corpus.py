#!/usr/bin/env python3
"""Validate a local corpus manifest; performs no network access."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

URL = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
STATUSES = {"candidate", "verified", "failed", "excluded", "duplicate"}
KINDS = {"primary", "secondary", "discovery"}
RELEVANCE = {"high", "medium", "low"}


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()

    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2

    errors: list[str] = []
    if not isinstance(data, dict):
        errors.append("root_must_be_object")
        data = {}
    if not nonempty(data.get("question")):
        errors.append("question_required")
    if not nonempty(data.get("consulted_at")):
        errors.append("consulted_at_required")

    records = data.get("records")
    if not isinstance(records, list):
        errors.append("records_must_be_array")
        records = []

    seen: dict[str, int] = {}
    domains: set[str] = set()
    verified = 0
    failures = 0
    duplicates = 0
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix}.must_be_object")
            continue
        url = record.get("url")
        if not isinstance(url, str) or not URL.match(url):
            errors.append(f"{prefix}.valid_http_url_required")
        canonical = record.get("canonical_url", url)
        if not isinstance(canonical, str) or not URL.match(canonical):
            errors.append(f"{prefix}.valid_canonical_url_required")
        elif canonical in seen and record.get("status") != "duplicate":
            errors.append(f"{prefix}.duplicate_canonical_url_without_duplicate_status")
        else:
            seen[canonical] = index

        domain = record.get("domain")
        if not nonempty(domain):
            errors.append(f"{prefix}.domain_required")
        else:
            domains.add(domain.lower())

        status = record.get("status")
        if status not in STATUSES:
            errors.append(f"{prefix}.status_invalid")
        elif status == "verified":
            verified += 1
            for field in ("title", "retrieved_at", "evidence"):
                if not nonempty(record.get(field)):
                    errors.append(f"{prefix}.{field}_required_for_verified")
            if record.get("kind") not in KINDS:
                errors.append(f"{prefix}.kind_invalid")
        elif status == "failed":
            failures += 1
            if not nonempty(record.get("failure")):
                errors.append(f"{prefix}.failure_required_for_failed")
        elif status == "duplicate":
            duplicates += 1
            if not nonempty(record.get("duplicate_of")):
                errors.append(f"{prefix}.duplicate_of_required")

        if "kind" in record and record.get("kind") not in KINDS:
            errors.append(f"{prefix}.kind_invalid")
        if "relevance" in record and record.get("relevance") not in RELEVANCE:
            errors.append(f"{prefix}.relevance_invalid")

    claims = data.get("claims", [])
    if not isinstance(claims, list):
        errors.append("claims_must_be_array")
        claims = []
    for index, claim in enumerate(claims):
        prefix = f"claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{prefix}.must_be_object")
            continue
        if not nonempty(claim.get("id")) or not nonempty(claim.get("text")):
            errors.append(f"{prefix}.id_and_text_required")
        if claim.get("kind") not in {"fact", "inference"}:
            errors.append(f"{prefix}.kind_must_be_fact_or_inference")
        if not isinstance(claim.get("record_urls"), list) or not claim["record_urls"]:
            errors.append(f"{prefix}.record_urls_required")

    result = {
        "status": "ok" if not errors else "invalid",
        "records": len(records),
        "unique_domains": len(domains),
        "verified": verified,
        "failed": failures,
        "duplicates": duplicates,
        "claims": len(claims),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
