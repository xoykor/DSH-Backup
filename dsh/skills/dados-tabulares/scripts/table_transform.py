#!/usr/bin/env python3
"""Deterministic, explicit CSV/TSV/JSON table transformations."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


class TableError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def detect_format(path: Path, requested: str | None = None) -> str:
    if requested and requested != "auto":
        return requested
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".tsv":
        return "tsv"
    if suffix in {".csv", ".txt"}:
        return "csv"
    raise TableError(f"cannot infer table format from {path.name}; pass --input-format")


def load_table(path: Path, fmt: str) -> tuple[list[dict[str, Any]], list[str]]:
    if fmt == "json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TableError(f"invalid JSON: {exc}") from exc
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            payload = payload["rows"]
        if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
            raise TableError("JSON must be a list of objects or an object with a 'rows' list")
        columns: list[str] = []
        for row in payload:
            for key in row:
                if not isinstance(key, str):
                    raise TableError("JSON object keys must be strings")
                if key not in columns:
                    columns.append(key)
        return [dict(row) for row in payload], columns

    delimiter = "\t" if fmt == "tsv" else ","
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        if not reader.fieldnames:
            raise TableError("CSV/TSV must contain a header row")
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise TableError("CSV/TSV header contains duplicate column names")
        rows: list[dict[str, Any]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise TableError(f"line {line_number} has more fields than the header")
            rows.append(dict(row))
        return rows, list(reader.fieldnames)


def _condition(value: Any, rule: Any) -> bool:
    if not isinstance(rule, dict):
        return value == rule
    if len(rule) != 1:
        raise TableError("each filter condition must contain exactly one operator")
    operator, expected = next(iter(rule.items()))
    if operator == "eq":
        return value == expected
    if operator == "ne":
        return value != expected
    if operator == "in":
        if not isinstance(expected, list):
            raise TableError("filter 'in' expects a list")
        return value in expected
    if operator == "contains":
        return isinstance(value, str) and str(expected) in value
    if operator in {"gt", "gte", "lt", "lte"}:
        try:
            left, right = float(value), float(expected)
        except (TypeError, ValueError) as exc:
            raise TableError(f"numeric filter {operator} received non-numeric data") from exc
        return {"gt": left > right, "gte": left >= right, "lt": left < right, "lte": left <= right}[operator]
    if operator == "not_empty":
        if not isinstance(expected, bool):
            raise TableError("filter 'not_empty' expects a boolean")
        return (value not in (None, "")) if expected else (value in (None, ""))
    raise TableError(f"unsupported filter operator: {operator}")


def apply_operations(rows: list[dict[str, Any]], columns: list[str], operations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict) or not isinstance(operation.get("op"), str):
            raise TableError(f"operation {index} must be an object with an 'op' string")
        name = operation["op"]
        if name == "clean":
            trim = operation.get("trim_strings", True)
            collapse = operation.get("collapse_whitespace", False)
            if not isinstance(trim, bool) or not isinstance(collapse, bool):
                raise TableError("clean options must be booleans")
            for row in rows:
                for key, value in list(row.items()):
                    if isinstance(value, str):
                        if trim:
                            value = value.strip()
                        if collapse:
                            value = re.sub(r"\s+", " ", value)
                        row[key] = value
        elif name == "filter":
            where = operation.get("where")
            if not isinstance(where, dict) or not where:
                raise TableError("filter requires a non-empty 'where' object")
            unknown = set(where) - set(columns)
            if unknown:
                raise TableError(f"filter columns not found: {sorted(unknown)}")
            rows = [row for row in rows if all(_condition(row.get(key, ""), rule) for key, rule in where.items())]
        elif name == "dedupe":
            keys = operation.get("keys")
            keep = operation.get("keep", "first")
            if not isinstance(keys, list) or not keys or any(key not in columns for key in keys):
                raise TableError("dedupe requires non-empty 'keys' containing existing columns")
            if keep not in {"first", "last"}:
                raise TableError("dedupe 'keep' must be 'first' or 'last'")
            if keep == "first":
                seen: set[tuple[str, ...]] = set()
                kept: list[dict[str, Any]] = []
                for row in rows:
                    marker = tuple(json.dumps(row.get(key, ""), ensure_ascii=False, sort_keys=True, separators=(",", ":")) for key in keys)
                    if marker not in seen:
                        seen.add(marker)
                        kept.append(row)
                rows = kept
            else:
                positions: dict[tuple[str, ...], int] = {}
                for pos, row in enumerate(rows):
                    positions[tuple(json.dumps(row.get(key, ""), ensure_ascii=False, sort_keys=True, separators=(",", ":")) for key in keys)] = pos
                rows = [row for pos, row in enumerate(rows) if positions[tuple(json.dumps(row.get(key, ""), ensure_ascii=False, sort_keys=True, separators=(",", ":")) for key in keys)] == pos]
        elif name == "select":
            selected = operation.get("columns")
            if not isinstance(selected, list) or not selected or any(key not in columns for key in selected):
                raise TableError("select requires a non-empty list of existing columns")
            columns = list(selected)
            rows = [{key: row.get(key, "") for key in columns} for row in rows]
        elif name == "rename":
            mapping = operation.get("mapping")
            if not isinstance(mapping, dict) or any(old not in columns for old in mapping):
                raise TableError("rename requires a mapping whose source columns exist")
            renamed: list[str] = []
            for key in columns:
                new_key = mapping.get(key, key)
                if not isinstance(new_key, str) or not new_key:
                    raise TableError("renamed columns must be non-empty strings")
                renamed.append(new_key)
            if len(set(renamed)) != len(renamed):
                raise TableError("rename would create duplicate column names")
            rows = [{mapping.get(key, key): value for key, value in row.items()} for row in rows]
            columns = renamed
        else:
            raise TableError(f"unsupported operation: {name}")
    return rows, columns


def write_table(path: Path, fmt: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    delimiter = "\t" if fmt == "tsv" else ","
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter=delimiter, extrasaction="raise")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in columns} for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--operations", type=Path, help="JSON list or {'operations': [...]} of explicit operations")
    parser.add_argument("--input-format", choices=["auto", "csv", "tsv", "json"], default="auto")
    parser.add_argument("--output-format", choices=["auto", "csv", "tsv", "json"], default="auto")
    args = parser.parse_args()
    try:
        source = args.input.resolve()
        destination = args.output.resolve()
        if source == destination or (destination.exists() and os.path.samefile(source, destination)):
            raise TableError("refusing to overwrite the input; choose a separate --output")
        input_fmt = detect_format(source, args.input_format)
        output_fmt = detect_format(destination, args.output_format)
        rows, columns = load_table(source, input_fmt)
        operations: list[dict[str, Any]] = []
        if args.operations:
            spec = json.loads(args.operations.read_text(encoding="utf-8"))
            operations = spec.get("operations") if isinstance(spec, dict) else spec
            if not isinstance(operations, list):
                raise TableError("operations file must be a list or an object with an 'operations' list")
        before = len(rows)
        rows, columns = apply_operations(rows, columns, operations)
        write_table(destination, output_fmt, rows, columns)
        result = {
            "status": "ok", "input": str(source), "output": str(destination),
            "input_format": input_fmt, "output_format": output_fmt,
            "input_sha256": sha256(source), "output_sha256": sha256(destination),
            "rows_before": before, "rows_after": len(rows),
            "removed_rows": before - len(rows), "columns": columns,
            "operations": [op.get("op") for op in operations],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, TableError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
