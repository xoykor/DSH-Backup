#!/usr/bin/env python3
"""Validate DOCX ZIP/XML integrity and optionally render it with LibreOffice."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

MARKER = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")
TEXT = re.compile(r"<w:t\b[^>]*>(.*?)</w:t>", re.S)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--require", action="append", default=[])
    parser.add_argument("--render-dir", type=Path)
    args = parser.parse_args()
    if not args.input.is_file():
        print(json.dumps({"status": "error", "error": "input_not_found"}), file=sys.stderr)
        return 2
    unresolved: set[str] = set()
    try:
        with zipfile.ZipFile(args.input) as package:
            bad = package.testzip()
            if bad:
                raise ValueError(f"corrupt member: {bad}")
            xml_members = [name for name in package.namelist() if name.startswith("word/") and name.endswith(".xml")]
            all_text = []
            for name in xml_members:
                raw = package.read(name).decode("utf-8")
                ElementTree.fromstring(raw)
                all_text.extend(TEXT.findall(raw))
            joined = "\n".join(all_text)
            unresolved = {match.group(1) for match in MARKER.finditer(joined)}
            absent = [needle for needle in args.require if needle not in joined]
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, ElementTree.ParseError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if unresolved or absent:
        print(json.dumps({"status": "error", "unresolved": sorted(unresolved), "missing_required": absent}, ensure_ascii=False), file=sys.stderr)
        return 1

    rendered = None
    render_error = None
    if args.render_dir:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            render_error = "render_skipped: soffice/libreoffice unavailable"
        else:
            args.render_dir.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(args.render_dir), str(args.input)], capture_output=True, text=True, timeout=120)
            if proc.returncode:
                render_error = (proc.stderr or proc.stdout).strip()[-1000:]
            else:
                rendered = str(args.render_dir / (args.input.stem + ".pdf"))
    result = {"status": "ok", "input": str(args.input), "rendered_pdf": rendered}
    if render_error:
        result["render_note"] = render_error
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
