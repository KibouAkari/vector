import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildProviderMetric,
  measureProviderCall,
} from '../lib/provider-telemetry-core.mjs';

const runtime = {
  id: 'provider-config-A',
  provider: 'openai',
  model: 'fixture-model',
  adapter: 'openai-responses',
  apiKey: 'SECRET-NEVER-STORED',
};

test('success collects reported tokens and preserves response', async () => {
  const events = [];

  const response = {
    usage: {
      input_tokens: 12,
      output_tokens: 0,
      input_tokens_details: {
        cached_tokens: 3,
      },
    },
    output: [{ type: 'secret-private-content' }],
  };

  let time = 100;

  const result = await measureProviderCall({
    runtime,
    execute: async () => {
      time = 225;
      return response;
    },
    now: () => time,
    record: (metric) => events.push(metric),
  });

  assert.strictEqual(result, response);
  assert.equal(events[0].elapsedMs, 125);
  assert.equal(events[0].inputTokens, 12);
  assert.equal(events[0].outputTokens, 0);
  assert.equal(events[0].cachedTokens, 3);

  assert.equal(
    JSON.stringify(events).includes('SECRET'),
    false
  );

  assert.equal(
    JSON.stringify(events).includes('secret-private-content'),
    false
  );
});

test('failed request preserves original error', async () => {
  const events = [];

  const error = Object.assign(
    new Error('PRIVATE MESSAGE'),
    { status: 503 }
  );

  await assert.rejects(
    measureProviderCall({
      runtime,
      execute: async () => {
        throw error;
      },
      record: (metric) => events.push(metric),
    }),
    (caught) => caught === error
  );

  assert.equal(events[0].success, false);
  assert.equal(events[0].errorCategory, 'upstream-5xx');
  assert.equal(events[0].httpStatus, 503);

  assert.equal(
    JSON.stringify(events).includes('PRIVATE MESSAGE'),
    false
  );
});

test('recorder failure cannot affect response', async () => {
  const response = { ok: true };

  const result = await measureProviderCall({
    runtime,
    execute: async () => response,
    record: () => {
      throw new Error('database down');
    },
  });

  assert.strictEqual(result, response);
});

test('missing provider configuration is not recorded', () => {
  const metric = buildProviderMetric({
    runtime: {
      provider: 'openai',
      model: 'test',
    },
    elapsedMs: 50,
  });

  assert.equal(metric, null);
});

test('missing usage remains unknown instead of zero', () => {
  const metric = buildProviderMetric({
    runtime,
    response: {},
    elapsedMs: 10,
  });

  assert.equal(metric.inputTokens, null);
  assert.equal(metric.outputTokens, null);
});

test('negative and fractional token values are rejected', () => {
  const metric = buildProviderMetric({
    runtime,
    response: {
      usage: {
        input_tokens: -2,
        output_tokens: 1.5,
      },
    },
    elapsedMs: 1,
  });

  assert.equal(metric.inputTokens, null);
  assert.equal(metric.outputTokens, null);
});

test('rate limits and network timeouts are categorized', () => {
  const rateLimit = buildProviderMetric({
    runtime,
    error: { status: 429 },
    elapsedMs: 1,
  });

  const timeout = buildProviderMetric({
    runtime,
    error: { code: 'ETIMEDOUT' },
    elapsedMs: 1,
  });

  assert.equal(rateLimit.errorCategory, 'rate-limit');
  assert.equal(timeout.errorCategory, 'timeout');
});

test('multiple credentials remain separate', () => {
  const first = buildProviderMetric({
    runtime,
    response: {},
    elapsedMs: 1,
  });

  const second = buildProviderMetric({
    runtime: {
      ...runtime,
      id: 'provider-config-B',
    },
    response: {},
    elapsedMs: 1,
  });

  assert.notEqual(
    first.providerConfigId,
    second.providerConfigId
  );
});
