#!/usr/bin/env python3
"""Extract, inspect, split, merge, reorder, and render PDFs deterministically."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class PdfError(ValueError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_pypdf() -> tuple[Any, Any]:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise PdfError("pypdf is required; use the DSH Python runtime with its bundled dependencies") from exc
    return PdfReader, PdfWriter


def ensure_distinct(input_path: Path, output_path: Path) -> None:
    if input_path.resolve() == output_path.resolve():
        raise PdfError("refusing to overwrite the input; choose a separate output")
    if output_path.exists() and os.path.samefile(input_path, output_path):
        raise PdfError("refusing an output hardlink to the input")


def reader_for(path: Path) -> Any:
    PdfReader, _ = load_pypdf()
    try:
        return PdfReader(str(path))
    except Exception as exc:
        raise PdfError(f"cannot read PDF {path}: {exc}") from exc


def page_text(page: Any) -> str:
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


def inspect_pdf(path: Path) -> dict[str, Any]:
    reader = reader_for(path)
    texts = [page_text(page) for page in reader.pages]
    char_count = sum(len(text) for text in texts)
    return {
        "pages": len(reader.pages),
        "textual_pages": sum(bool(text.strip()) for text in texts),
        "empty_pages": sum(not text.strip() for text in texts),
        "text_characters": char_count,
        "classification": "textual" if char_count else "likely-scanned-or-empty",
    }


def write_reader(reader: Any, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        writer = load_pypdf()[1]()
        writer.clone_document_from_reader(reader)
        writer.write(stream)


def action_inspect(args: argparse.Namespace) -> dict[str, Any]:
    result = inspect_pdf(args.input)
    result.update({"status": "ok", "input": str(args.input.resolve()), "input_sha256": sha256(args.input)})
    return result


def action_extract(args: argparse.Namespace) -> dict[str, Any]:
    ensure_distinct(args.input, args.output)
    reader = reader_for(args.input)
    texts = [page_text(page) for page in reader.pages]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(texts) + ("\n" if texts else ""), encoding="utf-8")
    return {"status": "ok", "input": str(args.input.resolve()), "output": str(args.output.resolve()), "pages": len(texts), "text_characters": sum(map(len, texts)), "classification": "textual" if any(t.strip() for t in texts) else "likely-scanned-or-empty"}


def action_split(args: argparse.Namespace) -> dict[str, Any]:
    reader = reader_for(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    PdfWriter = load_pypdf()[1]
    for number, page in enumerate(reader.pages, start=1):
        target = args.output_dir / f"page-{number:03d}.pdf"
        if target.resolve() == args.input.resolve():
            raise PdfError("split destination collides with input")
        writer = PdfWriter()
        writer.add_page(page)
        with target.open("wb") as stream:
            writer.write(stream)
        outputs.append(str(target.resolve()))
    return {"status": "ok", "input": str(args.input.resolve()), "output_dir": str(args.output_dir.resolve()), "pages": len(outputs), "outputs": outputs}


def action_merge(args: argparse.Namespace) -> dict[str, Any]:
    if not args.inputs:
        raise PdfError("merge requires at least one --input PDF")
    for path in args.inputs:
        if not path.exists():
            raise PdfError(f"input PDF not found: {path}")
        ensure_distinct(path, args.output)
    PdfWriter = load_pypdf()[1]
    writer = PdfWriter()
    page_count = 0
    for path in args.inputs:
        reader = reader_for(path)
        for page in reader.pages:
            writer.add_page(page)
            page_count += 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as stream:
        writer.write(stream)
    return {"status": "ok", "inputs": [str(p.resolve()) for p in args.inputs], "output": str(args.output.resolve()), "pages": page_count, "output_sha256": sha256(args.output)}


def parse_pages(value: str, total: int) -> list[int]:
    try:
        pages = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise PdfError("--pages must be a comma-separated list of 1-based integers") from exc
    if len(pages) != total or sorted(pages) != list(range(1, total + 1)):
        raise PdfError(f"--pages must contain every page exactly once (1..{total})")
    return pages


def action_reorder(args: argparse.Namespace) -> dict[str, Any]:
    reader = reader_for(args.input)
    order = parse_pages(args.pages, len(reader.pages))
    ensure_distinct(args.input, args.output)
    PdfWriter = load_pypdf()[1]
    writer = PdfWriter()
    for number in order:
        writer.add_page(reader.pages[number - 1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as stream:
        writer.write(stream)
    return {"status": "ok", "input": str(args.input.resolve()), "output": str(args.output.resolve()), "order": order, "pages": len(order), "output_sha256": sha256(args.output)}


def find_pdftoppm() -> str:
    configured = os.environ.get("PDFTOPPM")
    if configured and Path(configured).is_file():
        return configured
    found = shutil.which("pdftoppm")
    if found:
        return found
    bundled = Path("__HOME__/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm")
    if bundled.is_file():
        return str(bundled)
    raise PdfError("pdftoppm is required for render; install Poppler or set PDFTOPPM")


def action_render(args: argparse.Namespace) -> dict[str, Any]:
    binary = find_pdftoppm()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if any(args.output_dir.glob("page-*.png")):
        raise PdfError("render output directory already contains page-*.png; choose an empty directory")
    prefix = args.output_dir / "page"
    completed = subprocess.run([binary, "-png", str(args.input), str(prefix)], capture_output=True, text=True, check=False)
    if completed.returncode:
        raise PdfError(completed.stderr.strip() or f"pdftoppm exited {completed.returncode}")
    rendered = sorted(str(path.resolve()) for path in args.output_dir.glob("page-*.png"))
    return {"status": "ok", "input": str(args.input.resolve()), "output_dir": str(args.output_dir.resolve()), "rendered_pages": len(rendered), "outputs": rendered, "renderer": binary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("inspect", "extract", "split", "render"):
        command = sub.add_parser(name)
        command.add_argument("--input", required=True, type=Path)
        if name == "extract": command.add_argument("--output", required=True, type=Path)
        if name in {"split", "render"}: command.add_argument("--output-dir", required=True, type=Path)
    merge = sub.add_parser("merge")
    merge.add_argument("--inputs", nargs="+", required=True, type=Path)
    merge.add_argument("--output", required=True, type=Path)
    reorder = sub.add_parser("reorder")
    reorder.add_argument("--input", required=True, type=Path)
    reorder.add_argument("--output", required=True, type=Path)
    reorder.add_argument("--pages", required=True, help="complete 1-based order, e.g. 3,1,2")
    args = parser.parse_args()
    try:
        if not args.input.exists() if hasattr(args, "input") else False:
            raise PdfError(f"input PDF not found: {args.input}")
        result = {"inspect": action_inspect, "extract": action_extract, "split": action_split, "merge": action_merge, "reorder": action_reorder, "render": action_render}[args.action](args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, PdfError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
