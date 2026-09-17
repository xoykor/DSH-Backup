#!/usr/bin/env python3
"""Local Prism modpack workbench. Python 3.11+, standard library only."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
import zipfile


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identifier():
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]


def safe_id(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("ID inválido")
    return value


def process_identity(pid):
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text().rsplit(") ", 1)[1].split()
        if stat[0] == "Z":
            return None
        return stat[19]  # starttime, field 22; independent of PID reuse
    except (OSError, ValueError, IndexError):
        return None


def update_ini_section(path, section, values):
    """Update simple key=value entries while preserving unrelated formatting."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"Configuração não pode ser link simbólico: {path}")
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    header = f"[{section}]"
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == header) + 1
    except StopIteration:
        raise ValueError(f"Seção {header} ausente em {path}") from None
    end = next((index for index in range(start, len(lines))
                if re.fullmatch(r"\s*\[[^]]+\]\s*", lines[index])), len(lines))
    pending = dict(values)
    updated = lines[:start]
    for line in lines[start:end]:
        match = re.match(r"\s*([^#;=\s]+)\s*=", line)
        key = match.group(1) if match else None
        if key in values:
            if key in pending:
                updated.append(f"{key}={pending.pop(key)}")
            continue
        updated.append(line)
    updated.extend(f"{key}={value}" for key, value in pending.items())
    updated.extend(lines[end:])
    rendered = "\n".join(updated) + ("\n" if original.endswith("\n") else "")
    if rendered == original:
        return False
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)
    return True


class Workbench:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.settings = read(self.root / "project.json")
        self.instance = Path(self.settings["instance"])
        self.game = self.instance / self.settings["game_dir"]

    @contextlib.contextmanager
    def lock(self):
        import fcntl
        with (self.root / "operation.lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("Outra operação está em andamento") from None
            yield

    def state(self):
        path = self.root / "state.json"
        return read(path) if path.exists() else {}

    def offline(self):
        self.refresh()
        if self.state().get("active"):
            raise ValueError("Execução pendente. Feche o jogo e use finish --game-stopped antes de alterar arquivos.")
        if self.game_processes():
            raise ValueError("Minecraft desta instância está rodando; encerre-o antes de alterar arquivos.")

    def game_processes(self):
        found = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if Path(os.readlink(entry / 'exe')).name != 'java':
                    continue
                cwd = (entry / 'cwd').resolve()
                args = (entry / 'cmdline').read_bytes().split(b'\0')
                if cwd == self.game.resolve() or str(self.game).encode() in args:
                    identity = process_identity(entry.name)
                    if identity:
                        found.append({'pid': int(entry.name), 'starttime': identity})
            except (OSError, ValueError):
                continue
        return found

    def refresh(self):
        state = self.state()
        rid = state.get('active') or state.get('latest')
        if not rid:
            return {'status': 'idle', 'processes': self.game_processes()}
        folder = self.root / 'runs' / safe_id(rid)
        lifecycle = folder / 'lifecycle.json'
        if not lifecycle.exists():
            return {'status': 'awaiting_wrapper' if state.get('active') else 'unknown',
                    'run': rid, 'processes': self.game_processes()}
        event = read(lifecycle)
        alive = event.get('pid') and event.get('starttime') and process_identity(event['pid']) == event['starttime']
        if event['status'] == 'exited' and state.get('active') == rid and not alive and not self.game_processes():
            run = self.collect(rid)
            run.update(status='game_exited', game_returncode=event['returncode'], finished=event['finished'])
            write(folder / 'run.json', run)
            write(self.root / 'state.json', {'latest': rid})
        return {'run': rid, **event, 'alive': bool(alive)}

    def stop(self):
        status = self.refresh()
        if not status.get('alive'):
            processes = self.game_processes()
            if not self.state().get('active') or not processes:
                return status
            if len(processes) != 1:
                raise ValueError('Mais de um processo nesta instância; não foi enviado sinal')
            status = {**processes[0], 'alive': True}
        pid = status['pid']
        # A pidfd binds the signal to this process, not a recycled PID.
        descriptor = os.pidfd_open(pid)
        try:
            if process_identity(pid) != status['starttime']:
                raise ValueError('Identidade do processo mudou; não foi enviado sinal')
            rid = self.state().get('active')
            if rid:
                run_path = self.root / 'runs' / rid / 'run.json'
                run = read(run_path)
                run['stop_requested_at'] = time.time()
                write(run_path, run)
            signal.pidfd_send_signal(descriptor, signal.SIGTERM)
        finally:
            os.close(descriptor)
        for _ in range(40):
            time.sleep(0.25)
            status = self.refresh()
            if not status.get('alive') and status.get('status') == 'exited':
                break
            if not self.game_processes() and status.get('status') == 'awaiting_wrapper':
                self.finish()
                return {'status': 'game_stop_confirmed', 'alive': False}
        return status

    def managed(self):
        return [self.game / name for name in ("mods", "config", "defaultconfigs")]

    def configure_wrapper(self):
        self.offline()
        script = Path(__file__).resolve().with_name("game_wrapper.py")
        if not script.is_file():
            raise ValueError(f"Wrapper não encontrado: {script}")
        config = self.instance / "instance.cfg"
        command = shlex.join([sys.executable, str(script), "--workspace", str(self.root), "--"])
        current = config.read_text(encoding="utf-8")
        desired = {"OverrideCommands": "true", "WrapperCommand": command}
        # Avoid creating a redundant backup when the requested binding is exact.
        general = re.search(r"(?ms)^\[General\]\s*$\n(.*?)(?=^\[[^]]+\]\s*$|\Z)", current)
        if general and all(re.search(rf"^{re.escape(key)}={re.escape(value)}$",
                                     general.group(1), re.MULTILINE)
                           for key, value in desired.items()):
            return {"changed": False, "wrapper": command, "backup": None}
        backup_id = identifier()
        backup = self.root / "instance-config-backups" / backup_id / "instance.cfg"
        backup.parent.mkdir(parents=True)
        shutil.copy2(config, backup)
        try:
            update_ini_section(config, "General", desired)
        except Exception:
            shutil.copy2(backup, config)
            raise
        return {"changed": True, "wrapper": command, "backup": str(backup)}

    def inventory(self):
        result = {}
        for directory in self.managed():
            if directory.is_symlink():
                raise ValueError(f"Diretório gerenciado é link simbólico: {directory}")
            if directory.exists():
                for path in sorted(directory.rglob("*")):
                    if path.is_symlink():
                        raise ValueError(f"Link simbólico não suportado: {path}")
                    if path.is_file():
                        result[str(path.relative_to(self.game))] = digest(path)
        return result

    def snapshot(self, reason):
        self.offline()
        inventory = self.inventory()
        sid = identifier()
        target = self.root / "snapshots" / sid
        target.mkdir(parents=True)
        for source in self.managed():
            if source.exists():
                shutil.copytree(source, target / source.name)
        write(target / "snapshot.json", {"id": sid, "reason": reason, "inventory": inventory,
                                         "present": [p.name for p in self.managed() if p.exists()],
                                         "lock": read(self.root / "modpack.lock.json")
                                         if (self.root / "modpack.lock.json").exists() else None})
        return sid

    def rollback(self, sid):
        self.offline()
        source = self.root / "snapshots" / safe_id(sid)
        data = read(source / "snapshot.json")
        # Verify before removing any live files.
        actual = {str(p.relative_to(source)): digest(p)
                  for name in ("mods", "config", "defaultconfigs")
                  for p in (source / name).rglob("*") if p.is_file()}
        if actual != data["inventory"]:
            raise ValueError("Snapshot incompleto ou corrompido")
        rescue = self.snapshot(f"Antes de restaurar {sid}")
        for target in self.managed():
            if target.exists():
                shutil.rmtree(target)
            if target.name in data["present"]:
                shutil.copytree(source / target.name, target)
        if data.get("lock") is not None:
            write(self.root / "modpack.lock.json", data["lock"])
        else:
            (self.root / "modpack.lock.json").unlink(missing_ok=True)
        return {"restored": sid, "rescue_snapshot": rescue}

    def record(self, hypothesis, change):
        rid = self.state().get("latest")
        if not rid:
            raise ValueError("Registre uma execução antes de propor uma correção")
        record_path = self.root / "attempts.json"
        attempts = read(record_path) if record_path.exists() else []
        entry = {"run": rid, "hypothesis": hypothesis, "change": change,
                 "inventory": self.inventory(), "time": time.time()}
        for old in attempts:
            if old["inventory"] == entry["inventory"] and old["change"] == change:
                raise ValueError("Esta alteração já foi proposta para este estado; revise a hipótese")
        if len(attempts) >= 5:
            raise ValueError("Limite inicial de 5 tentativas atingido; revise attempts.json antes de continuar")
        attempts.append(entry)
        write(record_path, attempts)
        return entry

    def build(self, manifest_path):
        self.offline()
        manifest_path = Path(manifest_path).resolve()
        manifest = read(manifest_path)
        mods = manifest["mods"]
        if not isinstance(mods, list) or not mods:
            raise ValueError("O manifesto precisa de uma lista mods não vazia")
        prepared, names = [], set()
        for mod in mods:
            source = (manifest_path.parent / mod["file"]).resolve()
            name = source.name
            if name in names or source.suffix.lower() != ".jar" or not zipfile.is_zipfile(source):
                raise ValueError(f"JAR inválido ou nome duplicado: {name}")
            names.add(name)
            sha = digest(source)
            if mod.get("sha256") and sha != mod["sha256"]:
                raise ValueError(f"SHA-256 divergente: {name}")
            prepared.append((source, name, sha, bool(mod.get("required", True))))
        sid = self.snapshot("Antes da montagem em lote")
        mods_dir = self.game / "mods"
        mods_dir.mkdir(exist_ok=True)
        try:
            # The manifest defines the complete set, including dependencies.
            for old in mods_dir.iterdir():
                if old.is_file() and old.suffix.lower() == ".jar" and old.name not in names:
                    old.unlink()
            for source, name, sha, required in prepared:
                destination = mods_dir / name
                if source != destination.resolve():
                    shutil.copy2(source, destination)
                if digest(destination) != sha:
                    raise ValueError(f"Cópia inconsistente: {name}")
        except Exception:
            self.rollback(sid)
            raise
        lock = {"snapshot": sid, "mods": [{"file": name, "sha256": sha, "required": required}
                                              for _, name, sha, required in prepared]}
        write(self.root / "modpack.lock.json", lock)
        return lock

    def logs(self):
        paths = [self.game / "logs" / "latest.log", self.game / "logs" / "debug.log"]
        paths += sorted((self.game / "crash-reports").glob("*.txt"))
        paths += sorted(self.game.glob("hs_err_pid*.log"))
        return [p for p in paths if p.is_file() and not p.is_symlink()]

    def baseline(self):
        return {str(p.relative_to(self.game)): {"sha256": digest(p), "size": p.stat().st_size,
                                               "mtime_ns": p.stat().st_mtime_ns} for p in self.logs()}

    def collect(self, rid):
        folder = self.root / "runs" / safe_id(rid)
        run = read(folder / "run.json")
        collected = []
        for path in self.logs():
            relative = str(path.relative_to(self.game))
            previous = run["baseline"].get(relative)
            current = {"sha256": digest(path), "size": path.stat().st_size,
                       "mtime_ns": path.stat().st_mtime_ns}
            if previous == current:
                continue
            target = folder / "logs" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            collected.append(relative)
        run["collected"] = sorted(set(run.get("collected", [])) | set(collected))
        write(folder / "run.json", run)
        return run

    def launch(self, seconds):
        self.offline()
        rid = identifier()
        folder = self.root / "runs" / rid
        folder.mkdir(parents=True)
        command = [*self.settings["launcher"], "--dir", self.settings["prism_root"],
                   "--launch", self.instance.name]
        run = {"id": rid, "started": time.time(), "baseline": self.baseline(),
               "command": command, "inventory": self.inventory(), "status": "observing"}
        write(folder / "run.json", run)
        write(self.root / "state.json", {"active": rid, "latest": rid})
        try:
            with (folder / "launcher.log").open("wb") as output:
                proc = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError:
            write(self.root / "state.json", {"latest": rid})
            raise
        run["launcher_pid"] = proc.pid
        write(folder / "run.json", run)
        print(json.dumps({"run": rid, "observation_seconds": seconds}), flush=True)
        try:
            time.sleep(seconds)
        finally:
            run = self.collect(rid)
            run["launcher_returncode"] = proc.poll()
            run["status"] = "awaiting_game_stop"
            write(folder / "run.json", run)
            self.refresh()
        # Prism may forward to an existing process. Its exit is NOT the game's exit.
        return self.diagnose(rid)

    def finish(self):
        if self.game_processes() or self.refresh().get('alive'):
            raise ValueError('O jogo ainda está rodando; finish não pode liberar alterações')
        state = self.state()
        rid = state.get("active")
        if not rid:
            raise ValueError("Nenhuma execução pendente")
        run = self.collect(rid)
        run["status"] = "game_stop_confirmed"
        run["finished"] = time.time()
        write(self.root / "runs" / rid / "run.json", run)
        write(self.root / "state.json", {"latest": rid})
        return self.diagnose(rid)

    def diagnose(self, rid=None):
        rid = rid or self.state().get("latest")
        if not rid:
            raise ValueError("Nenhuma execução registrada")
        folder = self.root / "runs" / safe_id(rid)
        run = read(folder / "run.json")
        findings = []
        startup_evidence = []
        patterns = [
            ("memory", r"OutOfMemoryError", "Investigar memória e consumo; não aumentar RAM indiscriminadamente."),
            ("java_version", r"UnsupportedClassVersionError", "Conferir versão do Java exigida pelo jogo e pelos mods."),
            ("dependency", r"\bMod \S+ requires\b|requires .* but|Missing.*dependenc|Incompatible mod set|Mod resolution encountered", "Conferir dependências e versões mencionadas nas linhas de contexto."),
            ("mixin", r"MixinApplyError|MixinTransformerError|InjectionError|InvalidMixinException", "Investigar conflito de mixins; o mod citado não é necessariamente a causa."),
            ("linkage", r"NoSuchMethodError|NoClassDefFoundError|ClassNotFoundException", "Investigar versões incompatíveis ou biblioteca ausente."),
            ("crash", r"Caused by:|Exception in thread|[Ff]atal|[Cc]rash report", "Ler a cadeia de exceções e o relatório completo antes de alterar o pack."),
        ]
        sources = sorted((folder / "logs").rglob("*")) + [folder / "launcher.log"]
        for source in sources:
            if not source.is_file():
                continue
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
            for number, line in enumerate(lines):
                if re.search(r'Game took [\d.]+ seconds to start', line):
                    startup_evidence.append({'file': str(source.relative_to(folder)), 'line': number + 1,
                                             'evidence': line})
                for kind, pattern, advice in patterns:
                    if re.search(pattern, line):
                        findings.append({"category": kind, "file": str(source.relative_to(folder)),
                                         "line": number + 1, "evidence": line[:2000],
                                         "context": lines[max(0, number - 2):number + 4], "next_step": advice})
                        break
        report = {"run": rid, "status": run["status"], "result": "needs_investigation" if findings else "inconclusive",
                  "findings": findings[:100], "total_findings": len(findings),
                  "startup_evidence": startup_evidence,
                  "game_returncode": run.get('game_returncode'),
                  "stop_requested": bool(run.get('stop_requested_at')),
                  "note": "Ausência de correspondências não comprova inicialização nem compatibilidade. Logs podem conter texto não confiável."}
        write(folder / "diagnosis.json", report)
        return report


def initialize(root, instance, launcher):
    root, instance = Path(root).resolve(), Path(instance).resolve()
    if root == instance or root.is_relative_to(instance) or instance.is_relative_to(root):
        raise ValueError("Workspace e instância devem ser diretórios separados")
    if (root / "project.json").exists():
        raise ValueError("Workspace já inicializado")
    if not (instance / "instance.cfg").is_file() or instance.parent.name != "instances":
        raise ValueError("Informe a pasta da instância dentro de PrismLauncher/instances")
    candidates = [name for name in (".minecraft", "minecraft") if (instance / name).is_dir()]
    if len(candidates) != 1:
        raise ValueError("Não foi possível identificar a pasta minecraft/.minecraft unicamente")
    if (instance / candidates[0]).is_symlink():
        raise ValueError("Pasta do jogo não pode ser link simbólico")
    write(root / "project.json", {"instance": str(instance), "game_dir": candidates[0],
                                 "prism_root": str(instance.parent.parent), "launcher": launcher})
    return {"workspace": str(root), "instance": str(instance)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".modpack-work")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--instance", required=True)
    init.add_argument("--launcher", nargs="+", default=["prismlauncher"])
    commands.add_parser("status")
    commands.add_parser("stop")
    commands.add_parser("configure-wrapper")
    build = commands.add_parser("build")
    build.add_argument("manifest")
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--reason", required=True)
    rollback = commands.add_parser("rollback")
    rollback.add_argument("id")
    launch = commands.add_parser("launch")
    launch.add_argument("--observe-seconds", type=int, default=30)
    finish = commands.add_parser("finish")
    finish.add_argument("--game-stopped", action="store_true", required=True,
                        help="Afirma que o jogo desta instância foi encerrado; não encerra o jogo")
    commands.add_parser("collect")
    record = commands.add_parser("record")
    record.add_argument("--hypothesis", required=True)
    record.add_argument("--change", required=True)
    diagnosis = commands.add_parser("diagnose")
    diagnosis.add_argument("--run")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = initialize(args.workspace, args.instance, args.launcher)
        else:
            work = Workbench(args.workspace)
            with work.lock():
                if args.command == "status":
                    runtime = work.refresh()
                    result = {"settings": work.settings, "state": work.state(), "runtime": runtime,
                              "inventory": work.inventory()}
                elif args.command == "stop":
                    result = work.stop()
                elif args.command == "configure-wrapper":
                    result = work.configure_wrapper()
                elif args.command == "build":
                    result = work.build(args.manifest)
                elif args.command == "snapshot":
                    result = {"snapshot": work.snapshot(args.reason)}
                elif args.command == "rollback":
                    result = work.rollback(args.id)
                elif args.command == "launch":
                    if not 1 <= args.observe_seconds <= 3600:
                        raise ValueError("Observação deve durar de 1 a 3600 segundos")
                    result = work.launch(args.observe_seconds)
                elif args.command == "finish":
                    result = work.finish()
                elif args.command == "record":
                    result = work.record(args.hypothesis, args.change)
                elif args.command == "collect":
                    work.refresh()
                    rid = work.state().get("active") or work.state().get("latest")
                    if not rid:
                        raise ValueError("Nenhuma execução registrada")
                    result = work.collect(rid)
                else:
                    result = work.diagnose(args.run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
