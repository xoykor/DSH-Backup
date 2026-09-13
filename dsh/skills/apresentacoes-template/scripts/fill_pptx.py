#!/usr/bin/env python3
"""Fill contiguous {{field}} markers in PPTX text XML while preserving the package."""
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
TEXT = re.compile(r"(<a:t\b[^>]*>)(.*?)(</a:t>)", re.S)
INVALID_XML_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def values(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("values"), dict):
        data = data["values"]
    if not isinstance(data, dict):
        raise ValueError("values JSON must be an object")
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", required=True, type=Path)
    ap.add_argument("--values", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--allow-unresolved", action="store_true")
    args = ap.parse_args()
    try:
        if args.template.resolve() == args.output.resolve() or (args.output.exists() and os.path.samefile(args.template, args.output)):
            raise ValueError("output must be a different file from template")
        data = values(args.values)
        for key, value in data.items():
            if INVALID_XML_CONTROL.search(str(value)):
                raise ValueError(f"value for {key!r} contains an XML-invalid control character")
        original = zipfile.ZipFile(args.template)
        if original.testzip():
            raise ValueError("template ZIP is corrupt")
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    changed: dict[str, int] = {}
    missing: set[str] = set()
    text_bodies: list[str] = []
    members: dict[str, bytes] = {}
    for info in original.infolist():
        content = original.read(info.filename)
        if info.filename.startswith("ppt/") and info.filename.endswith(".xml"):
            xml = content.decode("utf-8")
            ElementTree.fromstring(xml)

            def text_node(match: re.Match[str]) -> str:
                def marker(found: re.Match[str]) -> str:
                    key = found.group(1)
                    if key not in data:
                        missing.add(key)
                        return found.group(0)
                    changed[key] = changed.get(key, 0) + 1
                    return html.escape(str(data[key]), quote=False)

                return match.group(1) + MARKER.sub(marker, match.group(2)) + match.group(3)

            content = TEXT.sub(text_node, xml).encode("utf-8")
            text_bodies.extend(match.group(2) for match in TEXT.finditer(content.decode("utf-8")))
            ElementTree.fromstring(content.decode("utf-8"))
        members[info.filename] = content
    unresolved = {match.group(1) for match in MARKER.finditer("".join(text_bodies))}
    if (missing or unresolved) and not args.allow_unresolved:
        original.close()
        print(json.dumps({"status": "error", "error": "unresolved_markers", "missing_values": sorted(missing), "unresolved": sorted(unresolved)}, ensure_ascii=False), file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w") as target:
        for info in original.infolist():
            target.writestr(info, members[info.filename])
    original.close()
    print(json.dumps({"status": "ok", "output": str(args.output), "replaced": changed, "missing": sorted(missing), "unresolved": sorted(unresolved)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
