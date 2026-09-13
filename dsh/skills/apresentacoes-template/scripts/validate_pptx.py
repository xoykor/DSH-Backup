#!/usr/bin/env python3
"""Validate PPTX ZIP/XML integrity and optionally create a PDF render."""
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
TEXT = re.compile(r"<a:t\b[^>]*>(.*?)</a:t>", re.S)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--require", action="append", default=[])
    ap.add_argument("--render-dir", type=Path)
    args = ap.parse_args()
    unresolved: set[str] = set()
    try:
        with zipfile.ZipFile(args.input) as package:
            bad = package.testzip()
            if bad:
                raise ValueError(f"corrupt member: {bad}")
            text_parts: list[str] = []
            for name in package.namelist():
                if not (name.startswith("ppt/") and name.endswith(".xml")):
                    continue
                raw = package.read(name).decode("utf-8")
                ElementTree.fromstring(raw)
                text_parts.extend(TEXT.findall(raw))
            joined = "\n".join(text_parts)
            unresolved = {match.group(1) for match in MARKER.finditer(joined)}
            absent = [needle for needle in args.require if needle not in joined]
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, ElementTree.ParseError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if unresolved or absent:
        print(json.dumps({"status": "error", "unresolved": sorted(unresolved), "missing_required": absent}, ensure_ascii=False), file=sys.stderr)
        return 1
    rendered = None
    note = None
    if args.render_dir:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            note = "render_skipped: soffice/libreoffice unavailable"
        else:
            args.render_dir.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(args.render_dir), str(args.input)], capture_output=True, text=True, timeout=120)
            if proc.returncode:
                note = (proc.stderr or proc.stdout).strip()[-1000:]
            else:
                rendered = str(args.render_dir / (args.input.stem + ".pdf"))
    result = {"status": "ok", "input": str(args.input), "rendered_pdf": rendered}
    if note:
        result["render_note"] = note
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
