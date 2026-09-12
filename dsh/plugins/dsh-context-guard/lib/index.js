/**
 * Model-independent loop protection for DSH tool execution.
 *
 * The plugin intentionally depends only on the public Cordis context passed to
 * `apply()`: it works with native DSH agents and relay-backed agents alike.
 */
export const name = 'dsh-context-guard';
// Cordis rejects undeclared context services at plugin load. Both are built-in
// DSH services present in the base bundle and make the guard fail closed if a
// profile cannot supply the required deterministic enforcement seams.
export const inject = ['tools', 'tokenMeter'];

const DEFAULTS = Object.freeze({
  economyTokens: 20_000,
  checkpointTokens: 25_000,
  compactTokens: 30_000,
  noProgressLimit: 3,
  equivalentBlockLimit: 5,
  textSimilarity: 0.94,
  resultFingerprintChars: 4_000,
});

function positiveInteger(value, fallback, label) {
  if (value === undefined) return fallback;
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`dsh-context-guard: ${label} must be a positive integer`);
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
    textSimilarity: raw.textSimilarity ?? DEFAULTS.textSimilarity,
    resultFingerprintChars: positiveInteger(raw.resultFingerprintChars, DEFAULTS.resultFingerprintChars, 'resultFingerprintChars'),
  };
  if (!(config.economyTokens < config.checkpointTokens && config.checkpointTokens < config.compactTokens)) {
    throw new Error('dsh-context-guard: economyTokens < checkpointTokens < compactTokens is required');
  }
  if (config.equivalentBlockLimit < config.noProgressLimit) {
    throw new Error('dsh-context-guard: equivalentBlockLimit must be >= noProgressLimit');
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
  const text = blocks.map((block) => {
    if (block?.type === 'text') return block.text;
    try { return JSON.stringify(block); } catch { return String(block); }
  }).join('\n');
  return `${result?.isError === true ? 'error:' : 'ok:'}${text.slice(0, cap)}`;
}

function isMutation(name) {
  return /(?:write|edit|patch|replace|apply|create|delete|rename|move|install|format)/i.test(name);
}

function isGuardResult(result) {
  return result?.isError === true && toolResultText(result, 300).includes('CONTEXT-GUARD');
}

function notice(text, summary) {
  return Object.freeze({
    id: `context-guard-${crypto.randomUUID()}`,
    role: 'user',
    content: Object.freeze([Object.freeze({ type: 'text', text })]),
    source: Object.freeze({ kind: 'plugin', plugin: name, form: 'notice', summary }),
  });
}

function createState() {
  return {
    actionCounts: new Map(),
    actionSamples: [],
    seenResults: new Set(),
    noProgress: 0,
    lastAssistantText: '',
    repeatedAssistantText: false,
    reassessmentIssued: false,
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

  const signalProgress = (state) => {
    state.noProgress = 0;
    state.repeatedAssistantText = false;
    state.reassessmentIssued = false;
  };

  ctx.tools.guard((exec) => {
    if (!exec.agent) return undefined;
    const state = stateFor(exec.agent);
    const args = canonical(exec.arguments);
    const key = `${exec.name}\u0000${args}`;
    const exactAttempts = state.actionCounts.get(key) ?? 0;
    const near = state.actionSamples.some((sample) => sample.name === exec.name && similarity(sample.args, args) >= config.textSimilarity);

    if (exactAttempts >= config.equivalentBlockLimit) {
      return `CONTEXT-GUARD BLOCKED: ${exec.name} has already been attempted ${exactAttempts} times with equivalent arguments and no newly observed result. This approach is blocked. Record it as failed, inspect the latest result, and choose a materially different diagnostic or stop with the concrete blocker.`;
    }
    if (state.noProgress >= config.noProgressLimit && !state.reassessmentIssued) {
      state.reassessmentIssued = true;
      return `CONTEXT-GUARD PAUSE: ${state.noProgress} consecutive actions produced no significant progress${state.repeatedAssistantText ? ', with repeated assistant text' : ''}${near ? ', and this call is near an earlier call' : ''}. Do not execute another action yet. Reassess the evidence, state the failed approach concisely, then use a materially different safe strategy or report the blocker.`;
    }
    return undefined;
  });

  ctx.on('tools/post-execute', async (exec, result, next) => {
    const downstream = await next();
    if (!exec.agent || isGuardResult(result)) return downstream;
    const state = stateFor(exec.agent);
    const args = canonical(exec.arguments);
    const key = `${exec.name}\u0000${args}`;
    const attempts = (state.actionCounts.get(key) ?? 0) + 1;
    state.actionCounts.set(key, attempts);
    state.actionSamples.push({ name: exec.name, args });
    if (state.actionSamples.length > 32) state.actionSamples.shift();

    const fingerprint = toolResultText(result, config.resultFingerprintChars);
    const isNewResult = !state.seenResults.has(fingerprint);
    state.seenResults.add(fingerprint);
    if (state.seenResults.size > 128) state.seenResults.clear();

    // A successful mutation, a new diagnostic/error/result, or a newly observed
    // state can advance the task. Repeating an unchanged read/command cannot.
    const progressed = (result?.isError !== true && isMutation(exec.name) && isNewResult) || isNewResult;
    if (progressed) signalProgress(state);
    else state.noProgress += 1;
    return downstream;
  });

  ctx.on('session/event', (session, event) => {
    if (event.type !== 'assistant/message') return;
    const state = sessionStates.get(String(session.id));
    if (!state) return;
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

  ctx.on('agent/pre-step', async ({ agent, signal }, next) => {
    const decision = await next();
    if (signal.aborted || !Array.isArray(decision?.messages)) return decision;
    const meter = ctx.tokenMeter;
    if (!meter || !agent?.session) return decision;
    let tokens;
    try {
      tokens = meter.measure(agent.session).totalTokens;
    } catch {
      return decision;
    }
    const state = stateFor(agent);
    let injected;
    if (tokens >= config.compactTokens && !state.compactNoticed) {
      state.compactNoticed = true;
      injected = notice(
        `CONTEXT BUDGET: approximately ${tokens} tokens are active. Automatic DSH compaction is due now. Preserve only the current objective, user constraints, completed work, decisions, changed files, relevant commands/results, unresolved errors, failed attempts, project state, and one concrete next step. Continue from the checkpoint after compaction; do not reconstruct old output.`,
        `context compact due (~${tokens} tokens)`,
      );
    } else if (tokens >= config.checkpointTokens && !state.checkpointNoticed) {
      state.checkpointNoticed = true;
      injected = notice(
        `CONTEXT BUDGET: approximately ${tokens} tokens. Checkpoint preparation mode is active. Stop rereading unchanged material, capture failed approaches and the next concrete step, and make remaining actions compact so automatic compaction at about ${config.compactTokens} tokens can resume safely.`,
        `checkpoint preparation (~${tokens} tokens)`,
      );
    } else if (tokens >= config.economyTokens && !state.economyNoticed) {
      state.economyNoticed = true;
      injected = notice(
        `CONTEXT BUDGET: approximately ${tokens} tokens. Economy mode is active: use targeted excerpts, bounded outputs, diffs, and recent results; do not reread unchanged files or repeat prior investigation.`,
        `economy mode (~${tokens} tokens)`,
      );
    }
    return injected ? { ...decision, messages: [...decision.messages, injected] } : decision;
  });
}
