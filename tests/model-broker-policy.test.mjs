import test from 'node:test';
import assert from 'node:assert/strict';

import {
  rankCandidates,
  safeToRetry,
  summarizeObservations,
} from '../lib/model-broker-policy.mjs';

const model = (id, extra = {}) => ({
  id,
  provider: 'example',
  external: true,
  enabled: true,
  health: 'healthy',
  capabilities: ['text'],
  qualityEstimate: .85,
  reliabilityEstimate: .95,
  estimatedCostChf: .03,
  estimatedLatencyMs: 3000,
  ...extra,
});

test('external routing fails closed by default', () => {
  const result = rankCandidates({}, [model('external')]);
  assert.equal(result.selected, null);
});

test('sensitive inputs cannot use external models', () => {
  const result = rankCandidates(
    { sensitive: true, allowExternal: true },
    [model('external')]
  );
  assert.equal(result.selected, null);
});

test('local model can run without external permission', () => {
  const result = rankCandidates(
    {},
    [model('local', { external: false })]
  );
  assert.equal(result.selected.modelId, 'local');
});

test('permissions and capability gates', () => {
  const result = rankCandidates(
    {
      allowExternal: true,
      allowedModelIds: ['good'],
      requiredCapabilities: ['vision'],
    },
    [
      model('not-allowed', {
        capabilities: ['vision'],
      }),
      model('good', {
        capabilities: ['text'],
      }),
    ]
  );

  assert.equal(result.selected, null);
  assert.equal(result.rejected.length, 2);
});

test('budget limits and unknown prices', () => {
  const result = rankCandidates(
    { allowExternal: true, maxCostChf: .01 },
    [
      model('expensive'),
      model('unknown', {
        estimatedCostChf: null,
      }),
      model('cheap', {
        estimatedCostChf: .005,
      }),
    ]
  );

  assert.equal(result.selected.modelId, 'cheap');
  assert.equal(result.rejected.length, 2);
});

test('down and excluded providers', () => {
  const result = rankCandidates(
    {
      allowExternal: true,
      excludedProviderIds: ['blocked'],
    },
    [
      model('down', { health: 'down' }),
      model('blocked', { providerId: 'blocked' }),
      model('fine'),
    ]
  );

  assert.equal(result.selected.modelId, 'fine');
});

test('economy mode prefers cheaper model', () => {
  const result = rankCandidates(
    { allowExternal: true, preference: 'economy' },
    [
      model('premium', {
        qualityEstimate: .97,
        estimatedCostChf: .30,
      }),
      model('economy', {
        qualityEstimate: .85,
        estimatedCostChf: .005,
      }),
    ]
  );

  assert.equal(result.selected.modelId, 'economy');
});

test('telemetry changes model ranking', () => {
  const observations = summarizeObservations([
    ...Array.from({ length: 8 }, () => ({
      modelId: 'slow',
      success: false,
      latencyMs: 50000,
      costChf: .03,
    })),
    ...Array.from({ length: 8 }, () => ({
      modelId: 'fast',
      success: true,
      latencyMs: 1500,
      costChf: .03,
    })),
  ]);

  const result = rankCandidates(
    { allowExternal: true },
    [model('slow'), model('fast')],
    observations
  );

  assert.equal(result.selected.modelId, 'fast');
  assert.equal(result.selected.inputs.measured, true);
});

test('unverified quality is excluded', () => {
  const observations = summarizeObservations(
    Array.from({ length: 5 }, () => ({
      modelId: 'm',
      success: true,
      qualityScore: 1,
      latencyMs: 200,
    }))
  );

  assert.equal(observations.m.verifiedQuality, null);
  assert.equal(
    observations.m.verifiedQualitySamples,
    0
  );
});

test('latency percentiles are deterministic', () => {
  const observations = summarizeObservations(
    [100, 500, 200, 300, 400].map(
      latencyMs => ({
        modelId: 'm',
        success: true,
        latencyMs,
      })
    )
  );

  assert.equal(observations.m.p50LatencyMs, 300);
  assert.equal(observations.m.p95LatencyMs, 500);
});

test('transient errors can be retried safely', () => {
  assert.equal(
    safeToRetry({ status: 503, idempotent: true }),
    true
  );

  assert.equal(
    safeToRetry({ status: 429, idempotent: true }),
    true
  );

  assert.equal(
    safeToRetry({ errorType: 'timeout', idempotent: true }),
    true
  );
});

test('do not retry after visible side effects', () => {
  assert.equal(
    safeToRetry({
      status: 503,
      idempotent: true,
      streamedOutput: true,
    }),
    false
  );

  assert.equal(
    safeToRetry({
      status: 503,
      idempotent: true,
      sideEffectsStarted: true,
    }),
    false
  );

  assert.equal(
    safeToRetry({
      status: 503,
      idempotent: false,
    }),
    false
  );
});

test('do not retry validation or auth errors', () => {
  for (
    const status of [400, 401, 402, 403, 404, 422]
  ) {
    assert.equal(
      safeToRetry({ status, idempotent: true }),
      false
    );
  }

  assert.equal(
    safeToRetry({
      status: 503,
      idempotent: true,
      attempts: 2,
    }),
    false
  );
});

test('retry requires explicit idempotency approval', () => {
  assert.equal(safeToRetry({ status: 503 }), false);
  assert.equal(safeToRetry({ status: 429 }), false);
  assert.equal(
    safeToRetry({ status: 503, idempotent: 'true' }),
    false
  );
});


test('rejects negative configured model costs', () => {
  const result = rankCandidates(
    { allowExternal: true },
    [
      model('negative', { estimatedCostChf: -.04 }),
      model('valid', { estimatedCostChf: .02 }),
    ]
  );
  assert.equal(result.selected.modelId, 'valid');
  assert.ok(result.rejected.some(
    entry => entry.modelId === 'negative' &&
      entry.reasons.includes('invalid-cost')
  ));
});

test('rejects negative observed cost before ranking', () => {
  const result = rankCandidates(
    { allowExternal: true },
    [model('invalid'), model('valid')],
    { invalid: { sampleCount: 6, meanCostChf: -.03 } }
  );
  assert.equal(result.selected.modelId, 'valid');
  assert.ok(result.rejected.some(
    entry => entry.modelId === 'invalid' &&
      entry.reasons.includes('invalid-cost')
  ));
});

test('only allowlisted transient HTTP statuses can retry', () => {
  for (const status of [429, 502, 503, 504]) {
    assert.equal(safeToRetry({ status, idempotent: true }), true);
  }
  for (const status of [400, 401, 408, 500, 501, 505, 507, 508, 520, 599]) {
    assert.equal(safeToRetry({ status, idempotent: true }), false);
  }
  assert.equal(safeToRetry({ status: 503 }), false);
  assert.equal(safeToRetry({ status: 503, idempotent: true, streamedOutput: true }), false);
});
