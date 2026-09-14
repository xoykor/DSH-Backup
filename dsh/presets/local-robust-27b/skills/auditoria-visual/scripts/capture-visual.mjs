#!/usr/bin/env node

import fs from 'node:fs/promises';
import { constants as fsConstants } from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const TARGETS = Object.freeze({
  'active-window': { scope: 'window' },
  'under-cursor': { scope: 'window' },
  'current-monitor': { scope: 'monitor' },
  screen: { scope: 'screen' },
});

const MAX_ATTEMPTS = 2;
const DEFAULT_DELAY_MS = 250;
const DEFAULT_TIMEOUT_MS = 15_000;
const MAX_DELAY_MS = 10_000;
const MAX_TIMEOUT_MS = 30_000;
const OUTPUT_WAIT_MS = 2_000;

class AdapterError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = 'AdapterError';
    this.code = code;
    this.details = details;
  }
}

const BACKEND_DEFINITIONS = Object.freeze([
  {
    name: 'spectacle',
    commands: ['spectacle'],
    // Do not include under-cursor here: on this Wayland session it can fall
    // back to an interactive selector. The adapter must never open one.
    supports: new Set(['active-window', 'current-monitor', 'screen']),
    args(target, outputPath, delayMs) {
      const captureFlag = {
        'active-window': '--activewindow',
        'current-monitor': '--current',
        screen: '--fullscreen',
      }[target];
      return ['--background', '--nonotify', '--delay', String(delayMs), captureFlag, '--output', outputPath];
    },
  },
  {
    name: 'grim',
    commands: ['grim'],
    supports: new Set(['screen']),
    args(_target, outputPath) {
      return [outputPath];
    },
  },
  {
    name: 'gnome-screenshot',
    commands: ['gnome-screenshot'],
    supports: new Set(['active-window', 'screen']),
    args(target, outputPath) {
      return target === 'active-window' ? ['--window', '--file', outputPath] : ['--file', outputPath];
    },
  },
  {
    name: 'import',
    commands: ['import'],
    supports: new Set(['screen']),
    args(_target, outputPath) {
      return ['-window', 'root', outputPath];
    },
  },
  {
    name: 'scrot',
    commands: ['scrot'],
    supports: new Set(['screen']),
    args(_target, outputPath) {
      return [outputPath];
    },
  },
  {
    name: 'maim',
    commands: ['maim'],
    supports: new Set(['screen']),
    args(_target, outputPath) {
      return [outputPath];
    },
  },
]);

function usage() {
  return [
    'Usage: node scripts/capture-visual.mjs --target <active-window|under-cursor|current-monitor|screen> --reason <text> [options]',
    '',
    'Options:',
    '  --step <label>          Evidence step label (default: visual-audit)',
    '  --evidence-dir <path>   Evidence directory (default: .dsh/evidence/visual)',
    '  --delay-ms <number>     Capture delay, bounded to 0..10000 (default: 250)',
    '  --timeout-ms <number>   Backend timeout, bounded to 1000..30000 (default: 15000)',
  ].join('\n');
}

function valueFor(argv, index, flag) {
  const value = argv[index + 1];
  if (value === undefined || value.startsWith('--')) {
    throw new AdapterError('MISSING_ARGUMENT', `${flag} requires a value`);
  }
  return value;
}

function boundedInteger(value, flag, minimum, maximum) {
  if (!/^\d+$/.test(value)) {
    throw new AdapterError('INVALID_ARGUMENT', `${flag} must be an integer`);
  }
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < minimum || number > maximum) {
    throw new AdapterError('INVALID_ARGUMENT', `${flag} must be between ${minimum} and ${maximum}`);
  }
  return number;
}

function safeLabel(value, fallback) {
  const label = (value || fallback).trim().replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '');
  return label.slice(0, 80) || fallback;
}

export function scopeForTarget(target) {
  return TARGETS[target]?.scope ?? null;
}

export function parseArgs(argv, cwd = process.cwd()) {
  const parsed = {
    target: null,
    reason: null,
    step: 'visual-audit',
    evidenceDir: path.resolve(cwd, '.dsh', 'evidence', 'visual'),
    delayMs: DEFAULT_DELAY_MS,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (flag === '--help' || flag === '-h') {
      parsed.help = true;
      continue;
    }
    if (flag === '--target') {
      parsed.target = valueFor(argv, index, flag);
      index += 1;
      continue;
    }
    if (flag === '--reason') {
      parsed.reason = valueFor(argv, index, flag).trim();
      index += 1;
      continue;
    }
    if (flag === '--step') {
      parsed.step = valueFor(argv, index, flag).trim();
      index += 1;
      continue;
    }
    if (flag === '--evidence-dir') {
      parsed.evidenceDir = path.resolve(cwd, valueFor(argv, index, flag));
      index += 1;
      continue;
    }
    if (flag === '--delay-ms') {
      parsed.delayMs = boundedInteger(valueFor(argv, index, flag), flag, 0, MAX_DELAY_MS);
      index += 1;
      continue;
    }
    if (flag === '--timeout-ms') {
      parsed.timeoutMs = boundedInteger(valueFor(argv, index, flag), flag, 1_000, MAX_TIMEOUT_MS);
      index += 1;
      continue;
    }
    throw new AdapterError('UNKNOWN_ARGUMENT', `unknown argument: ${flag}`);
  }

  if (parsed.help) return parsed;
  if (!parsed.target || !Object.hasOwn(TARGETS, parsed.target)) {
    throw new AdapterError('INVALID_TARGET', `--target must be one of: ${Object.keys(TARGETS).join(', ')}`, {
      target: parsed.target,
      requestedScope: scopeForTarget(parsed.target),
    });
  }
  if (!parsed.reason) {
    throw new AdapterError('MISSING_ARGUMENT', '--reason requires a non-empty value');
  }
  if (parsed.reason.length > 1_000) {
    throw new AdapterError('INVALID_ARGUMENT', '--reason is limited to 1000 characters');
  }
  if (!parsed.step) {
    throw new AdapterError('MISSING_ARGUMENT', '--step requires a non-empty value');
  }
  if (parsed.step.length > 200) {
    throw new AdapterError('INVALID_ARGUMENT', '--step is limited to 200 characters');
  }
  return parsed;
}

async function executable(candidate) {
  try {
    await fs.access(candidate, fsConstants.X_OK);
    return true;
  } catch {
    return false;
  }
}

async function findCommand(commands, env = process.env) {
  const pathEntries = (env.PATH || '').split(path.delimiter).filter(Boolean);
  const candidates = [];
  for (const command of commands) {
    if (path.isAbsolute(command)) {
      candidates.push(command);
      continue;
    }
    for (const directory of pathEntries) candidates.push(path.join(directory, command));
    if (process.platform === 'linux') {
      candidates.push(`/usr/bin/${command}`, `/usr/local/bin/${command}`);
    }
  }
  const seen = new Set();
  for (const candidate of candidates) {
    if (seen.has(candidate)) continue;
    seen.add(candidate);
    if (await executable(candidate)) return candidate;
  }
  return null;
}

export async function discoverBackends(env = process.env) {
  const discovered = [];
  for (const definition of BACKEND_DEFINITIONS) {
    const command = await findCommand(definition.commands, env);
    if (command) discovered.push({ definition, command });
  }
  return discovered;
}

export function selectBackend(discovered, target) {
  return discovered.find(({ definition }) => definition.supports.has(target)) ?? null;
}

function graphicalSession(env = process.env) {
  return Boolean(env.WAYLAND_DISPLAY || env.DISPLAY || env.MIR_SOCKET);
}

function imageMetadata(buffer) {
  if (buffer.length >= 24 && buffer.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) {
    if (buffer.toString('ascii', 12, 16) !== 'IHDR') return null;
    const width = buffer.readUInt32BE(16);
    const height = buffer.readUInt32BE(20);
    return width > 0 && height > 0 ? { mediaType: 'image/png', width, height } : null;
  }
  if (buffer.length >= 10 && (buffer.subarray(0, 6).toString('ascii') === 'GIF87a' || buffer.subarray(0, 6).toString('ascii') === 'GIF89a')) {
    const width = buffer.readUInt16LE(6);
    const height = buffer.readUInt16LE(8);
    return width > 0 && height > 0 ? { mediaType: 'image/gif', width, height } : null;
  }
  if (buffer.length >= 12 && buffer.subarray(0, 4).toString('ascii') === 'RIFF' && buffer.subarray(8, 12).toString('ascii') === 'WEBP') {
    return { mediaType: 'image/webp' };
  }
  if (buffer.length >= 3 && buffer.subarray(0, 3).equals(Buffer.from([0xff, 0xd8, 0xff]))) {
    return { mediaType: 'image/jpeg' };
  }
  return null;
}

export function inspectImageBuffer(buffer) {
  if (!Buffer.isBuffer(buffer) || buffer.length === 0) {
    throw new AdapterError('EMPTY_IMAGE', 'capture produced an empty image');
  }
  const metadata = imageMetadata(buffer);
  if (!metadata) {
    throw new AdapterError('INVALID_IMAGE', 'capture did not produce a supported PNG, JPEG, WebP, or GIF image');
  }
  return { bytes: buffer.length, ...metadata };
}

async function inspectImageFile(filePath) {
  let stat;
  try {
    stat = await fs.stat(filePath);
  } catch (error) {
    throw new AdapterError('IMAGE_NOT_CREATED', `capture did not create ${filePath}`, { cause: error.code });
  }
  if (!stat.isFile() || stat.size === 0) {
    throw new AdapterError('EMPTY_IMAGE', 'capture produced no usable image bytes', { bytes: stat.size });
  }
  let buffer;
  try {
    buffer = await fs.readFile(filePath);
  } catch (error) {
    throw new AdapterError('IMAGE_UNREADABLE', `capture file could not be read: ${filePath}`, { cause: error.code });
  }
  return inspectImageBuffer(buffer);
}

async function waitForOutput(filePath, timeoutMs = OUTPUT_WAIT_MS) {
  const startedAt = Date.now();
  while (Date.now() - startedAt <= timeoutMs) {
    try {
      const stat = await fs.stat(filePath);
      if (stat.isFile() && stat.size > 0) return true;
    } catch (error) {
      if (error.code !== 'ENOENT') return false;
    }
    await wait(100);
  }
  return false;
}

function shorten(value, maximum = 800) {
  return String(value || '').trim().slice(0, maximum);
}

function runCapture(command, args, timeoutMs, env = process.env) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      env,
      stdio: ['ignore', 'ignore', 'pipe'],
    });
    let stderr = '';
    let settled = false;
    let killTimer;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeoutTimer);
      if (killTimer) clearTimeout(killTimer);
      resolve(result);
    };
    const timeoutTimer = setTimeout(() => {
      child.kill('SIGTERM');
      killTimer = setTimeout(() => {
        child.kill('SIGKILL');
        finish({ ok: false, timeout: true, code: null, signal: 'SIGKILL', stderr: shorten(stderr) });
      }, 1_000);
    }, timeoutMs);
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('error', (error) => {
      finish({ ok: false, timeout: false, code: null, signal: null, error: error.code || error.message, stderr: shorten(stderr) });
    });
    child.on('close', (code, signal) => {
      finish({ ok: code === 0 && signal === null, timeout: false, code, signal, stderr: shorten(stderr) });
    });
  });
}

function timestampPart(date = new Date()) {
  return date.toISOString().replace(/[-:]/g, '').replace(/\.(\d{3})Z$/, '$1Z');
}

function evidenceFilePath(options, attempt) {
  const label = safeLabel(options.step, 'visual-audit');
  const target = safeLabel(options.target, 'target');
  const suffix = attempt > 1 ? `-retry-${attempt}` : '';
  return path.join(options.evidenceDir, `${timestampPart()}-${label}-${target}${suffix}.png`);
}

function baseResult(options, attemptedAt = new Date().toISOString()) {
  return {
    ok: false,
    captured: false,
    inspected: false,
    visuallyApproved: false,
    target: options.target ?? null,
    requestedScope: options.target ? scopeForTarget(options.target) : null,
    scope: null,
    actualScope: null,
    reason: options.reason ?? null,
    step: options.step ?? null,
    attemptedAt,
    capturedAt: null,
    filePath: null,
    resource: null,
  };
}

function errorResult(options, code, message, details = {}) {
  return {
    ...baseResult(options),
    error: { code, message, ...details },
  };
}

async function removeIfCreated(filePath) {
  if (!filePath) return;
  try {
    await fs.unlink(filePath);
  } catch (error) {
    if (error.code !== 'ENOENT') return;
  }
}

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function captureVisual(options, env = process.env) {
  const attemptedAt = new Date().toISOString();
  const resultBase = baseResult(options, attemptedAt);
  if (!graphicalSession(env)) {
    return {
      ...resultBase,
      error: {
        code: 'NO_GRAPHICAL_SESSION',
        message: 'no graphical session was detected (WAYLAND_DISPLAY, DISPLAY, or MIR_SOCKET is missing)',
      },
      availableBackends: [],
    };
  }

  const discovered = await discoverBackends(env);
  if (options.target === 'under-cursor') {
    return {
      ...resultBase,
      error: {
        code: 'CAPTURE_TARGET_DISABLED',
        message: 'under-cursor capture is disabled to avoid opening Spectacle\'s interactive selector; activate the intended window and use active-window',
      },
      availableBackends: discovered.map(({ definition }) => definition.name),
    };
  }
  const backend = selectBackend(discovered, options.target);
  if (!backend) {
    return {
      ...resultBase,
      error: {
        code: 'CAPTURE_UNAVAILABLE',
        message: `no installed capture backend supports the requested ${options.target} scope`,
      },
      availableBackends: discovered.map(({ definition }) => definition.name),
    };
  }

  try {
    await fs.mkdir(options.evidenceDir, { recursive: true });
  } catch (error) {
    return {
      ...resultBase,
      error: {
        code: 'EVIDENCE_DIRECTORY_UNAVAILABLE',
        message: `could not create evidence directory ${options.evidenceDir}`,
        cause: error.code || error.message,
      },
      backend: backend.definition.name,
    };
  }

  const attempts = [];
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
    const filePath = evidenceFilePath(options, attempt);
    const commandArgs = backend.definition.args(options.target, filePath, options.delayMs);
    const commandResult = await runCapture(backend.command, commandArgs, options.timeoutMs, env);
    if (commandResult.ok) {
      try {
        if (!(await waitForOutput(filePath))) {
          throw new AdapterError('IMAGE_NOT_CREATED', `capture did not create ${filePath}`);
        }
        const image = await inspectImageFile(filePath);
        const capturedAt = new Date().toISOString();
        return {
          ok: true,
          captured: true,
          inspected: false,
          visuallyApproved: false,
          target: options.target,
          requestedScope: scopeForTarget(options.target),
          scope: scopeForTarget(options.target),
          actualScope: scopeForTarget(options.target),
          reason: options.reason,
          step: options.step,
          attemptedAt,
          capturedAt,
          backend: backend.definition.name,
          command: backend.command,
          filePath,
          resource: { kind: 'image-file', path: filePath },
          recovery: { performed: attempt > 1, attempts: attempt, maxAttempts: MAX_ATTEMPTS },
          ...image,
        };
      } catch (error) {
        attempts.push({
          attempt,
          filePath,
          code: error.code || 'INVALID_IMAGE',
          message: error.message,
          backendExitCode: commandResult.code,
        });
        await removeIfCreated(filePath);
      }
    } else {
      attempts.push({
        attempt,
        filePath,
        code: commandResult.timeout ? 'CAPTURE_TIMEOUT' : 'CAPTURE_COMMAND_FAILED',
        message: commandResult.timeout
          ? `capture backend exceeded ${options.timeoutMs} ms`
          : `capture backend exited with code ${commandResult.code ?? 'unknown'}`,
        signal: commandResult.signal,
        stderr: commandResult.stderr,
        commandError: commandResult.error,
      });
      await removeIfCreated(filePath);
    }
    if (attempt < MAX_ATTEMPTS) await wait(150);
  }

  return {
    ...resultBase,
    error: {
      code: 'CAPTURE_FAILED_AFTER_RECOVERY',
      message: `capture failed after ${MAX_ATTEMPTS} attempts; no valid image evidence was retained`,
    },
    backend: backend.definition.name,
    command: backend.command,
    recovery: { performed: true, attempts: MAX_ATTEMPTS, maxAttempts: MAX_ATTEMPTS },
    attempts,
  };
}

export async function main(argv = process.argv.slice(2), cwd = process.cwd(), env = process.env) {
  let options;
  try {
    options = parseArgs(argv, cwd);
  } catch (error) {
    const errorOptions = {
      target: error.details?.target ?? null,
      reason: error.details?.reason ?? null,
      step: error.details?.step ?? null,
    };
    const result = error instanceof AdapterError
      ? errorResult(errorOptions, error.code, error.message, error.details)
      : errorResult({ target: null, reason: null, step: null }, 'ADAPTER_ERROR', error.message);
    return { exitCode: 1, result };
  }
  if (options.help) {
    return {
      exitCode: 0,
      result: { ok: true, captured: false, inspected: false, visuallyApproved: false, usage: usage() },
    };
  }
  try {
    const result = await captureVisual(options, env);
    return { exitCode: result.ok ? 0 : 1, result };
  } catch (error) {
    const result = error instanceof AdapterError
      ? errorResult(options, error.code, error.message, error.details)
      : errorResult(options, 'ADAPTER_ERROR', error.message);
    return { exitCode: 1, result };
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : null;
if (invokedPath === import.meta.url) {
  const { exitCode, result } = await main();
  process.stdout.write(`${JSON.stringify(result)}\n`);
  process.exitCode = exitCode;
}
