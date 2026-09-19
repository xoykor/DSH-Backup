#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# DSH configuration snapshot/restore tool.
#
# The repository is the source of truth for portable configuration. Runtime
# state, sessions, caches and credentials remain outside it by design.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR"
MANIFEST="$REPO_DIR/manifest.yaml"

DSH_HOME="${DSH_HOME:-${HOME:?HOME is not set}/.dsh}"
CODEX_HOME="${CODEX_HOME:-${HOME:?HOME is not set}/.codex}"
DSH_INSTALL_PREFIX="${DSH_INSTALL_PREFIX:-${HOME:?HOME is not set}/.local}"

DSH_PACKAGE=""
DSH_VERSION=""
NODE_REQUIREMENT=""
PNPM_VERSION=""
RUNTIME_LOCKFILE=""
DSH_BIN=""
PNPM_BIN=""
RESTORE_BACKUP_ROOT=""

log() { printf '[dsh-restore] %s\n' "$*"; }
warn() { printf '[dsh-restore] warning: %s\n' "$*" >&2; }
die() { printf '[dsh-restore] error: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: ./restore-dsh.sh <command>

Commands:
  snapshot  Capture the current portable DSH/Codex configuration into this repo.
  restore   Install the pinned runtime, restore configuration, and verify it.
  verify    Validate the installed runtime and saved profiles without writing.
  help      Show this help.

Environment overrides:
  DSH_HOME, CODEX_HOME, DSH_INSTALL_PREFIX
EOF
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

yaml_scalar() {
  local key="$1"
  sed -n -E "s/^${key}:[[:space:]]*//p" "$MANIFEST" \
    | sed -E 's/^"//; s/"$//' \
    | head -n 1
}

read_manifest() {
  [[ -f "$MANIFEST" ]] || die "manifest not found: $MANIFEST"
  DSH_PACKAGE="$(yaml_scalar dshPackage)"
  DSH_VERSION="$(yaml_scalar dshVersion)"
  NODE_REQUIREMENT="$(yaml_scalar nodeRequirement)"
  PNPM_VERSION="$(yaml_scalar pnpmVersion)"
  RUNTIME_LOCKFILE="$(yaml_scalar runtimeLockfile)"
  [[ -n "$DSH_PACKAGE" && -n "$DSH_VERSION" && -n "$PNPM_VERSION" && -n "$RUNTIME_LOCKFILE" ]] \
    || die "manifest is missing a runtime value"
}

sed_escape() {
  printf '%s' "$1" | sed 's/[&|\\]/\\&/g'
}

sed_pattern_escape() {
  printf '%s' "$1" | sed -e 's/[.[\*^$\\]/\\&/g' -e 's/|/\\|/g'
}

is_text_path() {
  case "$1" in
    *.yml|*.yaml|*.json|*.toml|*.md|*.txt|*.js|*.mjs|*.cjs|*.ts|*.tsx|*.py|*.sh|*.rules|*.patch)
      return 0 ;;
    *)  return 1 ;;
  esac
}

snapshot_text() {
  local src="$1"
  local dst="$2"
  [[ -f "$src" ]] || { warn "not found, skipped: $src"; return 0; }
  mkdir -p "$(dirname -- "$dst")"

  local dsh_marker codex_marker home_marker
  dsh_marker="$(sed_pattern_escape "$DSH_HOME")"
  codex_marker="$(sed_pattern_escape "$CODEX_HOME")"
  home_marker="$(sed_pattern_escape "$HOME")"

  sed \
    -e "s|${dsh_marker}|__DSH_HOME__|g" \
    -e "s|${codex_marker}|__CODEX_HOME__|g" \
    -e "s|${home_marker}|__HOME__|g" \
    "$src" > "$dst"
  chmod --reference="$src" "$dst" 2>/dev/null || true
}

materialize_text() {
  local src="$1"
  local dst="$2"
  [[ -f "$src" ]] || die "saved file not found: $src"
  mkdir -p "$(dirname -- "$dst")"

  local dsh_value codex_value home_value tmp
  dsh_value="$(sed_escape "$DSH_HOME")"
  codex_value="$(sed_escape "$CODEX_HOME")"
  home_value="$(sed_escape "$HOME")"
  tmp="$(mktemp "${dst}.tmp.XXXXXX")"
  if sed \
    -e "s|__DSH_HOME__|${dsh_value}|g" \
    -e "s|__CODEX_HOME__|${codex_value}|g" \
    -e "s|__HOME__|${home_value}|g" \
    "$src" > "$tmp"; then
    chmod --reference="$src" "$tmp" 2>/dev/null || true
    mv -- "$tmp" "$dst"
  else
    rm -f -- "$tmp"
    return 1
  fi
}

sanitize_tree_in_place() {
  local root="$1"
  [[ -d "$root" ]] || return 0
  while IFS= read -r -d '' file; do
    if is_text_path "$file"; then
      local tmp
      tmp="$(mktemp "${file}.tmp.XXXXXX")"
      if sed \
        -e "s|$(sed_pattern_escape "$DSH_HOME")|__DSH_HOME__|g" \
        -e "s|$(sed_pattern_escape "$CODEX_HOME")|__CODEX_HOME__|g" \
        -e "s|$(sed_pattern_escape "$HOME")|__HOME__|g" \
        "$file" > "$tmp"; then
        chmod --reference="$file" "$tmp" 2>/dev/null || true
        mv -- "$tmp" "$file"
      else
        rm -f -- "$tmp"
        return 1
      fi
    fi
  done < <(find "$root" -type f -print0)
}

materialize_tree_in_place() {
  local root="$1"
  [[ -d "$root" ]] || return 0
  while IFS= read -r -d '' file; do
    if is_text_path "$file"; then
      local tmp
      tmp="$(mktemp "${file}.tmp.XXXXXX")"
      if sed \
        -e "s|__DSH_HOME__|$(sed_escape "$DSH_HOME")|g" \
        -e "s|__CODEX_HOME__|$(sed_escape "$CODEX_HOME")|g" \
        -e "s|__HOME__|$(sed_escape "$HOME")|g" \
        "$file" > "$tmp"; then
        chmod --reference="$file" "$tmp" 2>/dev/null || true
        mv -- "$tmp" "$file"
      else
        rm -f -- "$tmp"
        return 1
      fi
    fi
  done < <(find "$root" -type f -print0)
}

copy_tree_snapshot() {
  local src="$1"
  local dst="$2"
  [[ -d "$src" ]] || { warn "not found, skipped: $src"; return 0; }
  mkdir -p "$dst"
  tar -C "$src" -cf - \
    --exclude='./.git' \
    --exclude='./.git/*' \
    --exclude='*/.git' \
    --exclude='*/.git/*' \
    --exclude='*/node_modules' \
    --exclude='*/node_modules/*' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='auth.json' \
    --exclude='auth.*.json' \
    --exclude='credentials*' \
    --exclude='*/__pycache__' \
    --exclude='*/__pycache__/*' \
    --exclude='*.pyc' \
    --exclude='*.jsonl' \
    . | tar -C "$dst" -xf -
  sanitize_tree_in_place "$dst"
}

copy_tree_restore() {
  local src="$1"
  local dst="$2"
  [[ -d "$src" ]] || die "saved directory not found: $src"
  mkdir -p "$dst"
  tar -C "$src" -cf - \
    --exclude='./.git' \
    --exclude='./.git/*' \
    --exclude='*/.git' \
    --exclude='*/.git/*' \
    --exclude='*/node_modules' \
    --exclude='*/node_modules/*' \
    . | tar -C "$dst" -xf -
  materialize_tree_in_place "$dst"
}

reset_repo_area() {
  local target="$1"
  case "$target" in
    "$REPO_DIR/dsh"|"$REPO_DIR/codex") ;;
    *) die "refusing to reset path outside snapshot areas: $target" ;;
  esac
  rm -rf -- "$target"
  mkdir -p "$target"
}

snapshot_profiles() {
  local src_root="$DSH_HOME/profiles"
  local dst_root="$REPO_DIR/dsh/profiles"
  [[ -d "$src_root" ]] || { warn "not found, skipped: $src_root"; return 0; }
  mkdir -p "$dst_root"

  while IFS= read -r -d '' profile; do
    local name dst file base
    name="$(basename -- "$profile")"
    [[ "$name" == "node_modules" ]] && continue
    dst="$dst_root/$name"
    mkdir -p "$dst"
    while IFS= read -r -d '' file; do
      base="$(basename -- "$file")"
      case "$base" in
        .env|.env.*|auth.json|auth.*.json|credentials*) continue ;;
      esac
      snapshot_text "$file" "$dst/$base"
    done < <(find "$profile" -mindepth 1 -maxdepth 1 -type f -print0)
    # Some profiles contain local bundle artifacts referenced by package.json.
    # They are configuration source, not generated node_modules, and must be
    # included so a restore does not leave file: dependencies dangling.
    if [[ -d "$profile/.dsh-artifacts" ]]; then
      copy_tree_snapshot "$profile/.dsh-artifacts" "$dst/.dsh-artifacts"
    fi
  done < <(find "$src_root" -mindepth 1 -maxdepth 1 -type d -print0)
}

snapshot_workspace() {
  local src="$1"
  local dst="$2"
  [[ -f "$src" ]] || { warn "not found, skipped: $src"; return 0; }
  local tmp
  tmp="$(mktemp)"
  node - "$src" > "$tmp" <<'NODE'
const fs = require('node:fs');
const source = process.argv[2];
const value = JSON.parse(fs.readFileSync(source, 'utf8'));

if (value.global && Array.isArray(value.global.archivedSessionIds)) {
  value.global.archivedSessionIds = [];
}
const workspaces = value.tables?.workspaces ?? {};
for (const workspace of Object.values(workspaces)) {
  if (workspace && typeof workspace === 'object') workspace.sessionIds = [];
}
process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
NODE
  snapshot_text "$tmp" "$dst"
  rm -f -- "$tmp"
}

snapshot_codex_skills() {
  local src_root="$CODEX_HOME/skills"
  local dst_root="$REPO_DIR/codex/skills"
  [[ -d "$src_root" ]] || { warn "not found, skipped: $src_root"; return 0; }
  mkdir -p "$dst_root"
  while IFS= read -r -d '' skill; do
    [[ "$(basename -- "$skill")" == ".system" ]] && continue
    copy_tree_snapshot "$skill" "$dst_root/$(basename -- "$skill")"
  done < <(find "$src_root" -mindepth 1 -maxdepth 1 -type d -print0)
}

snapshot_current() {
  read_manifest
  require_command find
  require_command node
  require_command sed
  require_command tar
  reset_repo_area "$REPO_DIR/dsh"
  reset_repo_area "$REPO_DIR/codex"

  snapshot_text "$DSH_HOME/settings.yaml" "$REPO_DIR/dsh/settings.yaml"
  snapshot_text "$DSH_HOME/cordis.patch.yml" "$REPO_DIR/dsh/cordis.patch.yml"
  snapshot_text "$DSH_HOME/AGENTS.md" "$REPO_DIR/dsh/AGENTS.md"
  snapshot_workspace "$DSH_HOME/storages/workspace.json" "$REPO_DIR/dsh/workspace.json"
  copy_tree_snapshot "$DSH_HOME/.agent-presets" "$REPO_DIR/dsh/presets"
  copy_tree_snapshot "$DSH_HOME/skills" "$REPO_DIR/dsh/skills"
  copy_tree_snapshot "$DSH_HOME/plugins" "$REPO_DIR/dsh/plugins"
  copy_tree_snapshot "$DSH_HOME/bridges" "$REPO_DIR/dsh/bridges"
  snapshot_profiles

  snapshot_text "$CODEX_HOME/config.toml" "$REPO_DIR/codex/config.toml.template"
  snapshot_text "$CODEX_HOME/computer-use/config.json" "$REPO_DIR/codex/computer-use/config.json"
  copy_tree_snapshot "$CODEX_HOME/rules" "$REPO_DIR/codex/rules"
  snapshot_codex_skills
  copy_tree_snapshot "$CODEX_HOME/plugins/cache/personal" "$REPO_DIR/codex/plugins/personal"

  log "snapshot complete: $REPO_DIR"
  log "credentials, sessions, history, caches and node_modules were excluded"
}

check_node() {
  require_command node
  local major
  major="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "$major" =~ ^[0-9]+$ ]] || die "could not determine Node.js version"
  (( major >= 22 )) || die "Node.js ${NODE_REQUIREMENT} is required; found $(node --version)"
}

check_dsh_stopped() {
  local running
  running="$(ps -eo pid=,args= | awk -v self="$$" '$1 != self && ($0 ~ /\/dsh( |$)/ || $0 ~ /\/dsh\.js( |$)/)')"
  [[ -z "$running" ]] || die "DSH is running; close it before restore:\n$running"
}

ensure_pnpm() {
  [[ -x "${PNPM_BIN:-}" ]] || die "locked runtime did not provide pnpm"
  local actual
  actual="$("$PNPM_BIN" --version)"
  [[ "$actual" == "$PNPM_VERSION" ]] \
    || die "expected pnpm $PNPM_VERSION, found $actual"
  export PATH="$(dirname -- "$PNPM_BIN"):$DSH_INSTALL_PREFIX/bin:$PATH"
}

runtime_job_observation_patch() {
  local target
  target="$(node --input-type=module -e 'import { createRequire } from "node:module"; import { realpathSync } from "node:fs"; process.stdout.write(createRequire(realpathSync(process.argv[1])).resolve("@deepseek-ai/dsh-tool-jobs"));' "$DSH_BIN")"
  node "$REPO_DIR/runtime/patches/job-observation/apply-job-observation.mjs" --target "$target" "$@"
}

runtime_checkpoint_compaction_patch() {
  local target
  target="$(node --input-type=module -e 'import { createRequire } from "node:module"; import { realpathSync } from "node:fs"; process.stdout.write(createRequire(realpathSync(process.argv[1])).resolve("@deepseek-ai/dsh-compaction-basic"));' "$DSH_BIN")"
  node "$REPO_DIR/runtime/patches/checkpoint-compaction/apply-checkpoint-compaction.mjs" --target "$target" "$@"
}

runtime_goal_round_compaction_patch() {
  local target
  target="$(node --input-type=module -e 'import { createRequire } from "node:module"; import { realpathSync } from "node:fs"; process.stdout.write(createRequire(realpathSync(process.argv[1])).resolve("@deepseek-ai/dsh-goal-round-driver"));' "$DSH_BIN")"
  node "$REPO_DIR/runtime/patches/goal-round-compaction/apply-goal-round-compaction.mjs" --target "$target" "$@"
}

runtime_compaction_progress_patch() {
  local target
  target="$(node --input-type=module -e 'import { createRequire } from "node:module"; import { realpathSync } from "node:fs"; import { dirname, join } from "node:path"; process.stdout.write(join(dirname(createRequire(realpathSync(process.argv[1])).resolve("@deepseek-ai/dsh-client-ui-chat/package.json")), "lib/client.js"));' "$DSH_BIN")"
  node "$REPO_DIR/runtime/patches/compaction-progress/apply-compaction-progress.mjs" --target "$target" "$@"
}

runtime_local_http_timeout_patch() {
  local target
  target="$(node --input-type=module -e 'import { createRequire } from "node:module"; import { realpathSync } from "node:fs"; process.stdout.write(createRequire(realpathSync(process.argv[1])).resolve("@deepseek-ai/dsh-llm-pi-ai"));' "$DSH_BIN")"
  node "$REPO_DIR/runtime/patches/local-http-timeout/apply-local-http-timeout.mjs" --target "$target" "$@"
}

ensure_dsh_runtime() {
  local runtime_template="$REPO_DIR/runtime"
  local lockfile="$REPO_DIR/$RUNTIME_LOCKFILE"
  [[ -f "$runtime_template/package.json" ]] \
    || die "runtime package manifest not found: $runtime_template/package.json"
  [[ -f "$lockfile" ]] || die "runtime lockfile not found: $lockfile"

  local runtime_root="$DSH_INSTALL_PREFIX/lib/dsh-runtime-$DSH_VERSION"
  local runtime_dsh="$runtime_root/node_modules/.bin/dsh"
  local runtime_pnpm="$runtime_root/node_modules/.bin/pnpm"
  local actual=""
  if [[ -x "$runtime_dsh" ]]; then
    actual="$("$runtime_dsh" --version 2>/dev/null || true)"
  fi

  if [[ "$actual" != "$DSH_VERSION" || ! -x "$runtime_pnpm" ]]; then
    log "installing locked DSH runtime ($DSH_PACKAGE@$DSH_VERSION, pnpm@$PNPM_VERSION)"
    local runtime_parent stage
    runtime_parent="$DSH_INSTALL_PREFIX/lib"
    mkdir -p "$runtime_parent"
    stage="$(mktemp -d "$runtime_parent/dsh-runtime-stage.XXXXXX")"
    cp -- "$runtime_template/package.json" "$stage/package.json"
    cp -- "$lockfile" "$stage/package-lock.json"

    npm ci --prefix "$stage" --no-fund --no-audit
    [[ -x "$stage/node_modules/.bin/dsh" ]] \
      || die "locked runtime installation did not provide dsh"
    actual="$("$stage/node_modules/.bin/dsh" --version 2>/dev/null || true)"
    [[ "$actual" == "$DSH_VERSION" ]] \
      || die "locked runtime installed DSH ${actual:-unavailable}, expected $DSH_VERSION"

    if [[ -e "$runtime_root" || -L "$runtime_root" ]]; then
      mv -- "$runtime_root" "$runtime_root.previous-$(date +%Y%m%d-%H%M%S)"
    fi
    mv -- "$stage" "$runtime_root"
  fi

  DSH_BIN="$runtime_root/node_modules/.bin/dsh"
  PNPM_BIN="$runtime_root/node_modules/.bin/pnpm"
  [[ -x "$DSH_BIN" ]] || die "DSH executable not found in locked runtime: $DSH_BIN"
  [[ -x "$PNPM_BIN" ]] || die "pnpm executable not found in locked runtime: $PNPM_BIN"

  runtime_job_observation_patch
  runtime_checkpoint_compaction_patch
  runtime_goal_round_compaction_patch
  runtime_compaction_progress_patch
  runtime_local_http_timeout_patch

  mkdir -p "$DSH_INSTALL_PREFIX/bin"
  ln -sfn -- "$DSH_BIN" "$DSH_INSTALL_PREFIX/bin/dsh"
  export PATH="$(dirname -- "$PNPM_BIN"):$DSH_INSTALL_PREFIX/bin:$DSH_INSTALL_PREFIX/node_modules/.bin:$HOME/.local/bin:$PATH"

  [[ -x "$DSH_BIN" ]] || die "DSH executable not found at $DSH_BIN"
  actual="$($DSH_BIN --version 2>/dev/null || true)"
  [[ "$actual" == "$DSH_VERSION" ]] \
    || die "expected DSH $DSH_VERSION, found ${actual:-unavailable}"
}

prepare_restore_backup() {
  RESTORE_BACKUP_ROOT="$HOME/.dsh-restore-backups/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$RESTORE_BACKUP_ROOT"
}

install_desktop_launcher() {
  local applications_dir icon_dir desktop_file icon_src
  applications_dir="$HOME/.local/share/applications"
  icon_dir="$HOME/.local/share/icons/hicolor/scalable/apps"
  desktop_file="$applications_dir/deepseek-harness.desktop"

  mkdir -p "$applications_dir" "$icon_dir"

  icon_src="$(find "$DSH_INSTALL_PREFIX/lib/dsh-runtime-$DSH_VERSION/node_modules" \
    -path '*/@deepseek-ai/dsh-web-frontend/dist/favicon.svg' \
    -type f -print -quit 2>/dev/null || true)"

  if [[ -n "$icon_src" && -f "$icon_src" ]]; then
    cp -- "$icon_src" "$icon_dir/deepseek-harness.svg"
  else
    warn "official DSH favicon not found; launcher will use a generic application icon"
  fi

  cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=DeepSeek Harness
Comment=DeepSeek Harness Web Interface
Exec=$DSH_INSTALL_PREFIX/bin/dsh --profile robust-local
Icon=deepseek-harness
Terminal=false
Categories=Development;Utility;
StartupNotify=true
EOF

  chmod +x "$desktop_file"

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
  fi
  if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
  fi

  log "desktop launcher installed: $desktop_file"
}

stage_existing() {
  local path="$1"
  local relative="$2"
  if [[ -e "$path" || -L "$path" ]]; then
    mkdir -p "$RESTORE_BACKUP_ROOT/$(dirname -- "$relative")"
    mv -- "$path" "$RESTORE_BACKUP_ROOT/$relative"
  fi
}

stage_codex_user_skills() {
  local root="$CODEX_HOME/skills"
  [[ -d "$root" ]] || return 0
  while IFS= read -r -d '' skill; do
    [[ "$(basename -- "$skill")" == ".system" ]] && continue
    stage_existing "$skill" "codex/skills/$(basename -- "$skill")"
  done < <(find "$root" -mindepth 1 -maxdepth 1 -type d -print0)
}

stage_managed_paths() {
  stage_existing "$DSH_HOME/settings.yaml" "dsh/settings.yaml"
  stage_existing "$DSH_HOME/cordis.patch.yml" "dsh/cordis.patch.yml"
  stage_existing "$DSH_HOME/AGENTS.md" "dsh/AGENTS.md"
  stage_existing "$DSH_HOME/storages/workspace.json" "dsh/workspace.json"
  stage_existing "$DSH_HOME/.agent-presets" "dsh/presets"
  stage_existing "$DSH_HOME/skills" "dsh/skills"
  stage_existing "$DSH_HOME/plugins" "dsh/plugins"
  stage_existing "$DSH_HOME/bridges" "dsh/bridges"
  stage_existing "$DSH_HOME/profiles" "dsh/profiles"

  stage_existing "$CODEX_HOME/config.toml" "codex/config.toml"
  stage_existing "$CODEX_HOME/computer-use/config.json" "codex/computer-use/config.json"
  stage_existing "$CODEX_HOME/rules" "codex/rules"
  stage_codex_user_skills
  stage_existing "$CODEX_HOME/plugins/cache/personal" "codex/plugins/personal"
}

restore_profiles() {
  local profile
  while IFS= read -r -d '' profile; do
    [[ -f "$profile/package.json" ]] || continue
    [[ -f "$profile/pnpm-lock.yaml" ]] || die "profile has no lockfile: $profile"
    log "installing profile dependencies: $(basename -- "$profile")"
    (
      cd -- "$profile"
      "$PNPM_BIN" install --frozen-lockfile
    )
  done < <(find "$DSH_HOME/profiles" -mindepth 1 -maxdepth 1 -type d -print0)
}

verify_memory_bundle() {
  local profile profile_dir package_json installed_package out

  for profile in web robust-local; do
    profile_dir="$DSH_HOME/profiles/$profile"
    package_json="$profile_dir/package.json"
    installed_package="$profile_dir/node_modules/dsh-memory/package.json"

    [[ -f "$package_json" ]] || die "$profile package.json is missing"
    [[ -f "$installed_package" ]] || die "dsh-memory is not installed in $profile"

    node - "$profile" "$package_json" "$installed_package" <<'NODE'
const fs = require('node:fs');
const [profileName, profilePath, installedPath] = process.argv.slice(2);
const profile = JSON.parse(fs.readFileSync(profilePath, 'utf8'));
const installed = JSON.parse(fs.readFileSync(installedPath, 'utf8'));

if (installed.version !== '0.7.1') {
  throw new Error(`expected dsh-memory 0.7.1 in ${profileName}, found ${installed.version ?? 'unknown'}`);
}
if (!profile.dsh?.profile?.bundles?.includes('dsh-memory')) {
  throw new Error(`${profileName} does not activate the dsh-memory bundle`);
}
NODE

    (
      cd -- "$profile_dir"
      node --input-type=module -e "import('dsh-memory').then(() => process.stdout.write('dsh-memory import OK\n'))"
    )

    out="$(mktemp)"
    "$DSH_BIN" --profile "$profile" --dump-config > "$out" 2>&1
    grep -q -- "id: memory" "$out" \
      || { tail -n 80 "$out" >&2 || true; rm -f -- "$out"; die "$profile composed config has no memory row"; }
    grep -q -- "name: dsh-memory" "$out" \
      || { tail -n 80 "$out" >&2 || true; rm -f -- "$out"; die "$profile memory row does not load dsh-memory"; }
    rm -f -- "$out"

    log "$profile: dsh-memory v0.7.1 installed and composed"
  done
}

restore_plugins() {
  local plugin has_deps
  while IFS= read -r -d '' plugin; do
    [[ -f "$plugin/package.json" ]] || continue
    has_deps="$(node -e 'const p=require(process.argv[1]); const groups=[p.dependencies,p.optionalDependencies,p.peerDependencies]; process.stdout.write(groups.some((group)=>group&&Object.keys(group).length>0)?"1":"0")' "$plugin/package.json")"
    [[ "$has_deps" == "1" ]] || continue
    log "installing plugin dependencies: $(basename -- "$plugin")"
    (
      cd -- "$plugin"
      if [[ -f package-lock.json ]]; then
        npm ci --legacy-peer-deps --ignore-scripts --no-fund --no-audit
      else
        npm install --legacy-peer-deps --ignore-scripts --no-fund --no-audit
      fi
    )
  done < <(find "$DSH_HOME/plugins" -mindepth 1 -maxdepth 1 -type d -print0)
}

verify_saved_paths() {
  [[ -x "$DSH_BIN" ]] || die "DSH executable is missing: $DSH_BIN"
  [[ -d "$DSH_HOME/profiles" ]] || die "profiles directory is missing: $DSH_HOME/profiles"
  [[ -d "$DSH_HOME/.agent-presets" ]] || die "agent presets directory is missing"
  [[ -d "$DSH_HOME/skills" ]] || die "DSH skills directory is missing"

  local profile out bytes
  while IFS= read -r -d '' profile; do
    local name
    name="$(basename -- "$profile")"
    [[ "$name" == "node_modules" ]] && continue
    out="$(mktemp)"
    if ! "$DSH_BIN" --profile "$name" --dump-config > "$out" 2>&1; then
      warn "dump-config failed for profile $name"
      tail -n 40 "$out" >&2 || true
      rm -f -- "$out"
      return 1
    fi
    bytes="$(wc -c < "$out")"
    rm -f -- "$out"
    log "profile $name: dump-config OK (${bytes} bytes)"
  done < <(find "$DSH_HOME/profiles" -mindepth 1 -maxdepth 1 -type d -print0)
}

verify_current() {
  read_manifest
  require_command find
  require_command ps
  check_node
  export PATH="$DSH_INSTALL_PREFIX/bin:$HOME/.local/bin:$HOME/.local/node_modules/.bin:$PATH"
  DSH_BIN="$DSH_INSTALL_PREFIX/bin/dsh"
  [[ -x "$DSH_BIN" ]] || DSH_BIN="$(command -v dsh || true)"
  [[ -n "$DSH_BIN" && -x "$DSH_BIN" ]] || die "DSH executable not found"
  local actual
  actual="$($DSH_BIN --version 2>/dev/null || true)"
  [[ "$actual" == "$DSH_VERSION" ]] \
    || die "expected DSH $DSH_VERSION, found ${actual:-unavailable}"
  runtime_job_observation_patch --check
  runtime_checkpoint_compaction_patch --check
  runtime_goal_round_compaction_patch --check
  runtime_compaction_progress_patch --check
  runtime_local_http_timeout_patch --check
  verify_saved_paths
  verify_memory_bundle
  log "verification complete"
}

restore_current() {
  read_manifest
  require_command find
  require_command mv
  require_command npm
  require_command ps
  require_command sed
  require_command tar
  check_node
  check_dsh_stopped

  [[ -d "$REPO_DIR/dsh/profiles" ]] || die "snapshot is incomplete: dsh/profiles is missing"
  prepare_restore_backup
  ensure_dsh_runtime
  ensure_pnpm
  stage_managed_paths

  mkdir -p "$DSH_HOME" "$CODEX_HOME"
  materialize_text "$REPO_DIR/dsh/settings.yaml" "$DSH_HOME/settings.yaml"
  materialize_text "$REPO_DIR/dsh/cordis.patch.yml" "$DSH_HOME/cordis.patch.yml"
  materialize_text "$REPO_DIR/dsh/AGENTS.md" "$DSH_HOME/AGENTS.md"
  if [[ -f "$REPO_DIR/dsh/workspace.json" ]]; then
    materialize_text "$REPO_DIR/dsh/workspace.json" "$DSH_HOME/storages/workspace.json"
  fi
  copy_tree_restore "$REPO_DIR/dsh/presets" "$DSH_HOME/.agent-presets"
  copy_tree_restore "$REPO_DIR/dsh/skills" "$DSH_HOME/skills"
  copy_tree_restore "$REPO_DIR/dsh/plugins" "$DSH_HOME/plugins"
  copy_tree_restore "$REPO_DIR/dsh/bridges" "$DSH_HOME/bridges"
  copy_tree_restore "$REPO_DIR/dsh/profiles" "$DSH_HOME/profiles"

  materialize_text "$REPO_DIR/codex/config.toml.template" "$CODEX_HOME/config.toml"
  if [[ -f "$REPO_DIR/codex/computer-use/config.json" ]]; then
    materialize_text "$REPO_DIR/codex/computer-use/config.json" "$CODEX_HOME/computer-use/config.json"
  fi
  if [[ -d "$REPO_DIR/codex/rules" ]]; then
    copy_tree_restore "$REPO_DIR/codex/rules" "$CODEX_HOME/rules"
  fi
  if [[ -d "$REPO_DIR/codex/skills" ]]; then
    copy_tree_restore "$REPO_DIR/codex/skills" "$CODEX_HOME/skills"
  fi
  if [[ -d "$REPO_DIR/codex/plugins/personal" ]]; then
    copy_tree_restore "$REPO_DIR/codex/plugins/personal" "$CODEX_HOME/plugins/cache/personal"
  fi

  restore_plugins
  restore_profiles
  install_desktop_launcher
  verify_saved_paths
  verify_memory_bundle
  log "restore complete"
  log "managed paths were backed up at $RESTORE_BACKUP_ROOT"
  log "authenticate again and configure external model/API secrets before use"
}

main() {
  local command="${1:-help}"
  case "$command" in
    snapshot) snapshot_current ;;
    restore) restore_current ;;
    verify) verify_current ;;
    help|-h|--help) usage ;;
    *) usage >&2; die "unknown command: $command" ;;
  esac
}

main "$@"
