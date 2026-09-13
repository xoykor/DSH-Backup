#!/usr/bin/env python3
"""Create a labeled local chart from a validated CSV/TSV/JSON table."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path
from typing import Any


class ChartError(ValueError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            payload = payload["rows"]
        if not isinstance(payload, list) or not payload or any(not isinstance(row, dict) for row in payload):
            raise ChartError("JSON must be a non-empty list of objects or an object with 'rows'")
        columns: list[str] = []
        for row in payload:
            for key in row:
                if key not in columns:
                    columns.append(key)
        return [dict(row) for row in payload], columns
    if path.suffix.lower() not in {".csv", ".tsv"}:
        raise ChartError("input format must be .csv, .tsv, or .json")
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ChartError("CSV/TSV requires a unique header")
        rows = [dict(row) for row in reader]
    if not rows:
        raise ChartError("input table has no rows")
    return rows, list(reader.fieldnames)


def numeric_values(rows: list[dict[str, Any]], column: str) -> list[float]:
    values: list[float] = []
    for number, row in enumerate(rows, start=2):
        value = row.get(column)
        if isinstance(value, bool) or value in (None, ""):
            raise ChartError(f"column {column!r} has a missing/non-numeric value at row {number}")
        try:
            number_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ChartError(f"column {column!r} has a non-numeric value at row {number}: {value!r}") from exc
        if not math.isfinite(number_value):
            raise ChartError(f"column {column!r} has non-finite value at row {number}: {value!r}")
        values.append(number_value)
    return values


def x_values(rows: list[dict[str, Any]], column: str) -> tuple[list[Any], bool]:
    values = [row.get(column) for row in rows]
    if any(value in (None, "") for value in values):
        raise ChartError(f"x column {column!r} contains missing values")
    try:
        numeric = [float(value) for value in values]
    except (TypeError, ValueError):
        return [str(value) for value in values], False
    if any(not math.isfinite(value) for value in numeric):
        raise ChartError(f"x column {column!r} contains a non-finite value")
    return numeric, True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path, help="JSON with kind, x, y, and optional labels")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provenance-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ChartError("chart spec must be a JSON object")
        kind = spec.get("kind")
        x_column = spec.get("x")
        y_spec = spec.get("y")
        y_columns = y_spec if isinstance(y_spec, list) else [y_spec]
        if kind not in {"line", "bar", "scatter"}:
            raise ChartError("kind must be line, bar, or scatter")
        if kind == "bar" and isinstance(y_spec, list) and len(y_spec) > 1:
            raise ChartError("bar charts with multiple y columns are not supported; use one chart per series")
        if not isinstance(x_column, str) or not x_column or not y_columns or any(not isinstance(col, str) or not col for col in y_columns):
            raise ChartError("spec requires x and one or more y column names")
        if args.output.suffix.lower() not in {".png", ".svg", ".pdf"}:
            raise ChartError("output must end in .png, .svg, or .pdf")
        rows, columns = load_rows(args.input)
        missing = {x_column, *y_columns} - set(columns)
        if missing:
            raise ChartError(f"spec columns not found: {sorted(missing)}")
        xs, x_numeric = x_values(rows, x_column)
        ys = {column: numeric_values(rows, column) for column in y_columns}
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise ChartError("matplotlib is required; use a Python runtime that includes it") from exc
        plt.rcParams.update({"font.size": 10, "axes.grid": True, "figure.dpi": 150})
        figure, axis = plt.subplots(figsize=tuple(spec.get("figsize", [8, 4.5])))
        for column in y_columns:
            label = spec.get("labels", {}).get(column, column) if isinstance(spec.get("labels", {}), dict) else column
            if kind == "line": axis.plot(xs, ys[column], marker=spec.get("marker", "o"), label=label)
            elif kind == "bar": axis.bar(xs, ys[column], alpha=0.75, label=label)
            else: axis.scatter(xs, ys[column], label=label)
        axis.set_title(str(spec.get("title", "")))
        axis.set_xlabel(str(spec.get("xlabel", x_column)))
        axis.set_ylabel(str(spec.get("ylabel", ", ".join(y_columns))))
        if len(y_columns) > 1 or spec.get("legend", True):
            axis.legend()
        if not x_numeric:
            axis.tick_params(axis="x", labelrotation=spec.get("xrotation", 0))
        figure.tight_layout()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(args.output, dpi=150 if args.output.suffix.lower() == ".png" else None)
        plt.close(figure)
        args.provenance_dir.mkdir(parents=True, exist_ok=True)
        source_copy = args.provenance_dir / f"source-table{args.input.suffix.lower()}"
        spec_copy = args.provenance_dir / "chart-spec.json"
        if source_copy.resolve() != args.input.resolve():
            shutil.copyfile(args.input, source_copy)
        spec_copy.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        provenance = {
            "status": "ok", "input": str(args.input.resolve()), "input_sha256": sha256(args.input),
            "source_copy": str(source_copy.resolve()), "spec_copy": str(spec_copy.resolve()),
            "output": str(args.output.resolve()), "output_sha256": sha256(args.output),
            "kind": kind, "x": x_column, "y": y_columns, "rows": len(rows), "columns": columns,
        }
        (args.provenance_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(provenance, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ChartError, json.JSONDecodeError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
