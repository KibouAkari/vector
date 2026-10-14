import { getSession } from '../../../../lib/auth';
import { db } from '../../../../lib/db';

import {
  canViewModelIntelligence
} from '../../../../lib/model-intelligence-summary.mjs';

export const dynamic = 'force-dynamic';

const PRIVATE = {
  'Cache-Control': 'private, no-store'
};

const json = (body, status = 200) =>
  Response.json(body, {
    status,
    headers: PRIVATE
  });

/**
 * Read-only, owner-scoped telemetry.
 * No schema changes, paid API calls or secret exposure.
 */
export async function GET(request) {
  const session = await getSession();

  if (!session) {
    return json({ error: 'Unauthorized' }, 401);
  }

  if (!canViewModelIntelligence(session)) {
    return json({ error: 'Forbidden' }, 403);
  }

  const days =
    new URL(request.url).searchParams.get('days') === '30'
      ? 30
      : 7;

  try {
    const schema = await db.query(`
      SELECT
        to_regclass(
          'public.provider_request_metrics'
        ) AS metrics,
        to_regclass(
          'public.model_providers'
        ) AS providers
    `);

    if (
      !schema.rows[0]?.metrics ||
      !schema.rows[0]?.providers
    ) {
      return json({
        status: 'not-configured',
        days,
        metrics: []
      });
    }

    const result = await db.query(`
      SELECT
        m.provider_config_id AS id,

        COUNT(*)::integer AS attempts,

        COUNT(*) FILTER (
          WHERE m.success
        )::integer AS successes,

        ROUND(
          AVG(m.elapsed_ms)
        )::integer AS average_ms,

        ROUND(
          PERCENTILE_CONT(0.95)
          WITHIN GROUP (
            ORDER BY m.elapsed_ms
          )
        )::integer AS p95_ms,

        SUM(m.input_tokens)::text AS input_tokens,
        SUM(m.output_tokens)::text AS output_tokens,

        COUNT(m.input_tokens)::integer
          AS input_samples,

        COUNT(m.output_tokens)::integer
          AS output_samples

      FROM provider_request_metrics m

      JOIN model_providers p
        ON p.id = m.provider_config_id

      WHERE
        p.owner_user_id = $1
        AND m.created_at >=
          NOW() - ($2::integer * INTERVAL '1 day')

      GROUP BY m.provider_config_id

      ORDER BY attempts DESC
    `, [
      session.userId,
      days
    ]);

    return json({
      status: 'ready',
      days,

      metrics: result.rows.map(row => ({
        id: row.id,
        attempts: Number(row.attempts),
        successes: Number(row.successes),

        averageMs: row.average_ms == null
          ? null
          : Number(row.average_ms),

        p95Ms: row.p95_ms == null
          ? null
          : Number(row.p95_ms),

        inputTokens: row.input_tokens == null
          ? null
          : Number(row.input_tokens),

        outputTokens: row.output_tokens == null
          ? null
          : Number(row.output_tokens),

        inputSamples: Number(row.input_samples),
        outputSamples: Number(row.output_samples)
      }))
    });

  } catch {
    return json({
      error: 'Metrics temporarily unavailable'
    }, 503);
  }
}
