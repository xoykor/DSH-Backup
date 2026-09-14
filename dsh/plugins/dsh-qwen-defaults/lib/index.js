/**
 * Make the Qwen thinking defaults explicit at the DSH request boundary.
 *
 * DSH's provider-neutral request contract exposes temperature, maxTokens, and
 * stop. The local Qwen model uses LM Studio's OpenAI-compatible Responses
 * reasoning levels; the profile owns the model-specific level mapping. The
 * remaining sampling controls are owned by the backend.
 */
export const name = 'dsh-qwen-defaults';

const PROVIDER = 'lmstudio';
const MODEL = 'qwen3.8-27b-gsq-rco';
const TEMPERATURE = 1.0;
const REASONING_EFFORT = 'high';

export function apply(ctx) {
  ctx.on('agent/request', async (payload, next) => {
    let resolved = await next();
    const presets = ctx.get?.('agentPresets') ?? ctx.agentPresets;
    if (presets?.composedPreset(payload.agent?.ctx) === 'local-robust-27b') {
      resolved = { ...resolved, provider: PROVIDER, model: MODEL,
        maxTokens: Math.min(resolved.maxTokens ?? 12000, 12000) };
    }
    if (resolved.provider !== PROVIDER || resolved.model !== MODEL) {
      return resolved;
    }
    return {
      ...resolved,
      ...(resolved.temperature === undefined ? { temperature: TEMPERATURE } : {}),
      ...(resolved.reasoningEffort === undefined ? { reasoningEffort: REASONING_EFFORT } : {}),
    };
  });
}
