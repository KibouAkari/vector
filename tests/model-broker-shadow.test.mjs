import test from 'node:test';
import assert from 'node:assert/strict';

import {
  compareProviderCandidates,
} from '../lib/model-broker-shadow.mjs';

const candidate = (id, provider, quality, score = 0) => ({
  score,
  runtime: {
    id,
    provider,
    model: 'fixture-model',
    benchmarkProfile: {
      scores: { general: quality },
      reliability: 90,
    },
    apiKey: 'never-log-or-use-this',
  },
});

test('comparison does not mutate existing candidates', () => {
  const candidates = [
    candidate('a', 'openai', 55, 100),
    candidate('b', 'anthropic', 95, 90),
  ];

  const before = JSON.stringify(candidates);

  const result = compareProviderCandidates({
    candidates,
  });

  assert.equal(JSON.stringify(candidates), before);
  assert.equal(result.status, 'compared');
  assert.equal(result.agreement, false);
  assert.equal(result.legacyFamily, 'openai');
  assert.equal(result.shadowFamily, 'anthropic');

  assert.equal(
    JSON.stringify(result).includes('apiKey'),
    false
  );
});

test('recognizes when both selections agree', () => {
  const result = compareProviderCandidates({
    candidates: [
      candidate('a', 'openai', 95),
      candidate('b', 'anthropic', 55),
    ],
  });

  assert.equal(result.agreement, true);
});

test('respects explicit user provider preference', () => {
  const result = compareProviderCandidates({
    candidates: [
      candidate('a', 'openai', 50),
      candidate('b', 'anthropic', 90),
    ],
    preferredProviderId: 'a',
  });

  assert.equal(result.status, 'skipped');
});

test('rejects incomplete comparison evidence', () => {
  const result = compareProviderCandidates({
    candidates: [
      candidate('a', 'openai', 80),
      {
        runtime: {
          id: 'b',
          provider: 'google',
          model: 'm',
        },
      },
    ],
  });

  assert.equal(result.status, 'insufficient-data');
});

test('requires multiple candidates', () => {
  const result = compareProviderCandidates({
    candidates: [
      candidate('a', 'openai', 80),
    ],
  });

  assert.equal(result.status, 'insufficient-data');
});
