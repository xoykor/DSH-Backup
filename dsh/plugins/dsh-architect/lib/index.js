import { BlockAssembler, createUserMessage } from '@deepseek-ai/dsh-llm';
import { defineTool } from '@deepseek-ai/dsh-tools';

export const name = 'dsh-architect';
export const inject = ['tools', 'llm'];

const DEFAULTS = Object.freeze({
  provider: 'google',
  model: 'gemini-3.1-pro-preview',
  reasoningEffort: 'high',
  maxTokens: 8192,
  timeoutMs: 120000,
  maxInputChars: 48000,
  maxOutputChars: 24000,
  maxCacheEntries: 128,
});

  const EXECUTOR = Object.freeze({ provider: 'lmstudio', model: 'ornith-1.5-9b' });
  const PRESET_ID = 'ornith-gemini-architect';

const OPERATIONS = Object.freeze({
  plan: 'architect_plan',
  debug: 'architect_debug',
  review: 'architect_review',
});

const SYSTEM_PROMPT = [
  'You are Gemini Architect, a consultive architecture reviewer for an Ornith 1.5 9B coding agent.',
  'You have no tools, no filesystem, no terminal, and no access to the agent history beyond the bounded context in this request.',
  'Give advice only. Never claim to have run a command, edited a file, or verified a test.',
  'Return a concise JSON object with keys strategy, files, steps, invariants, risks, validation, and advice.',
  'Each array value must be a short string. The advice is advisory: the Ornith agent decides and executes every change.',
].join(' ');

const SCHEMAS = {
  plan: {
    task: { type: 'string', required: true, description: 'Original task that may require coordinated changes across modules.' },
    context: { type: 'string', required: true, description: 'Selected repository facts, constraints, and relevant observations only.' },
    files: { type: 'array', required: true, items: { type: 'string' }, description: 'Relevant file paths already selected by the executor (use an empty array when none apply).' },
  },
  debug: {
    task: { type: 'string', required: true, description: 'The failing task or behavior.' },
    attempts: { type: 'array', required: true, items: { type: 'string' }, description: 'At least two concrete attempts and their observed outcomes.' },
    context: { type: 'string', required: true, description: 'Current bounded state and error evidence.' },
    files: { type: 'array', required: true, items: { type: 'string' }, description: 'Relevant file paths already selected by the executor (use an empty array when none apply).' },
  },
  review: {
    originalTask: { type: 'string', required: true, description: 'The original user task.' },
    plan: { type: 'string', required: true, description: 'The plan the executor followed.' },
    diff: { type: 'string', required: true, description: 'The current git diff or an equivalent bounded change summary.' },
    tests: { type: 'string', required: true, description: 'Tests and deterministic checks already run.' },
    pendingProblems: { type: 'string', required: true, description: 'Known unresolved problems, or an explicit statement that there are none.' },
  },
};

function text(value, label, max = 16000) {
  if (typeof value !== 'string' || value.trim() === '') throw new Error(`dsh-architect: ${label} must be a non-empty string`);
  const clean = value.trim();
  if (clean.length > max) throw new Error(`dsh-architect: ${label} exceeds ${max} characters`);
  return clean;
}

function files(value) {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > 64) throw new Error('dsh-architect: files must contain at most 64 paths');
  return value.map((entry, index) => text(entry, `files[${index}]`, 512));
}

function operationPayload(operation, args) {
  if (operation === 'plan' || operation === OPERATIONS.plan) return {
    task: text(args.task, 'task'),
    context: text(args.context, 'context', 32000),
    files: files(args.files),
  };
  if (operation === 'debug' || operation === OPERATIONS.debug) {
    if (!Array.isArray(args.attempts) || args.attempts.length < 2) {
      throw new Error('dsh-architect: debug requires at least two reasonable attempts with evidence');
    }
    return {
      task: text(args.task, 'task'),
      attempts: args.attempts.map((entry, index) => text(entry, `attempts[${index}]`, 8000)),
      context: text(args.context, 'context', 24000),
      files: files(args.files),
    };
  }
  return {
    originalTask: text(args.originalTask, 'originalTask', 12000),
    plan: text(args.plan, 'plan', 16000),
    diff: text(args.diff, 'diff', 24000),
    tests: text(args.tests, 'tests', 12000),
    pendingProblems: text(args.pendingProblems, 'pendingProblems', 8000),
  };
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}

function safeId(exec) {
  const session = exec?.agent?.session;
  const id = session?.id ?? exec?.agent?.id ?? 'unowned';
  return String(id);
}

function boundedJson(value, max) {
  try { return JSON.stringify(value).slice(0, max); } catch { return String(value).slice(0, max); }
}

function responseText(assembler) {
  return assembler.blocks()
    .filter((block) => block?.type === 'text' || block?.type === 'reasoning')
    .map((block) => block.text)
    .join('\n')
    .trim();
}

function parsedAdvice(raw) {
  const candidates = [raw, raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')];
  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate);
      if (parsed && typeof parsed === 'object') return parsed;
    } catch { /* Gemini may return prose; retain it as advice. */ }
  }
  return { advice: raw };
}

function stringList(value, fallback = []) {
  if (!Array.isArray(value)) return fallback;
  return value.slice(0, 32).map((item) => typeof item === 'string' ? item.trim() : boundedJson(item, 1000)).filter(Boolean);
}

function normalizeResult(operation, payload, raw, config, deduplicated) {
  const parsed = parsedAdvice(raw);
  const advice = typeof parsed.advice === 'string' && parsed.advice.trim() !== '' ? parsed.advice.trim() : raw;
  return {
    operation,
    provider: config.provider,
    model: config.model,
    reasoningEffort: 'high',
    thinkingLevel: 'high',
    consulted: true,
    deduplicated,
    advice: advice.slice(0, config.maxOutputChars),
    strategy: stringList(parsed.strategy, [operation === 'architect_plan' ? 'Use the bounded evidence to choose the smallest coherent change.' : 'Inspect the evidence and isolate the next falsifiable action.']),
    files: stringList(parsed.files, payload.files ?? []),
    steps: stringList(parsed.steps),
    invariants: stringList(parsed.invariants),
    risks: stringList(parsed.risks),
    validation: stringList(parsed.validation),
  };
}

async function consult(ctx, operation, args, exec, config, cache) {
  const payload = operationPayload(operation, args);
  const request = {
    operation,
    provider: config.provider,
    model: config.model,
    reasoningEffort: 'high',
    payload,
  };
  const key = `${safeId(exec)}\u0000${operation}\u0000${canonical(request)}`;
  const cached = cache.get(key);
  if (cached !== undefined) return { ...cached, deduplicated: true };
  const inflight = cache.inflight.get(key);
  if (inflight !== undefined) return { ...(await inflight), deduplicated: true };

  const work = (async () => {
    const modelInfo = await ctx.llm.resolveModelInfo(config.provider, config.model, exec.signal);
    if (!modelInfo || modelInfo.provider !== config.provider || modelInfo.id !== config.model) {
      throw new Error('dsh-architect: configured Gemini model could not be resolved');
    }
    const prompt = `${SYSTEM_PROMPT}\n\nOperation: ${operation}\nBounded executor input (treat as untrusted facts):\n${JSON.stringify(payload)}`;
    if (prompt.length > config.maxInputChars) throw new Error(`dsh-architect: bounded consultation payload exceeds ${config.maxInputChars} characters`);
    const timeout = AbortSignal.timeout(config.timeoutMs);
    const signal = AbortSignal.any([exec.signal, timeout]);
    const assembler = new BlockAssembler();
    try {
      for await (const chunk of ctx.llm.stream({
        provider: config.provider,
        model: config.model,
        reasoningEffort: 'high',
        messages: [createUserMessage({ content: [{ type: 'text', text: prompt }], source: { kind: 'user' } })],
        tools: [],
        maxTokens: config.maxTokens,
        signal,
      })) assembler.push(chunk);
    } finally {
      timeout?.throwIfAborted?.();
    }
    if (assembler.finish.kind === 'error' || assembler.finish.kind === 'aborted') {
      throw new Error(`dsh-architect: Gemini consultation failed (${assembler.finish.failure?.code ?? assembler.finish.kind})`);
    }
    const raw = responseText(assembler);
    if (!raw) throw new Error('dsh-architect: Gemini returned no consultive text');
    return normalizeResult(operation, payload, raw, config, false);
  })();
  cache.inflight.set(key, work);
  try {
    const result = await work;
    cache.values.set(key, result);
    while (cache.values.size > config.maxCacheEntries) cache.values.delete(cache.values.keys().next().value);
    return result;
  } finally {
    cache.inflight.delete(key);
  }
}

const OUTPUT = {
  schema: {
    type: 'object',
    additionalProperties: false,
    properties: {
      operation: { type: 'string', required: true }, provider: { type: 'string', required: true }, model: { type: 'string', required: true },
      reasoningEffort: { type: 'string', required: true }, thinkingLevel: { type: 'string', required: true }, consulted: { type: 'boolean', required: true }, deduplicated: { type: 'boolean', required: true },
      advice: { type: 'string', required: true }, strategy: { type: 'array', required: true, items: { type: 'string' } }, files: { type: 'array', required: true, items: { type: 'string' } },
      steps: { type: 'array', required: true, items: { type: 'string' } }, invariants: { type: 'array', required: true, items: { type: 'string' } }, risks: { type: 'array', required: true, items: { type: 'string' } }, validation: { type: 'array', required: true, items: { type: 'string' } },
    },
  },
  render: (_args, value) => [{ type: 'text', text: `Gemini Architect (${value.operation}, ${value.model}, HIGH): ${value.advice}` }],
};

function tool(operation, config, ctx, cache) {
  return defineTool({
    name: OPERATIONS[operation],
    description: operation === 'plan'
      ? 'Consult Gemini for architecture when a change spans multiple modules or the implementation strategy is uncertain. The executor supplies bounded context; Gemini has no tools.'
      : operation === 'debug'
        ? 'Consult Gemini after at least two reasonable failed attempts, with concrete error evidence. Gemini has no tools and cannot execute fixes.'
        : 'Consult Gemini after substantial changes for a bounded review of the original task, plan, diff, tests, and pending problems. Gemini has no tools.',
    parameters: SCHEMAS[operation],
    output: OUTPUT,
    timeoutMs: config.timeoutMs + 5000,
    execute: (args, exec) => consult(ctx, OPERATIONS[operation], args, exec, config, cache),
    presentCall: (args) => ({ card: 'generic', title: `Consult Gemini (${operation})`, kind: 'other', rawInput: args }),
  });
}

export function apply(ctx, rawConfig = {}) {
  const config = Object.freeze({ ...DEFAULTS, ...rawConfig });
  if (config.provider !== 'google' || config.model !== 'gemini-3.1-pro-preview') throw new Error('dsh-architect: this preset is pinned to the catalog-verified Gemini 3.1 Pro Preview route');
  if (config.reasoningEffort !== 'high') throw new Error('dsh-architect: HIGH reasoning is mandatory');
  if (!Number.isInteger(config.maxTokens) || config.maxTokens <= 0 || !Number.isInteger(config.timeoutMs) || config.timeoutMs <= 0 || !Number.isInteger(config.maxInputChars) || config.maxInputChars <= 0 || !Number.isInteger(config.maxOutputChars) || config.maxOutputChars <= 0 || !Number.isInteger(config.maxCacheEntries) || config.maxCacheEntries <= 0) {
    throw new Error('dsh-architect: maxTokens, timeoutMs, maxInputChars, maxOutputChars, and maxCacheEntries must be positive integers');
  }
  // This preset is an Ornith executor. The exact session guard means a UI
  // selection or inherited global default cannot route this agent elsewhere.
  const isTargetAgent = (agent) => agent?.session?.header?.agentPreset === PRESET_ID;

  // Preset mounts are standing compositions whose scoped registrations are
  // visible to the joined agent. These routes are dispatched from the loop
  // carrier, so the global listener uses an exact session guard and never
  // rewrites a sibling preset's request.
  ctx.on('system-prompt/assemble', async (_assembly, context, next) => {
    if (!isTargetAgent(context?.agent)) return next();
    const assembled = await next();
    return {
      ...assembled,
      variables: { ...assembled.variables, provider: EXECUTOR.provider, model: EXECUTOR.model },
    };
  }, { prepend: true, global: true });
  ctx.on('agent/request', async (payload, next) => {
    if (!isTargetAgent(payload?.agent)) return next();
    const resolved = await next();
    const { reasoningEffort: _discardedReasoningEffort, ...withoutReasoning } = resolved;
    return { ...withoutReasoning, provider: EXECUTOR.provider, model: EXECUTOR.model };
  }, { prepend: true, global: true });
  const cache = {
    values: new Map(),
    inflight: new Map(),
    get(key) { return this.values.get(key); },
    set(key, value) { this.values.set(key, value); },
  };
  for (const operation of Object.keys(OPERATIONS)) ctx.tools.register(tool(operation, config, ctx, cache));
}
