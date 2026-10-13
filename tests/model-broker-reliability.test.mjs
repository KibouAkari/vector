import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  normalizedOpenAiUsage,
  normalizedAnthropicUsage,
} from '../lib/provider-usage-normalization.mjs';

import { safeToRetry } from '../lib/model-broker-policy.mjs';
import {
  compareProviderCandidates,
} from '../lib/model-broker-shadow.mjs';
import {
  buildProviderMetric,
} from '../lib/provider-telemetry-core.mjs';

const source = path =>
  readFileSync(new URL(path, import.meta.url), 'utf8');

const candidate = (id, provider, quality = 80) => ({
  runtime: {
    id,
    provider,
    model: 'fixture',
    benchmarkProfile: {
      scores: { general: quality },
      reliability: 90,
    },
  },
});

test('HTTP status cannot be bypassed by errorType', () => {
  for (const status of [400, 401, 500, 501, 505, 599]) {
    assert.equal(
      safeToRetry({
        status,
        errorType: 'timeout',
        idempotent: true,
      }),
      false
    );
  }

  assert.equal(
    safeToRetry({
      status: 503,
      errorType: 'timeout',
      idempotent: true,
    }),
    true
  );

  assert.equal(
    safeToRetry({
      errorType: 'timeout',
      idempotent: true,
    }),
    true
  );

  assert.equal(
    safeToRetry({
      status: '503',
      errorType: 'timeout',
      idempotent: true,
    }),
    false
  );
});

test('Perplexity provider family is recognized', () => {
  const result = compareProviderCandidates({
    candidates: [
      candidate('p', 'perplexity', 95),
      candidate('o', 'openai', 60),
    ],
  });

  assert.equal(result.status, 'compared');
  assert.equal(result.legacyFamily, 'perplexity');
});

test('profileless alternatives are skipped', () => {
  const result = compareProviderCandidates({
    candidates: [
      candidate('a', 'openai', 70),
      {
        runtime: {
          id: 'custom',
          provider: 'custom',
          model: 'm',
        },
      },
      candidate('b', 'anthropic', 95),
    ],
  });

  assert.equal(result.status, 'compared');
  assert.equal(result.candidateCount, 2);
});

test('legacy winner without profile is not compared', () => {
  const result = compareProviderCandidates({
    candidates: [
      {
        runtime: {
          id: 'custom',
          provider: 'custom',
          model: 'm',
        },
      },
      candidate('a', 'openai'),
      candidate('b', 'anthropic'),
    ],
  });

  assert.equal(result.status, 'insufficient-data');
});

test('shadow resolver requires background opt-in', () => {
  const resolver = source('../lib/model-config.js');
  const background = source('../lib/background-executor.js');

  assert.match(resolver, /shadowComparison = false/);
  assert.match(resolver, /shadowComparison === true/);
  assert.match(background, /shadowComparison:\s+true/);
});

test('provider adapters distinguish absent usage from an explicit zero', () => {
  const runtime = {
    id: 'config-1',
    provider: 'openai',
    model: 'fixture',
  };

  for (const [adapter, normalize, raw] of [
    ['OpenAI-compatible', normalizedOpenAiUsage, {
      completion_tokens: 0,
    }],
    ['OpenAI Responses', normalizedOpenAiUsage, {
      output_tokens: 0,
    }],
    ['Anthropic', normalizedAnthropicUsage, {
      output_tokens: 0,
    }],
  ]) {
    const usage = normalize(raw);
    const metric = buildProviderMetric({
      runtime,
      response: { usage },
      elapsedMs: 5,
    });

    assert.equal(metric.inputTokens, null, adapter);
    assert.equal(metric.outputTokens, 0, adapter);
    assert.equal(metric.cachedTokens, null, adapter);
    assert.equal(usage.input_tokens, 0, adapter);

    assert.doesNotMatch(
      JSON.stringify(usage),
      /__vectorTelemetryPresence/,
      adapter
    );
  }
});

test('OpenAI usage preserves explicit zero and native cached tokens', () => {
  const usage = normalizedOpenAiUsage({
    prompt_tokens: 0,
    input_tokens: 99,
    completion_tokens: 0,
    output_tokens: 50,
    prompt_tokens_details: {
      cached_tokens: 0,
    },
    cache_read_input_tokens: 11,
  });
  assert.equal(usage.input_tokens, 0);
  assert.equal(usage.output_tokens, 0);
  assert.equal(usage.input_tokens_details.cached_tokens, 0);

  const native = normalizedOpenAiUsage({
    input_tokens: 12,
    output_tokens: 3,
    input_tokens_details: { cached_tokens: 7 },
  });
  const metric = buildProviderMetric({
    runtime: {
      id: 'config-1',
      provider: 'openai',
      model: 'fixture',
    },
    response: { usage: native },
    elapsedMs: 7,
  });
  assert.equal(metric.inputTokens, 12);
  assert.equal(metric.outputTokens, 3);
  assert.equal(metric.cachedTokens, 7);
});

test('production adapters use the tested normalization functions', () => {
  const runtime = source('../lib/provider-runtime.js');

  assert.match(
    runtime,
    /from "\.\/provider-usage-normalization\.mjs"/
  );
  assert.match(runtime, /normalizedOpenAiUsage\(\s*body\.usage/);
  assert.match(
    runtime,
    /normalizedAnthropicUsage\(response\.usage\)/
  );
});

test('HTTP errors and telemetry pool are isolated', () => {
  const runtime = source('../lib/provider-runtime.js');
  const telemetry = source('../lib/provider-telemetry.js');

  assert.match(
    runtime,
    /throw Object\.assign\(new Error\(message\),\s*\{\s*status: response\.status/
  );

  assert.match(
    runtime,
    /lastError = Object\.assign\(new Error\(message\),\s*\{\s*status: response\.status/
  );

  assert.match(telemetry, /max: 1/);
  assert.match(telemetry, /MAX_IN_FLIGHT = 1/);

  assert.doesNotMatch(
    telemetry,
    /import \{ db \} from '\.\/db'/
  );
});
