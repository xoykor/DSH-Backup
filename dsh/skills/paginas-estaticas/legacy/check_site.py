#!/usr/bin/env python3
"""Check local HTML/CSS references without opening a browser or doing network I/O."""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class References(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
        self.viewport = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for key in ("href", "src"):
            if values.get(key):
                self.refs.append(values[key] or "")
        if tag.lower() == "meta" and (values.get("name") or "").lower() == "viewport":
            self.viewport = True


def local_target(root: Path, current: Path, ref: str) -> tuple[Path | None, str | None]:
    parsed = urlsplit(ref)
    if parsed.scheme or parsed.netloc or ref.startswith("//") or ref.startswith("#"):
        return None, None
    raw = parsed.path
    if not raw:
        return None, None
    candidate = (current.parent / raw).resolve() if not raw.startswith("/") else (root / raw.lstrip("/")).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, "path_outside_root"
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--entry", default="index.html")
    args = ap.parse_args()
    root = args.root.resolve()
    entry = (root / args.entry).resolve()
    errors: list[dict[str, str]] = []
    warnings: list[str] = []
    checked: list[str] = []
    if not root.is_dir() or not entry.is_file():
        print(json.dumps({"status": "error", "error": "root_or_entry_not_found"}), file=sys.stderr)
        return 2
    html_parser = References()
    try:
        html_parser.feed(entry.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    checked.append(str(entry.relative_to(root)))
    if not html_parser.viewport:
        warnings.append("missing_meta_viewport")
    refs = [(entry, ref) for ref in html_parser.refs]
    for css in root.rglob("*.css"):
        try:
            body = css.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            errors.append({"file": str(css.relative_to(root)), "reference": "<css unreadable>", "error": "unreadable"})
            continue
        refs.extend((css, ref) for ref in re.findall(r"url\(\s*['\"]?([^'\")]+)", body))
    for current, ref in refs:
        target, error = local_target(root, current, ref)
        if error:
            errors.append({"file": str(current.relative_to(root)), "reference": ref, "error": error})
        elif target is not None and not target.is_file():
            errors.append({"file": str(current.relative_to(root)), "reference": ref, "error": "missing_local_target"})
        elif target is not None:
            checked.append(str(target.relative_to(root)))
    result = {"status": "ok" if not errors else "invalid", "root": str(root), "entry": args.entry, "checked": sorted(set(checked)), "references": len(refs), "errors": errors, "warnings": warnings}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
