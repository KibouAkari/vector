# Changelog

This changelog summarizes the commits in the available repository history.
It covers the initial sanitized application snapshot and the changes through
`8dad487` on 2026-10-14.

## Unreleased

### Added
- Owner-only Model Intelligence dashboard within Models & APIs.
- Seven-day and 30-day provider observations including request counts,
  success rates, latency and reported token usage.
- Read-only, owner-scoped metrics API with missing-data indicators.
- Offline regression tests and CI coverage for the dashboard.

### Security and testing
- Add real authenticated HTTP and isolated PostgreSQL tests for
  owner-only access, tenant isolation, date windows and missing data.
- Verify input-only and output-only token observations independently.

### Operational notes
- Model routing and provider credentials remain unchanged.
- Telemetry remains opt-in; its database migration is not applied.
- Per-connection CHF costs are not displayed until reliable attribution
  is available.

## 2026-10-14

### `8dad487` — Document available commits and add MIT attribution license (#12)

- Added the MIT license and project copyright attribution.
- Expanded the changelog to describe the previously documented history.

### `6e10ca9` — fix(cost): attribute usage events to users and verify budget isolation (#11)

- Persist the owning user ID with provider usage events, including background jobs.
- Centralize usage-event persistence and per-user total/monthly cost aggregation.
- Add a user-and-date usage index for efficient per-user budget checks.
- Add isolated-PostgreSQL tests for attribution and per-user budget separation, and run them in application CI.

## 2026-10-13

### `5945c33` — security: enforce project membership and server resource access (#10)

- Require project membership and owner privileges for protected project operations.
- Apply access checks to file, task, tool, conversation and related server-resource routes.
- Add authenticated project API integration coverage against isolated PostgreSQL and run it in CI when its fixture is available.
- Cover response preservation, file-write protection and editor deletion behavior.

### `7876e4c` — fix: harden model broker and provider telemetry (#9)

- Give explicit HTTP status precedence in retry classification and preserve provider HTTP status on failures.
- Restrict shadow comparison to opted-in background jobs; handle missing benchmark profiles and unsupported alternatives safely.
- Recognize Perplexity as a provider family.
- Normalize OpenAI and Anthropic usage while preserving the distinction between unknown and explicitly zero token counts.
- Isolate optional telemetry persistence to a dedicated, bounded PostgreSQL connection and document its operational limits.
- Add reliability tests for retry decisions, routing comparisons, usage normalization and telemetry isolation.

### `5409784` — feat: add opt-in provider request telemetry (#8)

- Add disabled-by-default measurement of provider, model, duration, response status and reported token usage.
- Keep prompts, responses, credentials and raw exception messages out of telemetry.
- Store telemetry separately from billable usage, using best-effort asynchronous persistence.
- Add an explicit migration, operational guidance and tests; include the telemetry tests in CI.

### `ce76032` — feat: introduce background model broker shadow routing (#7)

- Add a read-only model-candidate comparison at the provider resolver boundary, gated by an opt-in setting.
- Keep normal provider selection unchanged and avoid extra provider calls or prompt storage.
- Document the comparison's scope and the limits of catalog estimates.
- Add shadow-routing tests and run the model-broker test suite in CI.

### `292aefa` — fix: harden model broker cost and retry validation (#6)

- Reject negative estimated or observed costs.
- Limit transient HTTP retry classifications to an explicit status allowlist.
- Require explicit idempotency and prohibit retries after streamed output or started side effects.
- Add policy tests for the cost and retry constraints.

### `7b193f3` — feat: intelligent model broker foundation (#5)

- Add offline helpers to rank model candidates, summarize observations and assess retry safety.
- Apply privacy, permission, capability, health and budget constraints before ranking.
- Require explicit idempotency approval for retry eligibility; the policy does not itself execute retries.
- Document that the foundation is not connected to production routing and add unit tests and CI coverage.

### `e3b1fcf` — fix: secure CI checkout and simplify README (#4)

- Disable persisted checkout credentials in CI workflows.
- Simplify the README and replace the architecture graphic with a compact logo.
- Clarify screenshot guidance and validation workflow settings.

### `b50fb6e` — ci: add application build and security checks (#3)

- Add application CI for the Next.js production build and Gitleaks source scanning.
- Document current engineering checks, their boundaries and planned improvements.

### `035250c` — ci: establish Vector engineering checks

- Ignore Python bytecode and pytest cache artifacts.

### `cdc44b5` — docs: refine Vector README and architecture (#2)

- Refine product, architecture and development documentation.
- Add deployment guidance and a documentation validator with regression tests.
- Replace the banner with an architecture asset.

### `fafd0a9` — docs: redesign Vector GitHub documentation (#1)

- Rework the README, vision, architecture, roadmap and security documentation.
- Add design-system, development and third-party attribution guidance.
- Add a pull request template, documentation validation workflow and documentation assets.

### `e8fcca1` — chore: initialize Vector platform and documentation

- Add the sanitized application snapshot, Docker build, initial README, vision and contribution guidance.
- Establish the initial application, API routes, libraries, database migrations and asset structure.
