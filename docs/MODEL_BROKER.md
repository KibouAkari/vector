# Vector Model Broker

**Status:** Offline policy foundation.
Not connected to production routing yet.

## Implemented functions

### `rankCandidates`

Applies privacy, permission, capability,
provider-health and per-request cost constraints.

Only eligible models enter the quality, cost,
latency and reliability ranking.

### `summarizeObservations`

Aggregates trusted application observations:

- Model success rate
- Average observed cost in CHF
- P50 and P95 latency
- Verified quality score

Unverified model quality is not treated
as a measured result.

### `safeToRetry`

Classifies potentially retryable failures.

Retries are prohibited after visible streaming
or external side effects.

Retries require explicit `idempotent: true` approval. The default is `false`.

This function does not execute retries.

## Integration requirements

The broker must be connected at the existing
provider-selection boundary only after reviewing:

- User and project permissions
- Existing cost-control logic
- Provider runtime contracts
- Background-job idempotency
- Privacy classification
- Streaming behavior
- Health and telemetry persistence

No current production behavior is modified.

## Testing

Run:

```bash
node --test tests/model-broker-policy.test.mjs
```

Model names, estimated costs and latencies used by
the tests are synthetic fixtures, not live measurements.


## Additional safety constraints

- Negative configured or observed costs are invalid, even when no
  per-request cost ceiling has been set.
- Only HTTP 429, 502, 503 and 504 qualify as transient HTTP failures.
  Retry approval also requires explicit idempotency, zero visible
  streamed output and no started side effects.
- Retry classification is a pure decision helper; it never retries
  a request or changes production routing itself.
