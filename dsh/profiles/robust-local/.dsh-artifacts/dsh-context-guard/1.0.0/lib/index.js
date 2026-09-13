/**
 * Model-independent execution budget and loop protection for DSH.
 *
 * The plugin intentionally depends only on public Cordis services. Decisions
 * that stop a turn are made by the executor, not by a model instruction.
 */
export const name = 'dsh-context-guard';
export const inject = ['tools', 'tokenMeter'];

const DEFAULTS = Object.freeze({
  economyTokens: 20_000,
  checkpointTokens: 25_000,
  compactTokens: 30_000,
  noProgressLimit: 3,
  equivalentBlockLimit: 5,
  maxTurnSteps: 48,
  maxTurnToolCalls: 48,
  maxTurnMs: 900_000,
  maxTurnTokens: 180_000,
  diagnosticMaxCalls: 3,
  diagnosticMaxMs: 120_000,
  diagnosticMaxTokens: 24_000,
  textSimilarity: 0.94,
  resultFingerprintChars: 4_000,
});

function positiveInteger(value, fallback, label) {
  if (value === undefined) return fallback;
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error('dsh-context-guard: ' + label + ' must be a positive integer');
  }
  return value;
}

function resolveConfig(raw = {}) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('dsh-context-guard: configuration must be an object');
  }
  const knownKeys = new Set([
    'economyTokens', 'checkpointTokens', 'compactTokens', 'noProgressLimit',
    'equivalentBlockLimit', 'maxTurnSteps', 'maxTurnToolCalls', 'maxTurnMs',
    'maxTurnTokens', 'diagnosticMaxCalls', 'diagnosticMaxMs',
    'diagnosticMaxTokens', 'textSimilarity', 'resultFingerprintChars',
  ]);
  for (const key of Object.keys(raw)) {
    if (!knownKeys.has(key)) {
      throw new Error('dsh-context-guard: unknown configuration key "' + key + '"');
    }
  }
  const config = {
    economyTokens: positiveInteger(raw.economyTokens, DEFAULTS.economyTokens, 'economyTokens'),
    checkpointTokens: positiveInteger(raw.checkpointTokens, DEFAULTS.checkpointTokens, 'checkpointTokens'),
    compactTokens: positiveInteger(raw.compactTokens, DEFAULTS.compactTokens, 'compactTokens'),
    noProgressLimit: positiveInteger(raw.noProgressLimit, DEFAULTS.noProgressLimit, 'noProgressLimit'),
    equivalentBlockLimit: positiveInteger(raw.equivalentBlockLimit, DEFAULTS.equivalentBlockLimit, 'equivalentBlockLimit'),
    maxTurnSteps: positiveInteger(raw.maxTurnSteps, DEFAULTS.maxTurnSteps, 'maxTurnSteps'),
    maxTurnToolCalls: positiveInteger(raw.maxTurnToolCalls, DEFAULTS.maxTurnToolCalls, 'maxTurnToolCalls'),
    maxTurnMs: positiveInteger(raw.maxTurnMs, DEFAULTS.maxTurnMs, 'maxTurnMs'),
    maxTurnTokens: positiveInteger(raw.maxTurnTokens, DEFAULTS.maxTurnTokens, 'maxTurnTokens'),
    diagnosticMaxCalls: positiveInteger(raw.diagnosticMaxCalls, DEFAULTS.diagnosticMaxCalls, 'diagnosticMaxCalls'),
    diagnosticMaxMs: positiveInteger(raw.diagnosticMaxMs, DEFAULTS.diagnosticMaxMs, 'diagnosticMaxMs'),
    diagnosticMaxTokens: positiveInteger(raw.diagnosticMaxTokens, DEFAULTS.diagnosticMaxTokens, 'diagnosticMaxTokens'),
    textSimilarity: raw.textSimilarity ?? DEFAULTS.textSimilarity,
    resultFingerprintChars: positiveInteger(raw.resultFingerprintChars, DEFAULTS.resultFingerprintChars, 'resultFingerprintChars'),
  };
  if (!(config.economyTokens < config.checkpointTokens && config.checkpointTokens < config.compactTokens)) {
    throw new Error('dsh-context-guard: economyTokens < checkpointTokens < compactTokens is required');
  }
  if (config.diagnosticMaxCalls > config.maxTurnToolCalls) {
    throw new Error('dsh-context-guard: diagnosticMaxCalls must be <= maxTurnToolCalls');
  }
  if (typeof config.textSimilarity !== 'number' || config.textSimilarity < 0.8 || config.textSimilarity > 1) {
    throw new Error('dsh-context-guard: textSimilarity must be between 0.8 and 1');
  }
  return Object.freeze(config);
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]));
  }
  return value;
}

function canonical(value) {
  try {
    return JSON.stringify(stable(value));
  } catch {
    return String(value);
  }
}

function normalizedText(value) {
  return String(value ?? '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[^\p{L}\p{N} ]/gu, '')
    .trim();
}

function similarity(left, right) {
  if (!left || !right) return 0;
  if (left === right) return 1;
  const a = new Set(left.split(' ').filter(Boolean));
  const b = new Set(right.split(' ').filter(Boolean));
  let shared = 0;
  for (const token of a) if (b.has(token)) shared += 1;
  return shared / Math.max(a.size, b.size);
}

function toolResultText(result, cap) {
  const blocks = Array.isArray(result?.content) ? result.content : [];
  const content = blocks.map((block) => {
    if (block?.type === 'text') return block.text;
    try { return JSON.stringify(block); } catch { return String(block); }
  }).join('\n');
  let value = '';
  if (result?.value !== undefined) {
    try { value = JSON.stringify(stable(result.value)); } catch { value = String(result.value); }
  }
  const prefix = result?.isError === true ? 'error:' : 'ok:';
  // Put structured executor facts first so timeout, exit, and fs before/after
  // metadata cannot be pushed out of the bounded fingerprint by stdout.
  const serialized = prefix + (value ? '\nvalue:' + value : '') + '\ncontent:' + content;
  return serialized.slice(0, cap);
}

function isWorkspaceMutation(name) {
  return /(?:write|edit|patch|replace|apply|create_file|delete|unlink|rename|move|install|format|mkdir|rm|mv|cp)/i.test(name);
}

const COMMAND_TOOLS = new Set([
  'bash',
  'shell',
  'exec',
  'terminal',
  'run_code',
  'python',
  'pwsh',
  'powershell',
  'code',
]);

function hasReadOnlyCapability(exec) {
  // Read-only is executor metadata, never inferred from a tool name or source
  // text. The DSH ToolExecution contract currently has no built-in field, so a
  // host that wants timeout diagnosis must explicitly attach one of these
  // capability shapes at its policy boundary.
  return exec?.readOnly === true
    || exec?.capabilities?.readOnly === true
    || exec?.capability?.readOnly === true
    || exec?.definition?.readOnly === true;
}

function identityArguments(argumentsValue) {
  if (!argumentsValue || typeof argumentsValue !== 'object' || Array.isArray(argumentsValue)) {
    return argumentsValue;
  }
  return Object.fromEntries(
    Object.entries(argumentsValue).filter(([key]) => key !== 'description'),
  );
}

function actionKey(name, argumentsValue) {
  return String(name) + '\u0000' + canonical(identityArguments(argumentsValue));
}

function fileReferences(argumentsValue) {
  const text = canonical(argumentsValue);
  const matches = text.match(
    /[A-Za-z0-9_.~/-]+[A-Za-z0-9_.~-]*\.(?:py|js|mjs|ts|tsx|json|ya?ml|toml|ini|cfg|conf|md|log|txt)/gi,
  ) ?? [];
  return [...new Set(matches)].sort().slice(0, 16);
}

function semanticActionKey(name, argumentsValue) {
  const normalizedName = String(name).toLowerCase();
  const args = identityArguments(argumentsValue);
  const files = fileReferences(args);
  const subject = args && typeof args === 'object'
    ? (args.command ?? args.code ?? args.path ?? args.file ?? args.query ?? '')
    : '';
  // Keep command/content bytes intact for semantic cycle identity. The
  // bounded slice is only a memory cap; whitespace is not a delimiter here.
  const subjectText = String(subject).slice(0, 240);
  if (files.length > 0) {
    return normalizedName + '|' + files.join('|') + (COMMAND_TOOLS.has(normalizedName) ? '|' + subjectText : '');
  }
  return normalizedName + '|' + (subjectText || canonical(args).slice(0, 240));
}

function isCommandTool(name) {
  return COMMAND_TOOLS.has(String(name).toLowerCase());
}

function commandArgument(argumentsValue) {
  if (!argumentsValue || typeof argumentsValue !== 'object') return '';
  return String(argumentsValue.command ?? argumentsValue.code ?? '').trim();
}

function normalizedErrorText(value) {
  return String(value ?? '')
    .toLowerCase()
    .replace(/0x[\da-f]+/gi, '<hex>')
    .replace(/(?:line|column|col|offset|position)\s*[:=]?\s*\d+/g, '$1:<n>')
    .replace(/\b\d+\b/g, '<n>')
    .replace(/(?:\/[^\s:'"]+)+/g, '<path>')
    .replace(/\s+/g, ' ')
    .trim();
}

function resultErrorCause(result) {
  const value = result?.value;
  return value?.code ?? value?.errorCode ?? value?.reason ?? value?.error
    ?? result?.error?.code ?? result?.error?.message
    ?? (Array.isArray(result?.content) ? result.content.map((block) => block?.text ?? '').join(' ') : '');
}

function commandFailureEvidence(result, toolName) {
  if (result?.isError === true || timeoutEvidence(result, toolName)) return true;
  if (!isCommandTool(toolName)) return false;
  const value = result?.value;
  const exitCode = value?.exitCode ?? value?.exit_code;
  if (Number.isFinite(exitCode) && exitCode !== 0) return true;
  if (value?.signal !== undefined && value.signal !== null && value.signal !== '') return true;
  if (value?.aborted === true || value?.sandboxDenied === true || value?.sandbox_denied === true
    || value?.permissionDenied === true || value?.permission_denied === true) return true;
  const text = toolResultText(result, 4_000).toLowerCase();
  return /sandbox\s+(?:denied|violation)|permission denied|access denied|not permitted/.test(text);
}

function errorFamily(toolName, argumentsValue, result) {
  if (result?.isError !== true && !commandFailureEvidence(result, toolName)) return undefined;
  const cause = normalizedErrorText(resultErrorCause(result));
  let stage = 'other';
  if (timeoutEvidence(result, toolName) || /timeout|timed out|etimedout/.test(cause)) stage = 'timeout';
  else if (/parse|syntax|unicode escape|type-strip|unexpected token/.test(cause)) stage = 'parse';
  else if (/type error|undefined|null is not|not a function|cannot read/.test(cause)) stage = 'type';
  else if (result?.value?.sandboxDenied === true || result?.value?.sandbox_denied === true
    || result?.value?.permissionDenied === true || result?.value?.permission_denied === true
    || /permission|eacces|eperm|access denied|sandbox|not permitted|denied/.test(cause)) stage = 'permission';
  else if (/network|connection|enotfound|econn|http\s*[45]\d\d/.test(cause)) stage = 'network';
  else if (/validation|invalid argument|schema|unknown key/.test(cause)) stage = 'validation';
  const refs = fileReferences(argumentsValue).join('|');
  // Keep the class and resource, while dropping changing stack locations and
  // prose. The full result remains in the normal tool log for diagnosis.
  return String(toolName).toLowerCase() + '|' + stage + '|' + refs;
}

function errorFamilyHint(toolName, argumentsValue) {
  const text = normalizedErrorText(commandArgument(argumentsValue));
  let stage = 'other';
  if (/timeout|timed out|etimedout/.test(text)) stage = 'timeout';
  else if (/parse|syntax|unicode escape|type-strip|unexpected token|bad syntax/.test(text)) stage = 'parse';
  else if (/type error|undefined|null is not|not a function|cannot read/.test(text)) stage = 'type';
  return String(toolName).toLowerCase() + '|' + stage;
}

function observedMutationChange(result) {
  if (result?.isError === true) return false;
  const candidates = [result, result?.value, result?.meta];
  for (const value of candidates) if (value && typeof value === 'object') {
    if (value.changed === true || value.modified === true || value.written === true) return true;
    if (Array.isArray(value.changedFiles) && value.changedFiles.length > 0) return true;
    if (value.before !== undefined && value.after !== undefined && canonical(value.before) !== canonical(value.after)) return true;
    if (value.beforeHash !== undefined && value.afterHash !== undefined && value.beforeHash !== value.afterHash) return true;
    if (value.revision !== undefined || value.newRevision !== undefined) return true;
  }
  return false;
}

function tokenUsageAmount(usage) {
  if (!usage || typeof usage !== 'object') return undefined;
  const total = usage.totalTokens;
  const parts = [
    usage.inputTokens, usage.outputTokens, usage.cacheReadTokens,
    usage.cacheWriteTokens,
  ];
  if (Number.isFinite(total) && total > 0) return total;
  if (!parts.some((part) => Number.isFinite(part))) {
    return Number.isFinite(total) && total >= 0 ? total : undefined;
  }
  return parts.reduce((sum, part) => sum + (Number.isFinite(part) && part >= 0 ? part : 0), 0);
}

function isWorkspaceMutationCall(name, argumentsValue) {
  if (isWorkspaceMutation(name)) return true;
  if (!isCommandTool(name)) return false;
  const command = commandArgument(argumentsValue);
  return /(?:\b(?:sed|perl|tee|touch|mkdir|rmdir|rm|mv|cp|install|patch|apply_patch)\b|\bgit\s+(?:apply|checkout|restore|merge|cherry-pick)\b|\b(?:npm|pnpm|yarn)\s+(?:install|add|remove|uninstall)\b|\bpip\s+install\b|\b(?:write_text|writeFile|appendFile|open\s*\([^\n]*['\"](?:w|a))|(?:^|[^>])>{1,2})/i.test(command);
}

function timeoutEvidence(result, toolName) {
  const value = result?.value;
  if (value && (value.timedOut === true || value.timed_out === true || value.timeout === true)) {
    return true;
  }
  if (!isCommandTool(toolName)) return false;
  const reason = value?.reason ?? value?.error ?? result?.error?.message;
  if (typeof reason === 'string' && /(?:BASH_TIMEOUT|timed out|etimedout|timeout)/i.test(reason)) {
    return true;
  }
  const text = toolResultText(result, 4_000).toLowerCase();
  if (/\[timed out after \d+\s*ms\]|bash_timeout|etimedout/.test(text)) return true;
  const exitCode = value?.exitCode ?? value?.exit_code;
  return isCommandTool(toolName) && exitCode === 124;
}

function timeoutDuration(result) {
  const value = result?.value;
  for (const candidate of [value?.durationMs, value?.duration_ms, value?.timeoutMs, value?.timeout_ms]) {
    if (Number.isFinite(candidate) && candidate > 0) return candidate;
  }
  const match = toolResultText(result, 2_000).match(/(?:after|timeout(?:ed)?)[^\d]*(\d+)\s*ms/i);
  return match ? Number(match[1]) : undefined;
}

function cycleAtom(entry) {
  return canonical([
    entry.semanticKey,
    entry.resultFingerprint,
    entry.changeVersion,
  ]);
}

function hasRepeatedCycle(history) {
  const maximumPeriod = Math.min(6, Math.floor(history.length / 2));
  for (let period = 2; period <= maximumPeriod; period += 1) {
    const split = history.length - period;
    let equal = true;
    for (let index = 0; index < period; index += 1) {
      if (cycleAtom(history[split - period + index]) !== cycleAtom(history[split + index])) {
        equal = false;
        break;
      }
    }
    if (equal) return true;
  }
  return false;
}

function isGuardResult(result) {
  return result?.isError === true && toolResultText(result, 300).includes('CONTEXT-GUARD');
}

function notice(text, summary) {
  return Object.freeze({
    id: 'context-guard-' + crypto.randomUUID(),
    role: 'user',
    content: Object.freeze([Object.freeze({ type: 'text', text })]),
    source: Object.freeze({ kind: 'plugin', plugin: name, form: 'notice', summary }),
  });
}

function createState() {
  return {
    actionCounts: new Map(),
    stagnantActionCounts: new Map(),
    failureFamilyCounts: new Map(),
    failureFamilyVersion: new Map(),
    lastFailureFamily: '',
    lastResultByAction: new Map(),
    actionSamples: [],
    actionHistory: [],
    noProgress: 0,
    lastAssistantText: '',
    repeatedAssistantText: false,
    currentTurn: null,
    currentStep: 0,
    logicalStartedAt: 0,
    logicalSteps: 0,
    turnStartedAt: 0,
    turnActive: false,
    turnCalls: 0,
    inFlightCalls: 0,
    turnTokenBaseline: null,
    turnTokenUsage: 0,
    reportedTokenUsage: 0,
    hasReportedTokenUsage: false,
    meterHighWater: 0,
    changeVersion: 0,
    mode: 'idle',
    stopReason: '',
    cancelFailed: false,
    timeoutRecord: null,
    diagnosticCalls: 0,
    diagnosticStartedAt: 0,
    diagnosticTokenBaseline: 0,
    diagnosticNoticeIssued: false,
    turnTimer: undefined,
    diagnosticTimer: undefined,
    economyNoticed: false,
    checkpointNoticed: false,
    compactNoticed: false,
  };
}

export function apply(ctx, rawConfig = {}) {
  const config = resolveConfig(rawConfig);
  const states = new WeakMap();
  const sessionStates = new Map();

  const stateFor = (agent) => {
    let state = states.get(agent);
    if (!state) {
      const sessionId = agent?.session?.id === undefined ? undefined : String(agent.session.id);
      state = sessionId === undefined ? undefined : sessionStates.get(sessionId);
      if (!state) state = createState();
      states.set(agent, state);
      if (sessionId !== undefined) sessionStates.set(sessionId, state);
    }
    return state;
  };

  const clearTimer = (timer) => {
    if (timer !== undefined) clearTimeout(timer);
  };

  const clearTurnTimers = (state) => {
    clearTimer(state.turnTimer);
    clearTimer(state.diagnosticTimer);
    state.turnTimer = undefined;
    state.diagnosticTimer = undefined;
  };

  const readTokenTotal = (agent) => {
    if (!ctx.tokenMeter || !agent?.session) return undefined;
    try {
      const total = ctx.tokenMeter.measure(agent.session).totalTokens;
      return Number.isFinite(total) ? total : undefined;
    } catch {
      return undefined;
    }
  };

  const updateTokenUsage = (state, agent) => {
    if (state.hasReportedTokenUsage) {
      state.turnTokenUsage = Math.max(state.turnTokenUsage, state.reportedTokenUsage);
      return state.turnTokenUsage;
    }
    const total = readTokenTotal(agent);
    if (total === undefined) return undefined;
    if (state.turnTokenBaseline === null) state.turnTokenBaseline = total;
    const usage = Math.max(0, total - state.turnTokenBaseline);
    // `measure().totalTokens` is current context pressure. Keep a monotonic
    // high-water fallback so compaction cannot make the hard limit go down.
    state.meterHighWater = Math.max(state.meterHighWater, usage);
    state.turnTokenUsage = Math.max(state.turnTokenUsage, state.meterHighWater);
    return state.turnTokenUsage;
  };

  const stopTurn = (agent, state, reason, mode = 'stopped') => {
    if (state.mode === 'stopped' || state.mode === 'paused') return;
    state.mode = mode;
    state.stopReason = reason;
    state.cancelFailed = false;
    state.turnActive = false;
    clearTurnTimers(state);

    // Agent cancellation aborts exec.signal. Managed subprocess executors pass
    // that signal to their process-tree handle and await its termination.
    if (typeof agent?.cancel === 'function') {
      try {
        if (agent.status === undefined || agent.status === 'running') {
          agent.cancel({ kind: 'hook', reason }, { keepInbox: true });
        }
      } catch {
        // The turn may already be at its driver boundary; the guard still
        // denies every subsequent tool call, while exposing cancellation
        // uncertainty in the durable stop reason.
        state.cancelFailed = true;
        state.stopReason = reason + ' Agent cancellation could not be confirmed.';
      }
    }
  };

  const startTurn = (agent, state, turn, step, humanAuthorization = false) => {
    const newLogicalExecution = state.currentTurn === null || humanAuthorization;
    clearTurnTimers(state);
    if (newLogicalExecution) {
      state.logicalStartedAt = Date.now();
      state.logicalSteps = 0;
      state.turnCalls = 0;
      state.inFlightCalls = 0;
      state.turnTokenBaseline = readTokenTotal(agent) ?? null;
      state.turnTokenUsage = 0;
      state.reportedTokenUsage = 0;
      state.hasReportedTokenUsage = false;
      state.meterHighWater = 0;
      state.changeVersion = 0;
      state.mode = 'normal';
      state.stopReason = '';
      state.cancelFailed = false;
      state.timeoutRecord = null;
      state.diagnosticCalls = 0;
      state.diagnosticStartedAt = 0;
      state.diagnosticTokenBaseline = 0;
      state.diagnosticNoticeIssued = false;
      state.noProgress = 0;
      state.lastAssistantText = '';
      state.repeatedAssistantText = false;
      state.actionCounts.clear();
      state.stagnantActionCounts.clear();
      state.actionSamples.length = 0;
      state.failureFamilyCounts.clear();
      state.failureFamilyVersion.clear();
      state.lastFailureFamily = '';
      state.lastResultByAction.clear();
      state.actionHistory.length = 0;
      state.economyNoticed = false;
      state.checkpointNoticed = false;
      state.compactNoticed = false;
    } else if (state.mode === 'idle') {
      state.mode = 'normal';
    }
    state.currentTurn = turn;
    state.currentStep = step;
    state.turnStartedAt = state.logicalStartedAt;
    state.turnActive = true;
    state.logicalSteps += 1;

    const remainingMs = Math.max(0, config.maxTurnMs - (Date.now() - state.logicalStartedAt));
    state.turnTimer = setTimeout(() => {
      if (state.currentTurn !== turn || !state.turnActive) return;
      if (state.mode !== 'normal' && state.mode !== 'diagnostic') return;
      stopTurn(
        agent,
        state,
        'CONTEXT-GUARD STOPPED: the turn exceeded its total time budget of '
          + config.maxTurnMs + 'ms; active executor work was cancelled.',
      );
    }, remainingMs);
    state.turnTimer.unref?.();
    if (state.mode === 'diagnostic' && state.diagnosticStartedAt > 0) {
      const diagnosticRemainingMs = Math.max(
        0,
        config.diagnosticMaxMs - (Date.now() - state.diagnosticStartedAt),
      );
      state.diagnosticTimer = setTimeout(() => {
        if (state.currentTurn !== turn || !state.turnActive || state.mode !== 'diagnostic') return;
        stopTurn(
          agent,
          state,
          'CONTEXT-GUARD STOPPED: diagnostic mode exceeded its reduced time budget of '
            + config.diagnosticMaxMs + 'ms; active executor work was cancelled.',
        );
      }, diagnosticRemainingMs);
      state.diagnosticTimer.unref?.();
    }
  };

  const enterDiagnostic = (agent, state, exec, result, resultFingerprint) => {
    if (state.mode === 'diagnostic') {
      stopTurn(
        agent,
        state,
        'CONTEXT-GUARD STOPPED: a second timeout occurred during diagnostic mode; the diagnostic budget was not renewed.',
      );
      return;
    }
    if (state.mode === 'stopped' || state.mode === 'paused') return;
    state.mode = 'diagnostic';
    state.diagnosticCalls = 0;
    state.diagnosticStartedAt = Date.now();
    state.diagnosticTokenBaseline = state.turnTokenUsage;
    state.diagnosticNoticeIssued = false;
    state.timeoutRecord = {
      tool: exec.name,
      identity: actionKey(exec.name, exec.arguments),
      arguments: stable(exec.arguments),
      durationMs: timeoutDuration(result),
      resultFingerprint,
      resultText: toolResultText(result, 1_600),
      changeVersion: state.changeVersion,
    };
    const turn = state.currentTurn;
    state.diagnosticTimer = setTimeout(() => {
      if (state.currentTurn !== turn || state.mode !== 'diagnostic') return;
      stopTurn(
        agent,
        state,
        'CONTEXT-GUARD STOPPED: diagnostic mode exceeded its reduced time budget of '
          + config.diagnosticMaxMs + 'ms; active executor work was cancelled.',
      );
    }, config.diagnosticMaxMs);
    state.diagnosticTimer.unref?.();
  };

  const budgetReason = (agent, state) => {
    const now = Date.now();
    if (state.turnStartedAt > 0 && now - state.turnStartedAt >= config.maxTurnMs) {
      return 'CONTEXT-GUARD STOPPED: the turn exceeded its total time budget of '
        + config.maxTurnMs + 'ms.';
    }
    if (state.turnCalls >= config.maxTurnToolCalls) {
      return 'CONTEXT-GUARD STOPPED: the turn exhausted its global tool-call budget of '
        + config.maxTurnToolCalls + '; results and the next step must be reported without another automatic call.';
    }
    const tokenUsage = updateTokenUsage(state, agent);
    if (tokenUsage !== undefined && tokenUsage >= config.maxTurnTokens) {
      return 'CONTEXT-GUARD STOPPED: the turn exhausted its global token budget of '
        + config.maxTurnTokens + ' tokens.';
    }
    if (state.mode === 'diagnostic') {
      if (now - state.diagnosticStartedAt >= config.diagnosticMaxMs) {
        return 'CONTEXT-GUARD STOPPED: diagnostic mode exceeded its reduced time budget of '
          + config.diagnosticMaxMs + 'ms.';
      }
      if (state.diagnosticCalls >= config.diagnosticMaxCalls) {
        return 'CONTEXT-GUARD STOPPED: diagnostic mode exhausted its budget of '
          + config.diagnosticMaxCalls + ' calls.';
      }
      if (tokenUsage !== undefined && tokenUsage - state.diagnosticTokenBaseline >= config.diagnosticMaxTokens) {
        return 'CONTEXT-GUARD STOPPED: diagnostic mode exhausted its reduced token budget of '
          + config.diagnosticMaxTokens + ' tokens.';
      }
    }
    return undefined;
  };

  ctx.tools.guard((exec) => {
    if (!exec.agent) return undefined;
    const state = stateFor(exec.agent);
    if (state.mode === 'idle') {
      state.mode = 'normal';
      state.turnStartedAt = Date.now();
      state.turnActive = true;
    }

    if (state.mode === 'stopped' || state.mode === 'paused') {
      return 'CONTEXT-GUARD BLOCKED: this turn is already closed by the executor. '
        + state.stopReason;
    }

    const beforeCall = budgetReason(exec.agent, state);
    if (beforeCall !== undefined) {
      stopTurn(exec.agent, state, beforeCall);
      return beforeCall;
    }
    state.turnCalls += 1;

    if (state.mode === 'diagnostic') {
      if (!hasReadOnlyCapability(exec)) {
        return 'CONTEXT-GUARD BLOCKED: diagnostic mode requires an explicit '
          + 'read-only executor capability; tool names and command text are not sufficient.';
      }
      if (
        state.timeoutRecord
        && state.timeoutRecord.identity === actionKey(exec.name, exec.arguments)
        && state.timeoutRecord.changeVersion === state.changeVersion
      ) {
        return 'CONTEXT-GUARD BLOCKED: this is the timed-out command again with no '
          + 'executor-observed code, configuration, or strategy change.';
      }
      state.diagnosticCalls += 1;
      if (state.diagnosticCalls > config.diagnosticMaxCalls) {
        const reason = 'CONTEXT-GUARD STOPPED: diagnostic mode allows only '
          + config.diagnosticMaxCalls + ' calls after a timeout.';
        stopTurn(exec.agent, state, reason);
        return reason;
      }
    }

    const args = canonical(identityArguments(exec.arguments));
    const key = String(exec.name) + '\u0000' + args;
    const stagnantAttempts = state.stagnantActionCounts.get(key) ?? 0;
    const near = state.actionSamples.some((sample) => (
      sample.name === exec.name
      && similarity(sample.args, args) >= config.textSimilarity
    ));

    const familyHint = errorFamilyHint(exec.name, exec.arguments);
    const sameToolFallback = familyHint.endsWith('|other')
      && state.lastFailureFamily.startsWith(String(exec.name).toLowerCase() + '|');
    const familyCount = (state.lastFailureFamily.startsWith(familyHint) || sameToolFallback)
      ? (state.failureFamilyCounts.get(state.lastFailureFamily) ?? 0)
      : 0;
    if (
      familyCount >= config.noProgressLimit
      && state.failureFamilyVersion.get(state.lastFailureFamily) === state.changeVersion
    ) {
      const reason = 'CONTEXT-GUARD STOPPED: ' + exec.name
        + ' produced ' + familyCount + ' equivalent failures in the '
        + state.lastFailureFamily.split('|')[1] + ' family without an observed change.';
      stopTurn(exec.agent, state, reason);
      return reason;
    }

    if (stagnantAttempts >= config.equivalentBlockLimit) {
      const reason = 'CONTEXT-GUARD STOPPED: ' + exec.name
        + ' reached ' + config.equivalentBlockLimit
        + ' equivalent attempts without a new result'
        + (near ? ' (near-equivalent calls were also observed).' : '.');
      stopTurn(exec.agent, state, reason);
      return reason;
    }
    if (state.noProgress >= config.noProgressLimit && (state.lastFailureFamily === '' || familyCount > 0)) {
      const reason = 'CONTEXT-GUARD PAUSE: ' + state.noProgress
        + ' consecutive actions produced no new executor evidence. The executor '
        + 'closed the turn; inspect the latest failure in a new user turn.'
        + (state.repeatedAssistantText ? ' Repeated assistant text was also observed.' : '');
      stopTurn(exec.agent, state, reason, 'paused');
      return reason;
    }
    state.inFlightCalls += 1;
    return undefined;
  });

  ctx.on('tools/post-execute', async (exec, result, next) => {
    if (!exec.agent) return next();
    const state = stateFor(exec.agent);
    const denied = isGuardResult(result);
    if (!denied) state.inFlightCalls = Math.max(0, state.inFlightCalls - 1);
    const downstream = await next();
    if (denied) return downstream;
    const args = canonical(identityArguments(exec.arguments));
    const key = String(exec.name) + '\u0000' + args;
    const attempts = (state.actionCounts.get(key) ?? 0) + 1;
    state.actionCounts.set(key, attempts);
    state.actionSamples.push({ name: exec.name, args });
    if (state.actionSamples.length > 32) state.actionSamples.shift();

    const fingerprint = toolResultText(result, config.resultFingerprintChars);
    const previousFingerprint = state.lastResultByAction.get(key);
    const isNewResult = previousFingerprint === undefined || previousFingerprint !== fingerprint;
    state.lastResultByAction.set(key, fingerprint);
    const family = errorFamily(exec.name, exec.arguments, result);
    if (family !== undefined) {
      const previousFamily = state.lastFailureFamily;
      const familyCount = (state.failureFamilyCounts.get(family) ?? 0) + 1;
      state.failureFamilyCounts.set(family, familyCount);
      state.failureFamilyVersion.set(family, state.changeVersion);
      state.lastFailureFamily = family;
      // Changing the wording, line, or stack of an equivalent failure does
      // not constitute progress. A different failure class starts a separate
      // bounded investigation budget.
      state.noProgress = previousFamily === family ? state.noProgress + 1 : 1;
      state.stagnantActionCounts.set(key, (state.stagnantActionCounts.get(key) ?? 0) + 1);
    } else if (isNewResult) {
      state.noProgress = 0;
      state.lastFailureFamily = '';
      state.stagnantActionCounts.set(key, 0);
    } else {
      state.noProgress += 1;
      state.stagnantActionCounts.set(key, (state.stagnantActionCounts.get(key) ?? 0) + 1);
    }
    if (
      isWorkspaceMutationCall(exec.name, exec.arguments)
      && observedMutationChange(result)
    ) {
      state.changeVersion += 1;
      state.failureFamilyCounts.clear();
      state.failureFamilyVersion.clear();
      state.stagnantActionCounts.clear();
      state.noProgress = 0;
      state.lastFailureFamily = '';
    }

    state.actionHistory.push({
      semanticKey: semanticActionKey(exec.name, exec.arguments),
      resultFingerprint: fingerprint,
      changeVersion: state.changeVersion,
    });
    if (state.actionHistory.length > 32) state.actionHistory.shift();

    if (timeoutEvidence(result, exec.name)) {
      if (state.mode === 'diagnostic') {
        stopTurn(
          exec.agent,
          state,
          'CONTEXT-GUARD STOPPED: a second timeout occurred during diagnostic mode; no budget renewal is allowed.',
        );
        return downstream;
      }
      enterDiagnostic(exec.agent, state, exec, result, fingerprint);
    }

    if (hasRepeatedCycle(state.actionHistory)) {
      stopTurn(
        exec.agent,
        state,
        'CONTEXT-GUARD STOPPED: a repeated investigation cycle was detected from '
          + 'tool sequence, referenced files, and unchanged results.',
      );
      return downstream;
    }

    const tokenUsage = updateTokenUsage(state, exec.agent);
    if (state.turnCalls >= config.maxTurnToolCalls && state.inFlightCalls === 0) {
      stopTurn(
        exec.agent,
        state,
        'CONTEXT-GUARD STOPPED: the turn exhausted its global tool-call budget of '
          + config.maxTurnToolCalls + '.',
      );
    } else if (tokenUsage !== undefined && tokenUsage >= config.maxTurnTokens) {
      stopTurn(
        exec.agent,
        state,
        'CONTEXT-GUARD STOPPED: the turn exhausted its global token budget of '
          + config.maxTurnTokens + ' tokens.',
      );
    } else if (
      state.mode === 'diagnostic'
      && state.diagnosticCalls >= config.diagnosticMaxCalls
    ) {
      stopTurn(
        exec.agent,
        state,
        'CONTEXT-GUARD STOPPED: diagnostic mode exhausted its budget of '
          + config.diagnosticMaxCalls + ' calls.',
      );
    }
    return downstream;
  });

  ctx.on('session/event', (session, event) => {
    if (event.type !== 'assistant/message') return;
    const state = sessionStates.get(String(session.id));
    if (!state) return;
    if (event.data?.turn === state.currentTurn) {
      const amount = tokenUsageAmount(event.data?.usage);
      if (amount !== undefined) {
        // Provider usage is per request. Summing it is stable across context
        // compaction, unlike the meter's current-pressure measurement.
        if (amount > 0) {
          state.reportedTokenUsage += amount;
          state.hasReportedTokenUsage = true;
          state.turnTokenUsage = Math.max(state.turnTokenUsage, state.reportedTokenUsage);
        }
      }
    }
    if (state.mode === 'stopped' || state.mode === 'paused') return;
    const text = (event.data?.message?.content ?? [])
      .filter((block) => block?.type === 'text')
      .map((block) => block.text)
      .join('\n');
    const normalized = normalizedText(text);
    if (normalized.length < 80) return;
    if (similarity(state.lastAssistantText, normalized) >= config.textSimilarity) {
      state.repeatedAssistantText = true;
      state.noProgress += 1;
    }
    state.lastAssistantText = normalized;
  });

  ctx.on('agent/pre-step', async ({ agent, signal, turn, step, messages }, next) => {
    if (!agent) return next();
    const state = stateFor(agent);
    const humanAuthorization = Array.isArray(messages)
      && messages.some((message) => message?.source?.kind === 'user');
    if (state.currentTurn !== turn || humanAuthorization) {
      startTurn(agent, state, turn, step, humanAuthorization);
    }
    state.currentStep = step;

    let reason;
    if (state.mode === 'stopped' || state.mode === 'paused') {
      reason = state.stopReason;
    } else if (state.logicalSteps > config.maxTurnSteps) {
      reason = 'CONTEXT-GUARD STOPPED: turn ' + turn
        + ' exceeded the hard limit of ' + config.maxTurnSteps + ' steps.';
    } else {
      reason = budgetReason(agent, state);
    }
    if (reason !== undefined) {
      stopTurn(agent, state, reason);
      return { kind: 'reject', reason };
    }

    const decision = await next();
    if (signal.aborted || decision?.kind === 'reject' || !Array.isArray(decision?.messages)) {
      return decision;
    }

    const totalTokens = readTokenTotal(agent);
    const tokenUsage = updateTokenUsage(state, agent);
    const injected = [];

    if (state.mode === 'diagnostic' && !state.diagnosticNoticeIssued && state.timeoutRecord) {
      state.diagnosticNoticeIssued = true;
      const record = state.timeoutRecord;
      injected.push(notice(
        'EXECUTOR DIAGNOSTIC MODE: the previous executor call reported a timeout. '
          + 'Process cleanup status is not available from this guard. Tool='
          + record.tool
          + '; duration=' + (record.durationMs ?? 'unknown')
          + 'ms; diagnostic calls remaining='
          + Math.max(0, config.diagnosticMaxCalls - state.diagnosticCalls)
          + '. The prior output is recorded immediately before this notice. '
          + 'Only bounded diagnosis is allowed; an identical rerun requires a '
          + 'real executor-observed change.',
        'diagnostic mode after executor timeout',
      ));
    } else if (totalTokens !== undefined && totalTokens >= config.compactTokens && !state.compactNoticed) {
      state.compactNoticed = true;
      injected.push(notice(
        'CONTEXT BUDGET: approximately ' + totalTokens
          + ' tokens are active. Automatic DSH compaction is due now. Preserve '
          + 'only the current objective, constraints, completed work, changed '
          + 'files, relevant results, unresolved errors, failed attempts, and '
          + 'one concrete next step.',
        'context compact due (~' + totalTokens + ' tokens)',
      ));
    } else if (totalTokens !== undefined && totalTokens >= config.checkpointTokens && !state.checkpointNoticed) {
      state.checkpointNoticed = true;
      injected.push(notice(
        'CONTEXT BUDGET: approximately ' + totalTokens
          + ' tokens. Stop rereading unchanged material and capture the failed '
          + 'approach plus the next concrete step before compaction.',
        'checkpoint preparation (~' + totalTokens + ' tokens)',
      ));
    } else if (totalTokens !== undefined && totalTokens >= config.economyTokens && !state.economyNoticed) {
      state.economyNoticed = true;
      injected.push(notice(
        'CONTEXT BUDGET: approximately ' + totalTokens
          + ' tokens. Use targeted excerpts, bounded outputs, diffs, and recent '
          + 'results; do not reread unchanged files or repeat prior investigation.',
        'economy mode (~' + totalTokens + ' tokens)',
      ));
    }

    // tokenUsage is intentionally only observed here; it never resets the
    // global call, time, or token budgets.
    void tokenUsage;
    return injected.length > 0
      ? { ...decision, messages: [...decision.messages, ...injected] }
      : decision;
  });

  ctx.on('agent/turn-stopping', ({ agent, turn }) => {
    const state = states.get(agent);
    if (!state || state.currentTurn !== turn) return;
    state.turnActive = false;
    clearTurnTimers(state);
  });

  ctx.on('agent/disposed', ({ agent }) => {
    const state = states.get(agent);
    if (!state) return;
    clearTurnTimers(state);
    states.delete(agent);
  });

  // Keep the session-owned execution state available for an agent reconnect;
  // release it only when the durable session itself is disposed.
  ctx.on('session/disposed', (session) => {
    const sessionId = session?.id;
    if (sessionId !== undefined) sessionStates.delete(String(sessionId));
  });
}
