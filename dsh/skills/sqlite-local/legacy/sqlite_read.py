#!/usr/bin/env python3
"""Inspeção e consultas SQLite somente leitura, com limites e parâmetros."""
import argparse
import base64
import csv
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

MAX_RESULT = 1024 * 1024
MAX_CELL = 64 * 1024
READ_PRAGMAS = {"table_info", "table_xinfo", "index_info", "index_xinfo", "index_list", "foreign_key_list"}


def authorize(action, first, second, database, trigger):
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE): return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION:
        return sqlite3.SQLITE_DENY if (second or first or "").lower() in {"load_extension", "writefile", "readfile", "edit", "eval", "fts3_tokenizer"} else sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_PRAGMA and (first or "").lower() in READ_PRAGMAS: return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def encode_value(value):
    if isinstance(value, (str, bytes)) and len(value.encode("utf-8") if isinstance(value, str) else value) > MAX_CELL:
        raise ValueError("célula excede 64 KiB; selecione substrings ou agregue a consulta")
    if isinstance(value, bytes): return {"type": "blob", "base64": base64.b64encode(value).decode("ascii")}
    return value


def bounded_rows(cursor, limit):
    rows, size = [], 0
    for _ in range(limit):
        row = cursor.fetchone()
        if row is None: return rows, False
        encoded = [encode_value(value) for value in row]
        size += len(json.dumps(encoded, ensure_ascii=False).encode("utf-8"))
        if size > MAX_RESULT: raise ValueError("resultado excede 1 MiB; reduza colunas/linhas")
        rows.append(encoded)
    return rows, cursor.fetchone() is not None


def export(path, fmt, payload):
    target = path.absolute()
    if target.exists() or target.is_symlink(): raise ValueError("saída existente; sobrescrita recusada")
    if fmt == "json": encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    else:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(payload["columns"])
        for row in payload["rows"]:
            writer.writerow([json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v for v in row])
        encoded = stream.getvalue().encode("utf-8")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return str(target)


def run(args):
    source = args.database.resolve(strict=True)
    if not source.is_file(): raise ValueError("database deve ser arquivo regular")
    spec = {}
    if args.spec:
        if args.spec.stat().st_size > 1024 * 1024: raise ValueError("spec excede 1 MiB")
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or set(spec) - {"sql", "params", "max_rows", "timeout_seconds"}:
        raise ValueError("spec contém campos desconhecidos")
    maximum = spec.get("max_rows", 100)
    timeout = spec.get("timeout_seconds", 3)
    if type(maximum) is not int or not 1 <= maximum <= 10000: raise ValueError("max_rows deve estar entre 1 e 10000")
    if type(timeout) not in (int, float) or not 0.1 <= timeout <= 30: raise ValueError("timeout_seconds deve estar entre 0.1 e 30")
    if args.mode == "query":
        sql = spec.get("sql")
        params = spec.get("params", [])
        if not isinstance(sql, str) or not sql.strip() or len(sql.encode("utf-8")) > 128 * 1024: raise ValueError("sql obrigatório, até 128 KiB")
        if not isinstance(params, (dict, list)) or any(type(v) not in (str, int, float, bool, type(None)) for v in (params.values() if isinstance(params, dict) else params)):
            raise ValueError("params deve ser lista ou objeto de valores escalares JSON")
    else:
        if "sql" in spec or "params" in spec: raise ValueError("schema não aceita sql/params")
        sql = "SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        params = []
    start = time.monotonic()
    deadline = start + timeout
    connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=min(timeout, 1))
    try:
        connection.enable_load_extension(False)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RESULT)
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 128 * 1024)
        connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 256)
        connection.execute("BEGIN")
        connection.set_authorizer(authorize)
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        cursor = connection.execute(sql, params)
        if cursor.description is None: raise ValueError("consulta não produz tabela")
        columns = [column[0] for column in cursor.description]
        rows, truncated = bounded_rows(cursor, maximum)
        if time.monotonic() > deadline: raise ValueError("consulta excedeu timeout_seconds")
        payload = {"status": "ok", "mode": args.mode, "columns": columns, "rows": rows,
                   "returned_rows": len(rows), "truncated": truncated, "max_rows": maximum,
                   "read_only": True, "snapshot": "SQLite read transaction (includes committed WAL)",
                   "elapsed_seconds": round(time.monotonic() - start, 3)}
    finally:
        connection.close()
    if args.output:
        fmt = args.output_format or ("csv" if args.output.suffix.lower() == ".csv" else "json")
        payload["output"] = export(args.output, fmt, payload)
        payload.pop("rows")
        payload["output_format"] = fmt
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--mode", choices=["schema", "query"], default="schema")
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=["json", "csv"])
    try:
        print(json.dumps(run(parser.parse_args()), ensure_ascii=False))
        return 0
    except Exception as exc:
        # SQL/parser errors can echo data; keep diagnostics bounded and free of query literals.
        message = str(exc) if type(exc) is ValueError else type(exc).__name__
        print(json.dumps({"status": "error", "error": message}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__": raise SystemExit(main())
