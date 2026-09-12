# DSH configuration restore

This repository is a declarative snapshot of the local DSH/Codex setup. It
keeps profiles, presets, skills, custom plugins, bridges and relevant text
configuration. It deliberately does not keep sessions, conversation history,
caches, browser state or credentials. Workspace definitions are retained with
their session associations removed.

The current snapshot targets DSH `0.1.2-rc.1`, Node `>=22` and pnpm `11.26.0`.
The DSH and pnpm runtime versions are installed from the committed
`runtime/package-lock.json`.

## Restore

Close DSH first, then run from the repository root:

```bash
./restore-dsh.sh restore
```

The script will:

1. install the locked DSH and pnpm runtime if necessary;
2. expose that runtime as `~/.local/bin/dsh`;
3. restore `~/.dsh` and the selected `~/.codex` files;
4. reinstall every saved profile with its lockfile;
5. validate each profile with `dsh --profile <name> --dump-config`.

Existing managed paths are moved to
`~/.dsh-restore-backups/<timestamp>/` before replacement. No existing session
or history database is used by the restore.

After restoration, authenticate again and provide any values listed in
`secrets/required-env.example` through an external secret store or environment
variables. Local LM Studio models and other external applications are also
prerequisites; their model files are not Git artifacts.

## Snapshot and verification

To refresh the repository from the currently installed setup:

```bash
./restore-dsh.sh snapshot
```

To validate the installed setup without changing configuration:

```bash
./restore-dsh.sh verify
```

The snapshot command uses an explicit allowlist and replaces machine-specific
home paths with markers. It does not copy `~/.dsh/secrets`, auth files, browser
profiles, sessions, history or package-manager caches.

This repository has no remote configured by default. Add a private remote only
after reviewing the snapshot and confirming that no secret values are present.
