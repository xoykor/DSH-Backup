#!/usr/bin/env python3
"""Fill contiguous {{field}} markers in a DOCX without changing the source."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

MARKER = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")
TEXT = re.compile(r"(<w:t\b[^>]*>)(.*?)(</w:t>)", re.S)
INVALID_XML_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def load_values(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and isinstance(value.get("values"), dict):
        value = value["values"]
    if not isinstance(value, dict):
        raise ValueError("values JSON must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--values", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-unresolved", action="store_true")
    args = parser.parse_args()
    if not args.template.is_file():
        print(json.dumps({"status": "error", "error": "template_not_found"}), file=sys.stderr)
        return 2
    try:
        template_resolved = args.template.resolve()
        output_resolved = args.output.resolve()
        if template_resolved == output_resolved or (args.output.exists() and os.path.samefile(args.template, args.output)):
            raise ValueError("output must be a different file from template")
        values = load_values(args.values)
        for key, value in values.items():
            if INVALID_XML_CONTROL.search(str(value)):
                raise ValueError(f"value for {key!r} contains an XML-invalid control character")
        source = zipfile.ZipFile(args.template)
        if source.testzip() is not None:
            raise ValueError("template ZIP is corrupt")
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    changed: dict[str, int] = {}
    missing: set[str] = set()
    text_bodies: list[str] = []
    members: dict[str, bytes] = {}
    for info in source.infolist():
        data = source.read(info.filename)
        if info.filename.startswith("word/") and info.filename.endswith(".xml"):
            text = data.decode("utf-8")
            ElementTree.fromstring(text)

            def replace_text(match: re.Match[str]) -> str:
                body = match.group(2)

                def replace_marker(marker: re.Match[str]) -> str:
                    key = marker.group(1)
                    if key not in values:
                        missing.add(key)
                        return marker.group(0)
                    changed[key] = changed.get(key, 0) + 1
                    return html.escape(str(values[key]), quote=False)

                return match.group(1) + MARKER.sub(replace_marker, body) + match.group(3)

            text = TEXT.sub(replace_text, text)
            text_bodies.extend(match.group(2) for match in TEXT.finditer(text))
            ElementTree.fromstring(text)
            data = text.encode("utf-8")
        members[info.filename] = data
    source.close()
    unresolved = {match.group(1) for match in MARKER.finditer("".join(text_bodies))}
    if (missing or unresolved) and not args.allow_unresolved:
        error = {"status": "error", "error": "unresolved_markers", "missing_values": sorted(missing), "unresolved": sorted(unresolved)}
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w") as target, zipfile.ZipFile(args.template) as original:
        for info in original.infolist():
            target.writestr(info, members[info.filename])
    print(json.dumps({"status": "ok", "output": str(args.output), "replaced": changed, "missing": sorted(missing), "unresolved": sorted(unresolved)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
