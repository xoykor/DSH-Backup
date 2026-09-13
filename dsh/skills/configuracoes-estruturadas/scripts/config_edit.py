#!/usr/bin/env python3
"""Edite JSON/YAML/TOML com pré-condições, sem imprimir valores."""
import argparse
import copy
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tomllib

MAX_BYTES = 8 * 1024 * 1024


def kind(value):
    if value is None: return "null"
    if isinstance(value, bool): return "boolean"
    if isinstance(value, int): return "integer"
    if isinstance(value, float): return "number"
    if isinstance(value, str): return "string"
    if isinstance(value, dict): return "object"
    if isinstance(value, list): return "array"
    if isinstance(value, datetime.datetime): return "datetime"
    if isinstance(value, datetime.date): return "date"
    if isinstance(value, datetime.time): return "time"
    raise ValueError("tipo de valor não suportado")


def equal(a, b):
    if kind(a) != kind(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list): return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and math.isnan(a): return math.isnan(b)
    return a == b


def validate_tree(value, ancestors=None, depth=0):
    ancestors = set() if ancestors is None else ancestors
    kind(value)
    if depth > 64: raise ValueError("estrutura excede profundidade 64")
    if isinstance(value, (dict, list)):
        if id(value) in ancestors: raise ValueError("estrutura cíclica não suportada")
        ancestors.add(id(value))
        if isinstance(value, dict) and any(not isinstance(k, str) for k in value):
            raise ValueError("chaves devem ser strings")
        for child in (value.values() if isinstance(value, dict) else value):
            validate_tree(child, ancestors, depth + 1)
        ancestors.remove(id(value))


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("chave duplicada")
        result[key] = value
    return result


def parse(text, fmt):
    try:
        if fmt == "json":
            result = json.loads(text, object_pairs_hook=unique_pairs,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("constante JSON inválida")))
        elif fmt == "toml":
            result = tomllib.loads(text)
        else:
            try: import yaml
            except ImportError: raise ValueError("dependência ausente: PyYAML")
            class UniqueLoader(yaml.SafeLoader): pass
            def mapping(loader, node):
                loader.flatten_mapping(node)
                return unique_pairs([(loader.construct_object(k), loader.construct_object(v)) for k, v in node.value])
            UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
            result = yaml.load(text, Loader=UniqueLoader)
        validate_tree(result)
        if not isinstance(result, (dict, list)): raise ValueError("raiz deve ser objeto ou array")
        return result
    except ImportError: raise
    except Exception as exc:
        if str(exc) == "dependência ausente: PyYAML": raise
        raise ValueError("entrada inválida ou estrutura não suportada (conteúdo omitido)") from None


def toml_value(value):
    typ = kind(value)
    if typ == "null": raise ValueError("TOML não suporta null")
    if typ == "boolean": return "true" if value else "false"
    if typ in ("integer", "number"):
        if typ == "integer" and not -(2**63) <= value < 2**63: raise ValueError("inteiro excede faixa TOML 64 bits")
        return repr(value)
    if typ == "string": return json.dumps(value, ensure_ascii=False)
    if typ in ("datetime", "date", "time"): return value.isoformat()
    if typ == "array": return "[" + ", ".join(toml_value(v) for v in value) + "]"
    return "{ " + ", ".join(json.dumps(k, ensure_ascii=False) + " = " + toml_value(v) for k, v in value.items()) + " }"


def serialize(value, fmt):
    try:
        if fmt == "json": return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if fmt == "yaml":
            import yaml
            return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
        if not isinstance(value, dict): raise ValueError("TOML exige objeto na raiz")
        return "\n".join(json.dumps(k, ensure_ascii=False) + " = " + toml_value(v) for k, v in value.items()) + "\n"
    except (TypeError, OverflowError): raise ValueError("valor incompatível com formato de saída") from None


def apply(document, operations):
    if not isinstance(operations, list) or not 1 <= len(operations) <= 128:
        raise ValueError("operations deve conter de 1 a 128 operações")
    result, changes = copy.deepcopy(document), []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict): raise ValueError("operação deve ser objeto")
        if set(operation) - {"op", "path", "expected", "expected_type", "expected_absent", "value", "value_type"}:
            raise ValueError("campo desconhecido na operação")
        path = operation.get("path")
        if not isinstance(path, list) or not 1 <= len(path) <= 64 or any(type(k) not in (str, int) for k in path):
            raise ValueError("path deve ser array de chaves string ou índices inteiros")
        parent = result
        for component in path[:-1]:
            if isinstance(parent, dict) and isinstance(component, str) and component in parent: parent = parent[component]
            elif isinstance(parent, list) and type(component) is int and 0 <= component < len(parent): parent = parent[component]
            else: raise ValueError(f"operação {index}: caminho intermediário inexistente")
        key = path[-1]
        if isinstance(parent, dict) and isinstance(key, str): exists = key in parent
        elif isinstance(parent, list) and type(key) is int and 0 <= key < len(parent): exists = True
        else: raise ValueError(f"operação {index}: caminho final inválido")
        op = operation.get("op")
        if op not in ("set", "delete"): raise ValueError("op deve ser set ou delete")
        if operation.get("expected_absent") is True:
            if exists or "expected" in operation or "expected_type" in operation or op != "set":
                raise ValueError(f"operação {index}: pré-condição de ausência falhou")
        else:
            if "expected_absent" in operation or not exists or "expected" not in operation or "expected_type" not in operation:
                raise ValueError(f"operação {index}: expected e expected_type são obrigatórios para chave existente")
            if kind(parent[key]) != operation["expected_type"] or not equal(parent[key], operation["expected"]):
                raise ValueError(f"operação {index}: pré-condição de valor/tipo falhou (valores omitidos)")
        previous_type = kind(parent[key]) if exists else "absent"
        if op == "set":
            if "value" not in operation or kind(operation["value"]) != operation.get("value_type"):
                raise ValueError(f"operação {index}: value e value_type compatíveis são obrigatórios")
            validate_tree(operation["value"])
            parent[key] = copy.deepcopy(operation["value"])
        else:
            if "value" in operation or "value_type" in operation: raise ValueError("delete não aceita value")
            del parent[key]
        changes.append({"operation": op, "path": path, "before_type": previous_type,
                        "after_type": kind(parent[key]) if op == "set" else "absent"})
    return result, changes


def run(args):
    source = args.input.resolve(strict=True)
    target = args.output.absolute()
    if target.exists() or target.is_symlink(): raise ValueError("saída já existe; escolha novo arquivo")
    if source.stat().st_size > MAX_BYTES or args.spec.stat().st_size > MAX_BYTES: raise ValueError("arquivo excede 8 MiB")
    formats = {".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml"}
    fmt = args.format or formats.get(source.suffix.lower())
    if not fmt: raise ValueError("formato desconhecido; use --format")
    raw = source.read_bytes()
    document = parse(raw.decode("utf-8"), fmt)
    spec = json.loads(args.spec.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
    if not isinstance(spec, dict) or set(spec) != {"operations"}: raise ValueError("spec exige somente operations")
    result, changes = apply(document, spec["operations"])
    encoded = serialize(result, fmt).encode("utf-8")
    if len(encoded) > MAX_BYTES: raise ValueError("saída excede 8 MiB")
    if not equal(result, parse(encoded.decode("utf-8"), fmt)): raise ValueError("validação round-trip falhou")
    if source.read_bytes() != raw: raise ValueError("entrada mudou durante processamento")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return {"status": "ok", "output": str(target), "format": fmt, "changes": changes,
            "values_redacted": True, "input_sha256": hashlib.sha256(raw).hexdigest(),
            "output_sha256": hashlib.sha256(encoded).hexdigest(), "roundtrip_validated": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--format", choices=["json", "yaml", "toml"])
    try:
        print(json.dumps(run(parser.parse_args()), ensure_ascii=False))
        return 0
    except Exception as exc:
        # Parser/OS diagnostics may include secrets from malformed input: omit them.
        message = str(exc) if type(exc) is ValueError and not isinstance(exc, json.JSONDecodeError) else type(exc).__name__
        print(json.dumps({"status": "error", "error": message}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__": raise SystemExit(main())
