#!/usr/bin/env python3
"""Prism WrapperCommand. Never persist Java arguments or account tokens."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

from modpack import Workbench, identifier, process_identity, write, safe_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        raise ValueError('Prism não forneceu o comando Java')
    work = Workbench(args.workspace)
    if Path.cwd().resolve() != work.game.resolve():
        raise ValueError('Diretório de trabalho diferente da instância gerenciada')
    with (work.root / 'game.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rid = work.state().get('active')
        if not rid:
            with work.lock():
                work.offline()
                rid = identifier()
                write(work.root / 'runs' / rid / 'run.json', {
                    'id': rid, 'started': time.time(), 'baseline': work.baseline(),
                    'inventory': work.inventory(), 'status': 'manual_launch'})
                write(work.root / 'state.json', {'active': rid, 'latest': rid})
        folder = work.root / 'runs' / safe_id(rid)
        event = {'status': 'starting', 'wrapper_pid': os.getpid(), 'started': time.time()}
        write(folder / 'lifecycle.json', event)
        try:
            child = subprocess.Popen(command)
            event.update(status='running', pid=child.pid, starttime=process_identity(child.pid))
            write(folder / 'lifecycle.json', event)
            code = child.wait()
        except OSError:
            code = 127
        event.update(status='exited', returncode=code, finished=time.time())
        write(folder / 'lifecycle.json', event)
        return code if code >= 0 else 128 - code


if __name__ == '__main__':
    sys.exit(main())
