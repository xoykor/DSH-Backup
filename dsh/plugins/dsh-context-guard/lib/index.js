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
  if (typeof value === 'string') return value.trim().replace(/\s+/g, ' ');
  return value;
}

function canonical(value) {
  try {
    return JSON.stringify(stable(value));
  } catch {
    return String(value).trim().replace(/\s+/g, ' ');
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

const DIAGNOSTIC_TOOLS = new Set([
  'read',
  'read_file',
  'list_dir',
  'glob',
  'grep',
  'search',
  'find',
  'inspect',
  'get_goal',
  'get_verification_plan',
  'web_search',
  'web_fetch',
  'read_page',
  ...COMMAND_TOOLS,
]);

function isDiagnosticTool(name) {
  const normalized = String(name).toLowerCase();
  return DIAGNOSTIC_TOOLS.has(normalized)
    || /^(read|grep|search|list|glob|find|get_|inspect|web_search|web_fetch)/.test(normalized);
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
  const subjectText = String(subject).replace(/\s+/g, ' ').trim().slice(0, 240);
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
    actionSamples: [],
    seenResults: new Set(),
    actionHistory: [],
    noProgress: 0,
    lastAssistantText: '',
    repeatedAssistantText: false,
    currentTurn: null,
    currentStep: 0,
    turnStartedAt: 0,
    turnActive: false,
    turnCalls: 0,
    turnTokenBaseline: null,
    turnTokenUsage: 0,
    changeVersion: 0,
    mode: 'idle',
    stopReason: '',
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
      state = createState();
      states.set(agent, state);
      if (agent?.session?.id !== undefined) sessionStates.set(String(agent.session.id), state);
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
    const total = readTokenTotal(agent);
    if (total === undefined) return undefined;
    if (state.turnTokenBaseline === null) state.turnTokenBaseline = total;
    const usage = Math.max(0, total - state.turnTokenBaseline);
    state.turnTokenUsage = Math.max(state.turnTokenUsage, usage);
    return state.turnTokenUsage;
  };

  const stopTurn = (agent, state, reason, mode = 'stopped') => {
    if (state.mode === 'stopped' || state.mode === 'paused') return;
    state.mode = mode;
    state.stopReason = reason;
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
        // denies every subsequent tool call using the terminal state above.
      }
    }
  };

  const startTurn = (agent, state, turn, step) => {
    clearTurnTimers(state);
    state.currentTurn = turn;
    state.currentStep = step;
    state.turnStartedAt = Date.now();
    state.turnActive = true;
    state.turnCalls = 0;
    state.turnTokenBaseline = readTokenTotal(agent) ?? null;
    state.turnTokenUsage = 0;
    state.changeVersion = 0;
    state.mode = 'normal';
    state.stopReason = '';
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
    state.seenResults.clear();
    state.actionHistory.length = 0;
    state.economyNoticed = false;
    state.checkpointNoticed = false;
    state.compactNoticed = false;

    state.turnTimer = setTimeout(() => {
      if (state.currentTurn !== turn || !state.turnActive) return;
      if (state.mode !== 'normal' && state.mode !== 'diagnostic') return;
      stopTurn(
        agent,
        state,
        'CONTEXT-GUARD STOPPED: the turn exceeded its total time budget of '
          + config.maxTurnMs + 'ms; active executor work was cancelled.',
      );
    }, config.maxTurnMs);
    state.turnTimer.unref?.();
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
      if (!isDiagnosticTool(exec.name)) {
        return 'CONTEXT-GUARD BLOCKED: diagnostic mode permits only bounded '
          + 'inspection and test-diagnosis tools; this call is outside that allowlist.';
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

    if (stagnantAttempts >= config.equivalentBlockLimit) {
      const reason = 'CONTEXT-GUARD STOPPED: ' + exec.name
        + ' reached ' + config.equivalentBlockLimit
        + ' equivalent attempts without a new result'
        + (near ? ' (near-equivalent calls were also observed).' : '.');
      stopTurn(exec.agent, state, reason);
      return reason;
    }
    if (state.noProgress >= config.noProgressLimit) {
      const reason = 'CONTEXT-GUARD PAUSE: ' + state.noProgress
        + ' consecutive actions produced no new executor evidence. The executor '
        + 'closed the turn; inspect the latest failure in a new user turn.'
        + (state.repeatedAssistantText ? ' Repeated assistant text was also observed.' : '');
      stopTurn(exec.agent, state, reason, 'paused');
      return reason;
    }
    return undefined;
  });

  ctx.on('tools/post-execute', async (exec, result, next) => {
    const downstream = await next();
    if (!exec.agent || isGuardResult(result)) return downstream;
    const state = stateFor(exec.agent);
    const args = canonical(identityArguments(exec.arguments));
    const key = String(exec.name) + '\u0000' + args;
    const attempts = (state.actionCounts.get(key) ?? 0) + 1;
    state.actionCounts.set(key, attempts);
    state.actionSamples.push({ name: exec.name, args });
    if (state.actionSamples.length > 32) state.actionSamples.shift();

    const fingerprint = toolResultText(result, config.resultFingerprintChars);
    const isNewResult = !state.seenResults.has(fingerprint);
    state.seenResults.add(fingerprint);
    if (isNewResult) state.stagnantActionCounts.set(key, 0);
    else state.stagnantActionCounts.set(key, (state.stagnantActionCounts.get(key) ?? 0) + 1);
    if (
      result?.isError !== true
      && isWorkspaceMutationCall(exec.name, exec.arguments)
      && isNewResult
    ) {
      state.changeVersion += 1;
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

    if (isNewResult) {
      state.noProgress = 0;
      state.repeatedAssistantText = false;
    } else {
      state.noProgress += 1;
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
    if (state.turnCalls >= config.maxTurnToolCalls) {
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
    if (!state || state.mode === 'stopped' || state.mode === 'paused') return;
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

  ctx.on('agent/pre-step', async ({ agent, signal, turn, step }, next) => {
    if (!agent) return next();
    const state = stateFor(agent);
    if (state.currentTurn !== turn) startTurn(agent, state, turn, step);
    state.currentStep = step;

    let reason;
    if (state.mode === 'stopped' || state.mode === 'paused') {
      reason = state.stopReason;
    } else if (Number.isInteger(step) && step > config.maxTurnSteps) {
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
        'EXECUTOR DIAGNOSTIC MODE: the previous executor call timed out and its '
          + 'process cleanup completed before this state was entered. Tool='
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
}
