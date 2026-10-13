# Provider Request Telemetry

**Status:** Implemented in source, disabled by default.

The existing `requestProviderResponse()` entry point can
measure individual outbound model requests without making
additional provider calls.

## Captured fields

- Provider configuration ID and model
- Provider family and adapter
- Success/failure
- Total request duration
- HTTP status and coarse error category
- Reported input, output and cache tokens

Unknown usage remains `NULL`, not zero.

## Privacy

The telemetry writer never stores:

- Prompt content or model responses
- API keys or credentials
- Raw exception messages
- Conversation content or task instructions

No API or user-facing dashboard is provided in this phase.

## Cost accounting

This telemetry table is entirely separate from
`usage_events`.

The component never charges a user or writes monetary
costs. Accurate CHF costs require a verified pricing and
usage-attribution integration.

## Deployment requirements

Before enabling `VECTOR_PROVIDER_TELEMETRY=1`:

1. Review and separately apply the SQL migration.
2. Verify database access, permissions and backups.
3. Establish appropriate data retention.
4. Test in staging.
5. Obtain explicit approval for production rollout.

Merging Git code does not apply database migrations.

## Reliability

Writes are best-effort and asynchronous, with at most one
outstanding insert and one dedicated PostgreSQL connection
per application process. Additional observations are dropped
while that insert is in flight. Database failures, shutdown
or overload may result in missing observations.

The model response and original provider errors are
never changed by telemetry failures.

No live measurements are claimed until the feature has
been deployed, enabled and verified.

## Follow-up

Investigate `recordUsage()` user attribution: existing
callers pass `userId`, but its current function signature
does not consume that parameter.

Do not assume per-user spending data is correct until
that behavior is reviewed.

## Review hardening

- The terminal HTTP failure retains its status when the provider call fails.
  If an internal HTTP retry succeeds, one successful provider-call metric
  is recorded; individual failed attempts are not currently measured.
- Missing normalized token usage remains unknown in telemetry,
  while existing numerical usage handling stays unchanged.
- A dedicated PostgreSQL pool uses at most one connection and one
  outstanding insert per process. Excess observations are dropped.
- The isolated pool consumes one additional database connection
  per active application process.
