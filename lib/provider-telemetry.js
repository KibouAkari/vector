/**
 * Optional Postgres telemetry sink.
 * Never writes to usage_events.
 */

import crypto from 'node:crypto';
import { db } from './db';
import {
  measureProviderCall,
} from './provider-telemetry-core.mjs';

let inFlight = 0;
let warned = false;

const MAX_IN_FLIGHT = 32;

function queueMetric(metric) {
  if (inFlight >= MAX_IN_FLIGHT) return;

  inFlight++;

  // Non-blocking persistence: database failures must not
  // delay or fail model responses.
  void Promise.resolve()
    .then(() => db.query(`
      INSERT INTO provider_request_metrics (
        id,
        provider_config_id,
        provider,
        model,
        adapter,
        success,
        elapsed_ms,
        http_status,
        error_category,
        input_tokens,
        output_tokens,
        cached_tokens
      )
      VALUES (
        $1,$2,$3,$4,$5,$6,
        $7,$8,$9,$10,$11,$12
      )
    `, [
      crypto.randomUUID(),
      metric.providerConfigId,
      metric.provider,
      metric.model,
      metric.adapter,
      metric.success,
      metric.elapsedMs,
      metric.httpStatus,
      metric.errorCategory,
      metric.inputTokens,
      metric.outputTokens,
      metric.cachedTokens,
    ]))
    .catch(() => {
      if (!warned) {
        warned = true;

        console.warn(
          '[vector-telemetry] Persistence unavailable; request unaffected'
        );
      }
    })
    .finally(() => {
      inFlight--;
    });
}

export function observeProviderRequest({
  runtime,
  execute,
}) {
  if (
    process.env.VECTOR_PROVIDER_TELEMETRY !== '1'
  ) {
    return execute();
  }

  return measureProviderCall({
    runtime,
    execute,
    record: queueMetric,
  });
}
