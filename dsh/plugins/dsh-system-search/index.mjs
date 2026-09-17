import { promises as fs } from 'node:fs'
import os from 'node:os'
import path from 'node:path'

export const name = 'system-search'
export const inject = ['tools']

const DEFAULT_LIMIT = 40
const DEFAULT_MAX_DEPTH = 6
const DEFAULT_MAX_ENTRIES = 100_000
const DEFAULT_TIMEOUT_MS = 8_000
const MAX_ERRORS = 12
const DATA_EXTENSIONS = new Set([
  '.cfg', '.conf', '.csv', '.gif', '.ico', '.ini', '.jpeg', '.jpg', '.json', '.log',
  '.md', '.pdf', '.png', '.svg', '.toml', '.txt', '.webp', '.xml', '.yaml', '.yml',
])

function clamp(value, fallback, min, max) {
  const number = Number(value)
  return Number.isFinite(number) ? Math.max(min, Math.min(Math.trunc(number), max)) : fallback
}

function normalize(value) {
  return String(value)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '')
}

function scoreName(name, query, exact) {
  const candidate = normalize(name)
  if (candidate.length === 0) return null
  if (candidate === query) return 0
  if (exact) return null
  if (candidate.startsWith(query)) return 1
  if (candidate.includes(query)) return 2
  return null
}

function expandRoot(input, cwd, home) {
  let value = String(input || '').trim()
  if (value.length === 0) return null
  const replacements = {
    HOME: home,
    XDG_DATA_HOME: process.env.XDG_DATA_HOME || path.join(home, '.local', 'share'),
    XDG_CONFIG_HOME: process.env.XDG_CONFIG_HOME || path.join(home, '.config'),
    XDG_CACHE_HOME: process.env.XDG_CACHE_HOME || path.join(home, '.cache'),
  }
  value = value.replace(/^~(?=$|[\\/])/, home)
  value = value.replace(/^\$(HOME|XDG_DATA_HOME|XDG_CONFIG_HOME|XDG_CACHE_HOME)(?=$|[\\/])/, (_, key) => replacements[key])
  value = value.replace(/^\$\{(HOME|XDG_DATA_HOME|XDG_CONFIG_HOME|XDG_CACHE_HOME)\}(?=$|[\\/])/, (_, key) => replacements[key])
  return path.resolve(cwd, value)
}

function defaultRoots(scope, cwd, home) {
  const userData = [
    process.env.XDG_DATA_HOME || path.join(home, '.local', 'share'),
    process.env.XDG_CONFIG_HOME || path.join(home, '.config'),
    process.env.XDG_CACHE_HOME || path.join(home, '.cache'),
    path.join(home, '.local', 'bin'),
    path.join(home, 'Applications'),
  ]
  const system = process.platform === 'win32'
    ? [process.env.ProgramFiles, process.env['ProgramFiles(x86)'], process.env.ProgramData]
    : ['/usr/local/bin', '/usr/bin', '/opt', '/usr/share/applications', '/var/lib/flatpak/app', '/snap']
  const pathRoots = String(process.env.PATH || '').split(path.delimiter).filter(Boolean)

  if (scope === 'workspace') return [cwd]
  if (scope === 'user') return [home]
  if (scope === 'system') return [...pathRoots, ...system]
  if (scope === 'all') return [cwd, home, ...pathRoots, ...system]
  return [cwd, ...userData, ...pathRoots, ...system]
}

function uniqueRoots(values, cwd, home) {
  const seen = new Set()
  const roots = []
  for (const value of values) {
    if (value === undefined || value === null) continue
    const resolved = expandRoot(value, cwd, home)
    if (resolved === null || seen.has(resolved)) continue
    seen.add(resolved)
    roots.push(resolved)
  }
  return roots
}

function isExecutable(mode, filePath) {
  if (process.platform === 'win32') return /\.(?:bat|cmd|com|exe|ps1)$/i.test(filePath)
  return (mode & 0o111) !== 0 && !DATA_EXTENSIONS.has(path.extname(filePath).toLowerCase())
}

function isHiddenPath(filePath) {
  return path.resolve(filePath).split(path.sep).some((part) => part.length > 1 && part.startsWith('.'))
}

async function describe(candidatePath, dirent) {
  let stats
  let targetType
  try {
    stats = await fs.lstat(candidatePath)
    if (stats.isSymbolicLink()) {
      try {
        const target = await fs.stat(candidatePath)
        targetType = target.isDirectory() ? 'directory' : target.isFile() ? 'file' : 'other'
        return {
          path: candidatePath,
          name: path.basename(candidatePath),
          type: 'symlink',
          targetType,
          executable: target.isFile() && isExecutable(target.mode, candidatePath),
          hidden: isHiddenPath(candidatePath),
          size: target.isFile() ? target.size : undefined,
          modifiedAt: target.mtime.toISOString(),
        }
      } catch {
        targetType = 'missing'
      }
    }
  } catch {
    return null
  }

  const type = stats.isDirectory() || dirent?.isDirectory()
    ? 'directory'
    : stats.isFile() || dirent?.isFile()
      ? 'file'
      : stats.isSymbolicLink() || dirent?.isSymbolicLink()
        ? 'symlink'
        : 'other'
  return {
    path: candidatePath,
    name: path.basename(candidatePath),
    type,
    ...(targetType === undefined ? {} : { targetType }),
    executable: type === 'file' && isExecutable(stats.mode, candidatePath),
    hidden: isHiddenPath(candidatePath),
    ...(type === 'file' ? { size: stats.size } : {}),
    modifiedAt: stats.mtime.toISOString(),
  }
}

function acceptsKind(item, kind) {
  if (kind === 'any') return true
  if (kind === 'executable') return item.executable === true
  return item.type === kind || (item.type === 'symlink' && item.targetType === kind)
}

function formatResult(result) {
  const lines = [
    `system_search found ${result.matches.length} match(es) for "${result.query}" after scanning ${result.scannedEntries} entries in ${result.elapsedMs} ms.`,
  ]
  for (const item of result.matches) {
    const type = item.type === 'symlink' && item.targetType ? `symlink→${item.targetType}` : item.type
    const flags = [type, item.executable ? 'executable' : null, item.hidden ? 'hidden' : null].filter(Boolean).join(', ')
    lines.push(`- [${flags}] ${item.path}`)
  }
  if (result.truncated) lines.push(`Search truncated: ${result.truncationReason}. Refine query/roots or raise a bounded limit.`)
  if (result.errors.length > 0) {
    lines.push(`Skipped locations (${result.errors.length}):`)
    for (const error of result.errors) lines.push(`- ${error.path}: ${error.code}`)
  }
  return lines.join('\n')
}

export async function searchSystem(args = {}, options = {}) {
  const startedAt = Date.now()
  const queryText = String(args.query || '').trim()
  const query = normalize(queryText)
  if (query.length < 2) throw new Error('query must contain at least two letters or digits')

  const cwd = path.resolve(options.cwd || process.cwd())
  const home = path.resolve(options.home || os.homedir())
  const scope = ['smart', 'workspace', 'user', 'system', 'all'].includes(args.scope) ? args.scope : 'smart'
  const kind = ['any', 'file', 'directory', 'executable'].includes(args.kind) ? args.kind : 'any'
  const limit = clamp(args.maxResults, options.defaultLimit || DEFAULT_LIMIT, 1, 100)
  const maxDepth = clamp(args.maxDepth, options.defaultMaxDepth || DEFAULT_MAX_DEPTH, 0, 16)
  const maxEntries = clamp(args.maxEntries, options.defaultMaxEntries || DEFAULT_MAX_ENTRIES, 100, 500_000)
  const timeoutMs = clamp(args.timeoutMs, options.defaultTimeoutMs || DEFAULT_TIMEOUT_MS, 250, 30_000)
  const explicitRoots = Array.isArray(args.roots) && args.roots.length > 0
  const roots = uniqueRoots(explicitRoots ? args.roots.slice(0, 20) : defaultRoots(scope, cwd, home), cwd, home)
  const exact = args.exact === true
  const signal = options.signal
  const errors = []
  const candidates = []
  const candidatePaths = new Set()
  let scannedEntries = 0
  let timedOut = false
  let entryLimitReached = false

  const recordError = (filePath, error) => {
    if (errors.length >= MAX_ERRORS) return
    if (!explicitRoots && error?.code === 'ENOENT') return
    errors.push({ path: filePath, code: String(error?.code || error?.message || error) })
  }

  for (const root of roots) {
    if (signal?.aborted) throw signal.reason || new Error('system_search aborted')
    if (Date.now() - startedAt >= timeoutMs) { timedOut = true; break }
    const queue = [{ directory: root, depth: 0 }]
    let cursor = 0

    const rootScore = scoreName(path.basename(root), query, exact)
    if (rootScore !== null) {
      const item = await describe(root)
      if (item !== null && acceptsKind(item, kind)) {
        candidates.push({ ...item, match: rootScore === 0 ? 'exact' : rootScore === 1 ? 'prefix' : 'substring', score: rootScore })
        candidatePaths.add(item.path)
      }
    }

    while (cursor < queue.length) {
      if (signal?.aborted) throw signal.reason || new Error('system_search aborted')
      if (Date.now() - startedAt >= timeoutMs) { timedOut = true; break }
      if (scannedEntries >= maxEntries) { entryLimitReached = true; break }
      const current = queue[cursor++]
      let entries
      try {
        entries = await fs.readdir(current.directory, { withFileTypes: true })
      } catch (error) {
        recordError(current.directory, error)
        continue
      }

      for (const entry of entries) {
        scannedEntries += 1
        const candidatePath = path.join(current.directory, entry.name)
        const score = scoreName(entry.name, query, exact)
        if (score !== null && !candidatePaths.has(candidatePath)) {
          const item = await describe(candidatePath, entry)
          if (item !== null && acceptsKind(item, kind)) {
            candidates.push({ ...item, match: score === 0 ? 'exact' : score === 1 ? 'prefix' : 'substring', score })
            candidatePaths.add(candidatePath)
          }
        }
        if (entry.isDirectory() && current.depth < maxDepth) {
          queue.push({ directory: candidatePath, depth: current.depth + 1 })
        }
        if (scannedEntries >= maxEntries) { entryLimitReached = true; break }
      }
      if (timedOut || entryLimitReached) break
    }
    if (timedOut || entryLimitReached) break
  }

  candidates.sort((left, right) => left.score - right.score || left.path.length - right.path.length || left.path.localeCompare(right.path))
  const matches = candidates.slice(0, limit).map(({ score: _score, ...item }) => item)
  const resultLimitReached = candidates.length > limit
  const truncated = timedOut || entryLimitReached || resultLimitReached
  const truncationReason = timedOut
    ? `timeoutMs=${timeoutMs}`
    : entryLimitReached
      ? `maxEntries=${maxEntries}`
      : resultLimitReached
        ? `maxResults=${limit}`
        : null
  const result = {
    query: queryText,
    scope: explicitRoots ? 'custom' : scope,
    kind,
    roots,
    matches,
    scannedEntries,
    elapsedMs: Date.now() - startedAt,
    truncated,
    truncationReason,
    errors,
  }
  return { ...result, text: formatResult(result) }
}

export function apply(ctx, config = {}) {
  ctx.tools.register({
    name: 'system_search',
    description: [
      'Locate files, directories, executables, installed applications, and application data by name on the local system.',
      'Use this before guessing a path, using `which` for non-executables, applying a broad glob, or trying to read a directory.',
      'The default smart scope includes the workspace, PATH, hidden user app locations such as ~/.local/share and ~/.config, and common system application locations.',
      'Searches names only and returns bounded path/type metadata; it never reads file contents or changes the filesystem.',
    ].join(' '),
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['query'],
      properties: {
        query: { type: 'string', description: 'Name or partial name to locate, e.g. "Prism Launcher" or "prismlauncher".' },
        scope: { type: 'string', enum: ['smart', 'workspace', 'user', 'system', 'all'], description: 'Default: smart. Use user/all for a broader home-directory search.' },
        kind: { type: 'string', enum: ['any', 'file', 'directory', 'executable'], description: 'Restrict result type. Default: any.' },
        roots: { type: 'array', maxItems: 20, items: { type: 'string' }, description: 'Optional explicit roots; supports ~, $HOME and XDG directory variables.' },
        exact: { type: 'boolean', description: 'Match normalized names exactly instead of prefix/substring matching.' },
        maxResults: { type: 'integer', minimum: 1, maximum: 100, description: 'Maximum returned matches. Default: 40.' },
        maxDepth: { type: 'integer', minimum: 0, maximum: 16, description: 'Maximum directory depth below each root. Default: 6.' },
        maxEntries: { type: 'integer', minimum: 100, maximum: 500000, description: 'Maximum entries scanned. Default: 100000.' },
        timeoutMs: { type: 'integer', minimum: 250, maximum: 30000, description: 'Search deadline in milliseconds. Default: 8000.' },
      },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: value.text }],
    },
    async execute(args, exec) {
      const cwd = exec?.agent?.session?.header?.cwd || process.cwd()
      return searchSystem(args, {
        cwd,
        signal: exec?.signal,
        defaultLimit: clamp(config.maxResults, DEFAULT_LIMIT, 1, 100),
        defaultMaxDepth: clamp(config.maxDepth, DEFAULT_MAX_DEPTH, 0, 16),
        defaultMaxEntries: clamp(config.maxEntries, DEFAULT_MAX_ENTRIES, 100, 500_000),
        defaultTimeoutMs: clamp(config.timeoutMs, DEFAULT_TIMEOUT_MS, 250, 30_000),
      })
    },
  })

  ctx.inject(['systemPrompt'], (promptCtx) => {
    promptCtx.systemPrompt.section({
      name: 'system-search:discovery',
      order: 215,
      text: [
        'Use `system_search` to locate installed applications, executables, files, directories, and user application data when the exact path is unknown.',
        'It includes hidden locations such as `~/.local/share` and returns whether each match is a file, directory, symlink, or executable.',
        'Call it before guessing paths, using `which` for application data, broad globbing, or trying to read a directory.',
        'If the tool is hidden, search the tool catalog for `system`, `filesystem`, `install`, `application`, or the application name.',
      ].join(' '),
    })
  })
}
