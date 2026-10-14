import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  canViewModelIntelligence,
  modelIntelligenceRows
} from '../lib/model-intelligence-summary.mjs';

const owned = {
  id: 'a',
  credential_scope: 'personal',
  label: 'My OpenAI',
  provider: 'openai',
  enabled: true,
  api_key_encrypted: 'secret'
};

const shared = {
  id: 'b',
  credential_scope: 'workspace',
  label: 'Other',
  provider: 'anthropic',
  enabled: true
};

test('dashboard is owner-only', () => {
  assert.equal(
    canViewModelIntelligence({
      userId: '1',
      role: 'owner'
    }),
    true
  );

  assert.equal(
    canViewModelIntelligence({
      userId: '1',
      role: 'member'
    }),
    false
  );

  assert.equal(
    canViewModelIntelligence({
      role: 'owner'
    }),
    false
  );
});

test('only owned connections and allowed metadata', () => {
  const result = modelIntelligenceRows(
    [owned, shared],
    [
      { id: 'a', attempts: 2, successes: 1 },
      { id: 'b', attempts: 200, successes: 200 }
    ]
  );

  assert.equal(result.length, 1);
  assert.equal(result[0].successRate, 50);

  assert.doesNotMatch(
    JSON.stringify(result),
    /secret|Other/
  );
});

test('missing metrics do not fabricate reliability', () => {
  const result = modelIntelligenceRows(
    [owned],
    []
  );

  assert.equal(result[0].attempts, 0);
  assert.equal(result[0].successRate, null);
  assert.equal(result[0].inputTokens, null);
});

test('zero success differs from unknown', () => {
  const result = modelIntelligenceRows(
    [owned],
    [{
      id: 'a',
      attempts: 4,
      successes: 0,
      inputTokens: 0,
      inputSamples: 4
    }]
  );

  assert.equal(result[0].successRate, 0);
  assert.equal(result[0].inputTokens, 0);
});

test('API filters by owner and contains no writes', () => {
  const route = readFileSync(
    new URL(
      '../app/api/models/intelligence/route.js',
      import.meta.url
    ),
    'utf8'
  );

  assert.match(
    route,
    /canViewModelIntelligence\(session\)/
  );

  assert.match(
    route,
    /p\.owner_user_id = \$1/
  );

  assert.match(
    route,
    /JOIN model_providers p\s+ON p\.id = m\.provider_config_id/
  );

  assert.doesNotMatch(
    route,
    /INSERT INTO|UPDATE model_providers|DELETE FROM/
  );
});
