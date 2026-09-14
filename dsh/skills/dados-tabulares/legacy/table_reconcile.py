#!/usr/bin/env python3
"""Reconcilie duas tabelas sem descartar chaves duplicadas ou converter tipos."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "legacy"))
from table_transform import detect_format, load_table


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def group_rows(rows, keys):
    groups = defaultdict(list)
    for number, row in enumerate(rows, 1):
        if any(k not in row or row[k] is None or row[k] == "" or type(row[k]) not in (str, int, float, bool) for k in keys):
            raise ValueError(f"linha de dados {number}: chave ausente, vazia ou não escalar")
        values = [row[k] for k in keys]
        groups[canonical(values)].append((number, row))
    return groups


def reconcile(left, right, left_columns, right_columns, spec):
    if not isinstance(spec, dict) or set(spec) - {"keys", "compare_columns", "expected_counts", "max_examples"}:
        raise ValueError("spec contém campos desconhecidos")
    keys = spec.get("keys")
    if not isinstance(keys, list) or not keys or any(not isinstance(k, str) or k not in left_columns or k not in right_columns for k in keys) or len(set(keys)) != len(keys):
        raise ValueError("keys exige colunas únicas presentes nas duas tabelas")
    columns = spec.get("compare_columns", list(dict.fromkeys(left_columns + right_columns)))
    if not isinstance(columns, list) or any(not isinstance(c, str) or c not in left_columns + right_columns for c in columns) or len(set(columns)) != len(columns):
        raise ValueError("compare_columns deve conter colunas únicas existentes")
    columns = [c for c in columns if c not in keys]
    maximum = spec.get("max_examples", 100)
    if type(maximum) is not int or not 1 <= maximum <= 1000: raise ValueError("max_examples deve estar entre 1 e 1000")
    lg, rg = group_rows(left, keys), group_rows(right, keys)
    counts = {"left_rows": len(left), "right_rows": len(right), "left_unique_keys": len(lg), "right_unique_keys": len(rg),
              "only_left_rows": 0, "only_right_rows": 0, "ambiguous_left_rows": 0, "ambiguous_right_rows": 0,
              "equal_pairs": 0, "different_pairs": 0, "different_fields": 0,
              "left_duplicate_groups": sum(len(rows) > 1 for rows in lg.values()),
              "right_duplicate_groups": sum(len(rows) > 1 for rows in rg.values()),
              "left_rows_in_duplicate_groups": sum(len(rows) for rows in lg.values() if len(rows) > 1),
              "right_rows_in_duplicate_groups": sum(len(rows) for rows in rg.values() if len(rows) > 1)}
    examples = {k: [] for k in ("only_left", "only_right", "ambiguous", "differences", "duplicates_left", "duplicates_right")}
    total_examples = 0
    def add(category, value):
        nonlocal total_examples
        if total_examples < maximum:
            examples[category].append(value)
            total_examples += 1
    def refs(group): return {"count": len(group), "data_row_numbers": [n for n, _ in group[:20]], "row_numbers_truncated": len(group) > 20}
    for marker in sorted(lg.keys() | rg.keys()):
        a, b = lg.get(marker, []), rg.get(marker, [])
        key = dict(zip(keys, json.loads(marker)))
        if not b:
            counts["only_left_rows"] += len(a)
            add("only_left", {"key": key, "left": refs(a)})
        elif not a:
            counts["only_right_rows"] += len(b)
            add("only_right", {"key": key, "right": refs(b)})
        elif len(a) > 1 or len(b) > 1:
            counts["ambiguous_left_rows"] += len(a); counts["ambiguous_right_rows"] += len(b)
            add("ambiguous", {"key": key, "left": refs(a), "right": refs(b)})
        else:
            changes = []
            for column in columns:
                av = {"present": column in a[0][1]}; bv = {"present": column in b[0][1]}
                if av["present"]: av["value"] = a[0][1][column]
                if bv["present"]: bv["value"] = b[0][1][column]
                if canonical(av) != canonical(bv): changes.append({"column": column, "left": av, "right": bv})
            counts["different_pairs" if changes else "equal_pairs"] += 1
            counts["different_fields"] += len(changes)
            if changes: add("differences", {"key": key, "left_data_row": a[0][0], "right_data_row": b[0][0], "fields": changes})
    for label, groups in (("left", lg), ("right", rg)):
        for marker, group in groups.items():
            if len(group) > 1: add("duplicates_" + label, {"key": dict(zip(keys, json.loads(marker))), **refs(group)})
    accounted_left = counts["only_left_rows"] + counts["ambiguous_left_rows"] + counts["equal_pairs"] + counts["different_pairs"]
    accounted_right = counts["only_right_rows"] + counts["ambiguous_right_rows"] + counts["equal_pairs"] + counts["different_pairs"]
    if accounted_left != len(left) or accounted_right != len(right): raise ValueError("invariante de contagens falhou")
    expected = spec.get("expected_counts", {})
    if not isinstance(expected, dict) or any(key not in counts or type(value) is not int or value < 0 for key, value in expected.items()):
        raise ValueError("expected_counts deve mapear contagens conhecidas para inteiros não negativos")
    mismatches = {key: {"expected": value, "actual": counts[key]} for key, value in expected.items() if counts[key] != value}
    example_candidates = (sum(not rg.get(k) for k in lg) + sum(not lg.get(k) for k in rg)
                          + sum(bool(lg.get(k)) and bool(rg.get(k)) and (len(lg[k]) > 1 or len(rg[k]) > 1) for k in lg.keys() | rg.keys())
                          + counts["different_pairs"] + counts["left_duplicate_groups"] + counts["right_duplicate_groups"])
    return {"status": "mismatch" if mismatches else "ok", "keys": keys, "compare_columns": columns, "counts": counts,
            "counts_validated": True, "expected_count_mismatches": mismatches, "examples": examples,
            "examples_truncated": example_candidates > total_examples, "example_count": total_examples,
            "duplicate_policy": "report_ambiguous_without_pairing", "row_number_basis": "data rows, 1-based, excludes CSV header"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--left-format", choices=["auto", "csv", "tsv", "json"], default="auto")
    parser.add_argument("--right-format", choices=["auto", "csv", "tsv", "json"], default="auto")
    try:
        args = parser.parse_args()
        if args.output.exists() or args.output.is_symlink(): raise ValueError("saída já existe; use outro caminho")
        sources = [args.left.resolve(strict=True), args.right.resolve(strict=True)]
        if any(path.stat().st_size > 32 * 1024 * 1024 for path in sources) or args.spec.stat().st_size > 1024 * 1024: raise ValueError("entradas excedem 32 MiB ou spec excede 1 MiB")
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in sources]
        left, lc = load_table(sources[0], detect_format(sources[0], args.left_format))
        right, rc = load_table(sources[1], detect_format(sources[1], args.right_format))
        if max(len(left), len(right)) > 100000: raise ValueError("limite de 100000 linhas por tabela")
        result = reconcile(left, right, lc, rc, json.loads(args.spec.read_text(encoding="utf-8")))
        after = [hashlib.sha256(path.read_bytes()).hexdigest() for path in sources]
        if before != after: raise ValueError("entrada mudou durante leitura")
        result["input_sha256"] = {"left": before[0], "right": before[1]}
        encoded = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(encoded) > 8 * 1024 * 1024: raise ValueError("relatório excede 8 MiB; reduza max_examples ou compare_columns")
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream: stream.write(encoded)
        print(json.dumps({"status": result["status"], "output": str(args.output.absolute()), "counts": result["counts"],
                          "expected_count_mismatches": result["expected_count_mismatches"]}, ensure_ascii=False))
        return 0 if result["status"] == "ok" else 3
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__": raise SystemExit(main())
