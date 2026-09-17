/**
 * Shared context-policy math.
 *
 * The UI should edit ratios, not a second set of absolute token budgets. This
 * module is deliberately dependency-free so the host guard, the browser
 * client, and tests can use the exact same calculations.
 */

export const DEFAULT_RATIOS = Object.freeze({
  economy: 0.5,
  checkpoint: 0.625,
  compact: 0.7,
  response: 0.1875,
  summary: 0.0625,
  summaryMin: 0.0078125,
  safety: 0.03125,
  retain: 0.244140625,
});

const RATIO_FIELDS = Object.freeze([
  ['economyTokens', 'economyRatio', 'economy'],
  ['checkpointTokens', 'checkpointRatio', 'checkpoint'],
  ['compactTokens', 'compactRatio', 'compact'],
  ['responseMaxTokens', 'responseRatio', 'response'],
  ['summaryMaxTokens', 'summaryRatio', 'summary'],
  ['summaryMinTokens', 'summaryMinRatio', 'summaryMin'],
  ['safetyTokens', 'safetyRatio', 'safety'],
]);

function finiteRatio(value, fallback, label) {
  if (value === undefined) return fallback;
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0 || value >= 1) {
    throw new Error(`dsh-context-guard: ${label} must be a number between 0 and 1`);
  }
  return value;
}

function positiveInteger(value, label) {
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`dsh-context-guard: ${label} must be a positive integer`);
  }
  return value;
}

/** Resolve the ratios in one policy, using the shipped defaults when absent. */
export function normalizeRatios(raw = {}) {
  const ratios = {};
  for (const [, ratioField, name] of RATIO_FIELDS) {
    ratios[name] = finiteRatio(raw[ratioField], DEFAULT_RATIOS[name], ratioField);
  }
  ratios.retain = finiteRatio(raw.retainRatio, DEFAULT_RATIOS.retain, 'retainRatio');
  return Object.freeze(ratios);
}

/**
 * Derive absolute budgets from one context window. An explicitly supplied
 * ratio wins over a stale absolute value, which keeps Settings writes
 * authoritative while preserving backwards compatibility for YAML configs.
 */
export function deriveAbsoluteBudgets(raw = {}) {
  if (raw.contextWindow === undefined) {
    if (RATIO_FIELDS.some(([, ratioField]) => raw[ratioField] !== undefined)) {
      throw new Error('dsh-context-guard: contextWindow is required when ratio fields are used');
    }
    return { ...raw };
  }

  const contextWindow = positiveInteger(raw.contextWindow, 'contextWindow');
  const ratios = normalizeRatios(raw);
  const derived = { ...raw };
  for (const [absoluteField, ratioField, ratioName] of RATIO_FIELDS) {
    if (raw[ratioField] !== undefined) derived[absoluteField] = Math.floor(contextWindow * ratios[ratioName]);
  }
  return derived;
}

/** Convert absolute budgets back to ratios for the Settings presentation. */
export function ratiosFromBudgets(policy = {}) {
  const contextWindow = positiveInteger(policy.contextWindow, 'contextWindow');
  const ratios = {};
  for (const [absoluteField, , ratioName] of RATIO_FIELDS) {
    const value = positiveInteger(policy[absoluteField], absoluteField);
    ratios[ratioName] = value / contextWindow;
  }
  if (policy.retainTokens !== undefined) {
    ratios.retain = positiveInteger(policy.retainTokens, 'retainTokens') / contextWindow;
  } else if (policy.retainRatio !== undefined) {
    ratios.retain = finiteRatio(policy.retainRatio, DEFAULT_RATIOS.retain, 'retainRatio');
  } else {
    ratios.retain = DEFAULT_RATIOS.retain;
  }
  return Object.freeze(ratios);
}

/** Validate the cross-field invariants after all ratios are materialized. */
export function validateBudgets(policy = {}) {
  const economy = positiveInteger(policy.economyTokens, 'economyTokens');
  const checkpoint = positiveInteger(policy.checkpointTokens, 'checkpointTokens');
  const compact = positiveInteger(policy.compactTokens, 'compactTokens');
  if (!(economy < checkpoint && checkpoint < compact)) {
    throw new Error('dsh-context-guard: economyTokens < checkpointTokens < compactTokens is required');
  }

  if (policy.contextWindow !== undefined) {
    const contextWindow = positiveInteger(policy.contextWindow, 'contextWindow');
    const response = positiveInteger(policy.responseMaxTokens, 'responseMaxTokens');
    const summary = positiveInteger(policy.summaryMaxTokens, 'summaryMaxTokens');
    const summaryMin = positiveInteger(policy.summaryMinTokens, 'summaryMinTokens');
    const safety = positiveInteger(policy.safetyTokens, 'safetyTokens');
    if (summaryMin > summary) throw new Error('dsh-context-guard: summaryMinTokens must be <= summaryMaxTokens');
    if (compact + response + summary + safety >= contextWindow) {
      throw new Error('dsh-context-guard: checkpoint reserves require compactTokens + responseMaxTokens + summaryMaxTokens + safetyTokens to be < contextWindow');
    }
  }
  return true;
}
