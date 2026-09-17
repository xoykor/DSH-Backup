import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_RATIOS,
  deriveAbsoluteBudgets,
  ratiosFromBudgets,
  validateBudgets,
} from '../lib/policy.js';

test('ratios derive the same 9B budgets used by the current profile', () => {
  const policy = deriveAbsoluteBudgets({
    contextWindow: 131072,
    economyRatio: 0.5,
    checkpointRatio: 0.625,
    compactRatio: 0.7,
    responseRatio: 0.1875,
    summaryRatio: 0.0625,
    summaryMinRatio: 0.0078125,
    safetyRatio: 0.03125,
  });
  assert.deepEqual(
    Object.fromEntries(['economyTokens', 'checkpointTokens', 'compactTokens', 'responseMaxTokens', 'summaryMaxTokens', 'summaryMinTokens', 'safetyTokens'].map((key) => [key, policy[key]])),
    { economyTokens: 65536, checkpointTokens: 81920, compactTokens: 91750, responseMaxTokens: 24576, summaryMaxTokens: 8192, summaryMinTokens: 1024, safetyTokens: 4096 },
  );
  assert.equal(validateBudgets(policy), true);
});

test('the same ratios scale the 27B policy without model-specific token sliders', () => {
  const policy = deriveAbsoluteBudgets({
    contextWindow: 64000,
    economyRatio: DEFAULT_RATIOS.economy,
    checkpointRatio: DEFAULT_RATIOS.checkpoint,
    compactRatio: DEFAULT_RATIOS.compact,
    responseRatio: DEFAULT_RATIOS.response,
    summaryRatio: DEFAULT_RATIOS.summary,
    summaryMinRatio: 500 / 64000,
    safetyRatio: DEFAULT_RATIOS.safety,
  });
  assert.equal(policy.economyTokens, 32000);
  assert.equal(policy.checkpointTokens, 40000);
  assert.equal(policy.compactTokens, 44800);
  assert.equal(policy.responseMaxTokens, 12000);
  assert.equal(policy.summaryMaxTokens, 4000);
  assert.equal(policy.safetyTokens, 2000);
});

test('a ratio takes precedence over a stale absolute value', () => {
  const policy = deriveAbsoluteBudgets({ contextWindow: 64000, compactTokens: 1234, compactRatio: 0.7 });
  assert.equal(policy.compactTokens, 44800);
});

test('invalid dependent budgets fail validation', () => {
  assert.throws(
    () => validateBudgets({ economyTokens: 500, checkpointTokens: 400, compactTokens: 600 }),
    /economyTokens < checkpointTokens < compactTokens/,
  );
  assert.throws(
    () => validateBudgets({ economyTokens: 1, checkpointTokens: 2, compactTokens: 3, contextWindow: 100, responseMaxTokens: 50, summaryMaxTokens: 30, summaryMinTokens: 1, safetyTokens: 25 }),
    /compactTokens.*contextWindow/,
  );
});

test('absolute policy can be projected back to UI ratios', () => {
  const ratios = ratiosFromBudgets({
    contextWindow: 64000,
    economyTokens: 32000,
    checkpointTokens: 40000,
    compactTokens: 44800,
    responseMaxTokens: 12000,
    summaryMaxTokens: 4000,
    summaryMinTokens: 500,
    safetyTokens: 2000,
    retainTokens: 15625,
  });
  assert.equal(ratios.economy, 0.5);
  assert.equal(ratios.compact, 0.7);
  assert.equal(ratios.retain, 15625 / 64000);
});
