#!/usr/bin/env python3
"""OCR selected PDF pages or one image with Tesseract and a total deadline."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


class OCRError(Exception):
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def execute(argv, deadline):
    left = deadline - time.monotonic()
    if left <= 0:
        raise OCRError("total timeout exceeded")
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(argv, stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            proc.wait(timeout=left)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            raise OCRError("total timeout exceeded; process group terminated") from exc
        stdout.seek(0)
        result = stdout.read(65537)
        if len(result) > 65536:
            raise OCRError("tool response exceeded 64 KiB")
        if proc.returncode:
            # Document content and paths in stderr are not echoed into diagnostics.
            raise OCRError(f"{Path(argv[0]).name} exited with code {proc.returncode}")
        return result.decode("utf-8", errors="replace")


def binary(name):
    found = shutil.which(name)
    if found:
        return found
    for root in [Path('__HOME__/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override'),
                 Path('__HOME__/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback')]:
        if (root / name).is_file():
            return str(root / name)
    raise OCRError(f"missing dependency: {name}")


def language_files(tesseract, languages, explicit, deadline):
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*", languages):
        raise OCRError("invalid language name")
    roots = [Path(explicit)] if explicit else []
    roots.append(Path(__file__).resolve().parent.parent / "assets" / "tessdata")
    if os.environ.get("TESSDATA_PREFIX"):
        roots.append(Path(os.environ["TESSDATA_PREFIX"]))
    listing = execute([tesseract, "--list-langs"], deadline)
    match = re.search(r'List of available languages in "([^"]+)"', listing)
    if match:
        roots.append(Path(match[1]))
    roots += [Path("/usr/share/tessdata"), Path("/usr/share/tesseract-ocr/5/tessdata")]
    result = {}
    for lang in languages.split("+"):
        found = next((r / (lang + ".traineddata") for r in roots if (r / (lang + ".traineddata")).is_file()), None)
        if found is None:
            raise OCRError(f"missing Tesseract language: {lang}; supply --tessdata-dir")
        result[lang] = found.resolve()
    return result


def select_pages(value, total):
    pages = []
    for item in value.split(","):
        if re.fullmatch(r"[1-9][0-9]*", item):
            pages.append(int(item))
        elif re.fullmatch(r"[1-9][0-9]*-[1-9][0-9]*", item):
            first, last = map(int, item.split("-"))
            if last < first or last - first > 99:
                raise OCRError("invalid page range; maximum 100 pages per call")
            pages.extend(range(first, last + 1))
        else:
            raise OCRError("pages must be 1-based numbers or ranges, e.g. 1,3-5")
    if not pages or len(pages) > 100 or len(set(pages)) != len(pages) or any(p > total for p in pages):
        raise OCRError("pages contain duplicates, exceed document length or exceed 100 pages")
    return pages


def ocr(args):
    start = time.monotonic()
    if not 1 <= args.timeout_seconds <= 600 or not 72 <= args.dpi <= 400:
        raise OCRError("timeout must be 1..600 seconds and DPI 72..400")
    source = args.input.resolve(strict=True)
    if not source.is_file():
        raise OCRError("input must be a file")
    deadline = start + args.timeout_seconds
    tesseract = binary("tesseract")
    langs = language_files(tesseract, args.lang, args.tessdata_dir, deadline)
    with source.open("rb") as stream:
        is_pdf = stream.read(5) == b"%PDF-"
    total = 1
    render = None
    if is_pdf:
        if not args.pages:
            raise OCRError("PDF OCR requires explicit --pages, e.g. 1-3")
        render = binary("pdftoppm")
        info = execute([binary("pdfinfo"), str(source)], deadline)
        count = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
        if not count:
            raise OCRError("cannot determine PDF page count")
        total = int(count[1])
    pages = select_pages(args.pages or "1", total)
    input_hash = digest(source)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "running", "input": str(source), "input_sha256": input_hash,
              "languages": list(langs), "language_sha256": {k: digest(v) for k, v in langs.items()},
              "source_pages": total, "requested_pages": pages, "pages": [], "psm": args.psm,
              "dpi": args.dpi if is_pdf else None, "text_is_machine_recognized": True}
    try:
        with tempfile.TemporaryDirectory(prefix="dsh-ocr-") as raw_work:
            work = Path(raw_work)
            data_dir = work / "tessdata"
            data_dir.mkdir()
            for lang, path in langs.items():
                (data_dir / (lang + ".traineddata")).symlink_to(path)
            # Provide output format configs even when using a private tessdata directory.
            (data_dir / "configs").mkdir()
            (data_dir / "configs" / "txt").write_text("tessedit_create_txt 1\n")
            (data_dir / "configs" / "tsv").write_text("tessedit_create_tsv 1\n")
            for page in pages:
                image = source
                if is_pdf:
                    prefix = work / f"page-{page:03d}"
                    execute([render, "-f", str(page), "-l", str(page), "-singlefile", "-r", str(args.dpi),
                             "-scale-to", "5000", "-png", str(source), str(prefix)], deadline)
                    image = prefix.with_suffix(".png")
                    if not image.is_file():
                        raise OCRError("renderer did not create selected page")
                prefix = output / f"page-{page:03d}"
                execute([tesseract, str(image), str(prefix.resolve()), "--tessdata-dir", str(data_dir),
                         "-l", args.lang, "--psm", str(args.psm), "txt", "tsv"], deadline)
                text_path, tsv_path = prefix.with_suffix(".txt"), prefix.with_suffix(".tsv")
                if not text_path.is_file() or not tsv_path.is_file():
                    raise OCRError("Tesseract did not produce TXT and TSV outputs")
                if text_path.stat().st_size > 8 * 1024 * 1024 or tsv_path.stat().st_size > 32 * 1024 * 1024:
                    raise OCRError("OCR output too large for one page")
                text = text_path.read_text(encoding="utf-8")
                confidences = []
                with tsv_path.open(encoding="utf-8", newline="") as stream:
                    reader = csv.DictReader(stream, delimiter="\t")
                    if not reader.fieldnames or not {"text", "conf", "level"} <= set(reader.fieldnames):
                        raise OCRError("invalid TSV output")
                    for row in reader:
                        if row.get("level") == "5" and (row.get("text") or "").strip():
                            conf = float(row["conf"])
                            if conf >= 0:
                                confidences.append(conf)
                report["pages"].append({"page": page, "text": str(text_path.resolve()), "tsv": str(tsv_path.resolve()),
                    "characters": len(text), "empty": not bool(text.strip()), "words": len(confidences),
                    "mean_engine_confidence": round(sum(confidences)/len(confidences), 2) if confidences else None,
                    "text_sha256": digest(text_path), "tsv_sha256": digest(tsv_path)})
        if digest(source) != input_hash:
            raise OCRError("input changed during OCR")
        report["status"] = "completed_empty" if all(p["empty"] for p in report["pages"]) else "completed"
    except (OCRError, OSError, ValueError) as exc:
        report["status"] = "partial" if report["pages"] else "failed"
        report["error"] = str(exc)
    report["duration_seconds"] = round(time.monotonic() - start, 3)
    with (output / "report.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pages")
    parser.add_argument("--lang", default="por")
    parser.add_argument("--tessdata-dir", type=Path)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--psm", type=int, choices=[3, 4, 6, 7, 11], default=3)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    args = parser.parse_args()
    try:
        report = ocr(args)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["status"] in {"completed", "completed_empty"} else 2
    except (OCRError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
