#!/usr/bin/env python3
"""Planeje e aplique cópias/renomeações explícitas, com verificação e diário."""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time


def check_deadline(deadline):
    if time.monotonic() > deadline: raise ValueError("tempo limite excedido")


def path_parts(value):
    if not isinstance(value, str) or not value or "\x00" in value: raise ValueError("caminho relativo inválido")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in (".", "..", "") for p in value.split("/")):
        raise ValueError("caminho absoluto, vazio ou escape recusado")
    return path.parts


def root_open(root):
    root = Path(root).absolute()
    # Walk from / with no-follow on every component, retaining a directory fd.
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in root.parts[1:]:
            if part == "..": raise ValueError("root não pode conter ..")
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return root, fd
    except BaseException:
        os.close(fd)
        raise


def parent_open(rootfd, value):
    parts = path_parts(value)
    fd = os.dup(rootfd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd, parts[-1]
    except BaseException:
        os.close(fd)
        raise


def info(st):
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise ValueError("somente arquivo regular sem hardlinks é aceito")
    return {"device": st.st_dev, "inode": st.st_ino, "size": st.st_size,
            "mtime_ns": st.st_mtime_ns, "mode": stat.S_IMODE(st.st_mode)}


def digest_fd(fd, deadline):
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while True:
        check_deadline(deadline)
        chunk = os.read(fd, 1024 * 1024)
        if not chunk: break
        digest.update(chunk)
    return digest.hexdigest()


def snapshot(rootfd, value, deadline):
    parent, name = parent_open(rootfd, value)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = info(os.fstat(fd))
            digest = digest_fd(fd, deadline)
            if before != info(os.fstat(fd)): raise ValueError("origem mudou durante leitura")
            return {**before, "sha256": digest}
        finally: os.close(fd)
    finally: os.close(parent)


def absent(rootfd, value):
    parent, name = parent_open(rootfd, value)
    try:
        try: os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError: return
        raise ValueError("destino já existe; sobrescrita recusada")
    finally: os.close(parent)


def validate_operations(operations):
    if not isinstance(operations, list) or not 1 <= len(operations) <= 1000:
        raise ValueError("operations deve conter 1 a 1000 itens")
    sources, targets = set(), set()
    for entry in operations:
        if not isinstance(entry, dict) or entry.get("op") not in ("copy", "rename"): raise ValueError("op deve ser copy ou rename")
        if set(entry) - {"op", "source", "destination", "snapshot"}: raise ValueError("campo desconhecido na operação")
        source, target = entry.get("source"), entry.get("destination")
        path_parts(source); path_parts(target)
        if source in sources or target in targets: raise ValueError("origens/destinos repetidos no plano")
        sources.add(source); targets.add(target)
    if sources & targets: raise ValueError("destinos não podem ser origens do mesmo plano")


def write_json_exclusive(path, payload):
    path = Path(path).absolute()
    parent_path, filename = path.parent, path.name
    _, parentfd = root_open(parent_path)
    try:
        fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parentfd)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    finally: os.close(parentfd)


def plan(spec, output, deadline):
    if not isinstance(spec, dict) or set(spec) != {"root", "operations"}: raise ValueError("spec exige root e operations")
    validate_operations(spec["operations"])
    root, rootfd = root_open(spec["root"])
    try:
        entries = []
        for entry in spec["operations"]:
            if "snapshot" in entry: raise ValueError("snapshot é gerado pelo planner")
            absent(rootfd, entry["destination"])
            if Path(output).absolute() in (root / entry["source"], root / entry["destination"]):
                raise ValueError("plano não pode ocupar origem/destino")
            entries.append({**entry, "snapshot": snapshot(rootfd, entry["source"], deadline)})
        rootstat = os.fstat(rootfd)
        result = {"version": 1, "root": str(root), "root_identity": [rootstat.st_dev, rootstat.st_ino], "operations": entries}
        hashes = {}
        for entry in entries: hashes.setdefault(entry["snapshot"]["sha256"], []).append(entry["source"])
        result["duplicates_by_content"] = [names for names in hashes.values() if len(names) > 1]
        write_json_exclusive(output, result)
        return {"status": "planned", "dry_run": True, "plan": str(Path(output).absolute()),
                "operations": len(entries), "duplicates_by_content": result["duplicates_by_content"]}
    finally: os.close(rootfd)


def rename_noreplace(sourcefd, source, targetfd, target):
    libc = ctypes.CDLL(None, use_errno=True)
    try: fn = libc.renameat2
    except AttributeError: raise ValueError("rename seguro requer Linux/glibc com renameat2")
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(sourcefd, os.fsencode(source), targetfd, os.fsencode(target), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def perform(rootfd, entry, deadline):
    sourcefd, source = parent_open(rootfd, entry["source"])
    targetfd = None
    try:
        targetfd, target = parent_open(rootfd, entry["destination"])
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=sourcefd)
        try:
            before = info(os.fstat(fd))
            if {**before, "sha256": digest_fd(fd, deadline)} != entry["snapshot"]: raise ValueError("origem mudou após plano")
            if entry["op"] == "copy":
                out = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=targetfd)
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    while True:
                        check_deadline(deadline)
                        chunk = os.read(fd, 1024 * 1024)
                        if not chunk: break
                        view = memoryview(chunk)
                        while view: view = view[os.write(out, view):]
                    # Do not propagate executable/setuid modes implicitly.
                    os.fsync(out)
                finally: os.close(out)
            else:
                current = os.stat(source, dir_fd=sourcefd, follow_symlinks=False)
                if info(current) != before: raise ValueError("origem substituída antes do rename")
                rename_noreplace(sourcefd, source, targetfd, target)
                os.fsync(sourcefd)
            os.fsync(targetfd)
            if info(os.fstat(fd)) != before: raise ValueError("origem mudou durante operação; consulte diário")
        finally: os.close(fd)
        final = snapshot(rootfd, entry["destination"], deadline)
        if final["sha256"] != entry["snapshot"]["sha256"] or final["size"] != entry["snapshot"]["size"]:
            raise ValueError("verificação do destino falhou; consulte diário")
        return final
    finally:
        os.close(sourcefd)
        if targetfd is not None: os.close(targetfd)


def apply_plan(payload, journal_path, deadline):
    if not isinstance(payload, dict) or payload.get("version") != 1: raise ValueError("versão de plano inválida")
    validate_operations(payload.get("operations"))
    root, rootfd = root_open(payload.get("root"))
    journal_path = Path(journal_path).absolute()
    journalfd = None
    completed = 0
    try:
        rootstat = os.fstat(rootfd)
        if [rootstat.st_dev, rootstat.st_ino] != payload.get("root_identity"): raise ValueError("diretório root foi substituído")
        for entry in payload["operations"]:
            if journal_path in (root / entry["source"], root / entry["destination"]): raise ValueError("diário conflita com plano")
            absent(rootfd, entry["destination"])
            if snapshot(rootfd, entry["source"], deadline) != entry.get("snapshot"): raise ValueError("origem mudou; gere novo plano")
        _, parentfd = root_open(journal_path.parent)
        try: journalfd = os.open(journal_path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parentfd)
        finally: os.close(parentfd)
        def record(item):
            data = (json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8")
            while data: data = data[os.write(journalfd, data):]
            os.fsync(journalfd)
        record({"event": "start", "root": str(root), "operations": len(payload["operations"])})
        for index, entry in enumerate(payload["operations"]):
            recovery = ({"action": "rename_back_after_verifying_hash_and_free_destination", "source": entry["destination"], "destination": entry["source"], "sha256": entry["snapshot"]["sha256"]}
                        if entry["op"] == "rename" else {"action": "retain_original_and_inspect_copy", "source": entry["source"], "destination": entry["destination"]})
            record({"event": "started", "index": index, "operation": entry, "recovery": recovery, "automatic_recovery": False})
            try:
                final = perform(rootfd, entry, deadline)
                record({"event": "completed", "index": index, "verified_sha256": final["sha256"]})
                completed += 1
            except Exception as exc:
                record({"event": "failed_or_partial", "index": index, "error": type(exc).__name__, "inspect_before_retry": True})
                return {"status": "partial" if completed else "error", "completed": completed, "failed_index": index,
                        "journal": str(journal_path), "error": str(exc), "automatic_rollback": False}
        record({"event": "finished", "completed": completed})
        return {"status": "ok", "completed": completed, "journal": str(journal_path), "verified": True}
    finally:
        if journalfd is not None: os.close(journalfd)
        os.close(rootfd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "apply"])
    parser.add_argument("--spec", required=True, type=Path, help="especificação em plan; plano gerado em apply")
    parser.add_argument("--output", required=True, type=Path, help="plano em plan; diário JSONL novo em apply")
    parser.add_argument("--timeout", type=float, default=120)
    try:
        args = parser.parse_args()
        if not 1 <= args.timeout <= 3600: raise ValueError("timeout deve estar entre 1 e 3600 segundos")
        if args.spec.stat().st_size > 4 * 1024 * 1024: raise ValueError("spec excede 4 MiB")
        payload = json.loads(args.spec.read_text(encoding="utf-8"))
        deadline = time.monotonic() + args.timeout
        result = plan(payload, args.output, deadline) if args.mode == "plan" else apply_plan(payload, args.output, deadline)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] in ("ok", "planned") else 2
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__": raise SystemExit(main())
