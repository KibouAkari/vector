/**
 * Model Intelligence authorization and aggregation tests.
 *
 * Real Next.js HTTP requests and isolated PostgreSQL.
 * NEVER run against the production database.
 * No provider API calls.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { readFileSync } from 'node:fs';
import pg from 'pg';

const database = new URL(
  process.env.DATABASE_URL || 'postgres://missing'
);

const origin = process.env.VECTOR_AUTHZ_TEST_ORIGIN;

if (
  process.env.CI !== 'true' ||
  !['127.0.0.1', 'localhost'].includes(database.hostname) ||
  database.pathname !== '/vector_ci' ||
  origin !== 'http://127.0.0.1:3187' ||
  !String(process.env.FILE_STORAGE_PATH || '')
    .startsWith('/tmp/vector-auth-ci-')
) {
  throw new Error(
    'Refusing to run Model Intelligence tests outside isolated CI.'
  );
}

const db = new pg.Pool({
  connectionString: process.env.DATABASE_URL,
  max: 2
});

const password = 'ci-model-intelligence-test-only';
const suffix = crypto.randomBytes(5).toString('hex');

const accounts = {
  ownerA: {
    username: `mi_owner_a_${suffix}`,
    role: 'owner'
  },
  ownerB: {
    username: `mi_owner_b_${suffix}`,
    role: 'owner'
  },
  member: {
    username: `mi_member_${suffix}`,
    role: 'member'
  }
};

async function request(route, cookie) {
  return fetch(origin + route, {
    headers: cookie ? { cookie } : {},
    cache: 'no-store',
    redirect: 'manual'
  });
}

async function seedAccount(account) {
  account.id = crypto.randomUUID();

  const salt = crypto.randomBytes(24).toString('hex');
  const hash = crypto
    .scryptSync(password, salt, 64)
    .toString('hex');

  await db.query(`
    INSERT INTO vector_users (
      id, username, password_salt,
      password_hash, role, enabled, features
    )
    VALUES ($1,$2,$3,$4,$5,TRUE,'{}'::jsonb)
  `, [
    account.id,
    account.username,
    salt,
    hash,
    account.role
  ]);

  const response = await fetch(origin + '/api/auth/login', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      username: account.username,
      password
    })
  });

  assert.equal(response.status, 200);

  const cookie = response.headers.get('set-cookie');

  assert.ok(cookie?.startsWith('vector_session='));

  account.cookie = cookie.split(';')[0];
}

async function seedProvider(account, label) {
  const id = crypto.randomUUID();

  await db.query(`
    INSERT INTO model_providers (
      id, provider, label, owner_user_id
    )
    VALUES ($1,'openai',$2,$3)
  `, [id, label, account.id]);

  return id;
}

async function seedMetric(
  providerId,
  {
    daysAgo,
    success,
    elapsedMs,
    inputTokens = null,
    outputTokens = null
  }
) {
  await db.query(`
    INSERT INTO provider_request_metrics (
      id, provider_config_id, provider,
      model, success, elapsed_ms,
      input_tokens, output_tokens, created_at
    )
    VALUES (
      $1,$2,'openai',
      'ci-fixture-model',$3,$4,
      $5,$6,
      NOW() - ($7::integer * INTERVAL '1 day')
    )
  `, [
    crypto.randomUUID(),
    providerId,
    success,
    elapsedMs,
    inputTokens,
    outputTokens,
    daysAgo
  ]);
}

async function readMetrics(account, days = 7) {
  const response = await request(
    `/api/models/intelligence?days=${days}`,
    account.cookie
  );

  assert.equal(response.status, 200);
  assert.match(
    response.headers.get('cache-control') || '',
    /no-store/
  );

  return response.json();
}

test(
  'Model Intelligence enforces owner isolation and date filtering',
  async () => {
    try {
      // Initializes the normal application identity schema.
      const anonymous = await request(
        '/api/models/intelligence?days=7'
      );

      assert.equal(anonymous.status, 401);

      for (const account of Object.values(accounts)) {
        await seedAccount(account);
      }

      const memberResponse = await request(
        '/api/models/intelligence?days=7',
        accounts.member.cookie
      );

      assert.equal(memberResponse.status, 403);

      // The route must tolerate absent telemetry storage.
      const absent = await db.query(`
        SELECT to_regclass(
          'public.provider_request_metrics'
        ) AS existing
      `);

      if (!absent.rows[0].existing) {
        const fallback = await readMetrics(accounts.ownerA);
        assert.equal(fallback.status, 'not-configured');
        assert.deepEqual(fallback.metrics, []);
      }

      // Disposable CI database only; no production migration.
      await db.query(`
        CREATE TABLE IF NOT EXISTS model_providers (
          id TEXT PRIMARY KEY,
          provider TEXT NOT NULL,
          label TEXT NOT NULL,
          owner_user_id TEXT
        )
      `);

      const migration = readFileSync(
        new URL(
          '../migrations/20261013_provider_request_metrics.sql',
          import.meta.url
        ),
        'utf8'
      );

      await db.query(migration);

      const providerA = await seedProvider(
        accounts.ownerA,
        'Owner A private'
      );

      const providerB = await seedProvider(
        accounts.ownerB,
        'Owner B private'
      );

      // Seven-day window: two observations.
      // Input-only and output-only samples are separate.
      await seedMetric(providerA, {
        daysAgo: 1,
        success: true,
        elapsedMs: 120,
        inputTokens: 10
      });

      await seedMetric(providerA, {
        daysAgo: 2,
        success: false,
        elapsedMs: 300,
        outputTokens: 3
      });

      // Included at 30 days, excluded at seven days.
      await seedMetric(providerA, {
        daysAgo: 14,
        success: true,
        elapsedMs: 200,
        inputTokens: 5,
        outputTokens: 7
      });

      // Excluded from both windows.
      await seedMetric(providerA, {
        daysAgo: 45,
        success: true,
        elapsedMs: 900,
        inputTokens: 900,
        outputTokens: 900
      });

      // Different owner — must never leak into owner A.
      await seedMetric(providerB, {
        daysAgo: 1,
        success: true,
        elapsedMs: 80,
        inputTokens: 100,
        outputTokens: 200
      });

      const a7 = await readMetrics(accounts.ownerA, 7);

      assert.equal(a7.status, 'ready');
      assert.equal(a7.days, 7);
      assert.equal(a7.metrics.length, 1);
      assert.equal(a7.metrics[0].id, providerA);
      assert.equal(a7.metrics[0].attempts, 2);
      assert.equal(a7.metrics[0].successes, 1);
      assert.equal(a7.metrics[0].averageMs, 210);
      assert.equal(a7.metrics[0].inputTokens, 10);
      assert.equal(a7.metrics[0].outputTokens, 3);
      assert.equal(a7.metrics[0].inputSamples, 1);
      assert.equal(a7.metrics[0].outputSamples, 1);

      const a30 = await readMetrics(accounts.ownerA, 30);

      assert.equal(a30.days, 30);
      assert.equal(a30.metrics.length, 1);
      assert.equal(a30.metrics[0].attempts, 3);
      assert.equal(a30.metrics[0].successes, 2);
      assert.equal(a30.metrics[0].inputTokens, 15);
      assert.equal(a30.metrics[0].outputTokens, 10);

      const b7 = await readMetrics(accounts.ownerB, 7);

      assert.equal(b7.metrics.length, 1);
      assert.equal(b7.metrics[0].id, providerB);
      assert.equal(b7.metrics[0].attempts, 1);
      assert.equal(b7.metrics[0].inputTokens, 100);

      const invalid = await readMetrics(
        accounts.ownerA,
        'invalid'
      );

      assert.equal(invalid.days, 7);
      assert.deepEqual(invalid.metrics, a7.metrics);

      // The endpoint returns aggregate data only.
      const serialized = JSON.stringify(a7);

      assert.doesNotMatch(
        serialized,
        /password_hash|api_key_encrypted|Owner B private/
      );

    } finally {
      await db.end();
    }
  }
);
