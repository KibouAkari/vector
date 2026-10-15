# Changelog

This changelog documents repository changes by date, with commit and pull
request identifiers when available. Entries are listed newest first.
Production deployments are tracked separately.

## 2026-10-15

### Runtime: calculate server JSON rankings locally (#26)

- Add a read-only, bounded JSON ranking tool that verifies the entire source dataset locally and returns only top-N numeric values, units, coverage and read-time metadata. Names can be resolved from a complete local identity map.
- Keep missing/nonnumeric values explicit, reject incomplete sources and unsafe numeric values, and preserve existing Host Agent boundaries, privacy filtering and artifact completeness checks.
- Prefer local aggregation for ranking reports, serialize tool envelopes without decorative whitespace, and expose per-call token/cache/reasoning/stop metadata and tool output character counts for subsequent cost analysis.
- Route empty reasoning-only document responses through the existing single empty-response recovery instead of spending continuation calls on a nonexistent document fragment. Do not increase normal output caps or change providers.
- Offline fixtures verify five ten-row rankings over 43 synthetic files, source completeness, compact model inputs, accounting and document recovery. Live savings and production behavior require staging and a measured live task; no percentage saving is promised.

### Artifacts: render ranking bars and complete truncated documents (#25)

- Render explicit block-bar table cells as proportional vector graphics instead of unsupported question-mark glyphs; preserve supplied bar quantities.
- Continue provider-declared truncated PDF/DOCX content with tools disabled at most twice, using the original per-call token cap and accounting for all continuation usage.
- Reject unfinished or empty continuations before artifact persistence, and preserve completion metadata in compatible-chat and Anthropic adapters.
- Verify synthetic five-category, ten-row PDF rendering and proportional bars, all document-finalization paths, bounded continuation, usage accounting and provider completion metadata in CI; no user records, real model requests, new dependencies or schema changes.
- Production deployment and the original live request remain unverified by this change.

### Chat: finish documents after bounded tool investigation (#24)

- Render explicitly requested PDF/DOCX files after the final no-tools provider turn when the tool investigation reaches its configured limit.
- Preserve the existing renderer, completeness checks, format enforcement, usage accounting and bounded provider-call count.
- Propagate existing artifact state without duplicate rendering; reject empty document content and renderer failures instead of returning text-only success.
- Add regression coverage that reproduces the missing artifact before the fix and verifies PDF/DOCX generation, failures and reuse after the tool-round limit.
- No production deployment, provider calls or schema changes performed during development.

### Server: container resource control center (#23)

- Add separate top-five CPU and absolute-memory rankings plus a searchable, sortable container resource table.
- Fetch the existing host agent's one-shot Docker statistics only after the existing server permission check; keep host information available if resource sampling fails.
- Normalize the host agent's `ports` field for the existing server UI and preserve the original snapshot fields.
- Distinguish missing measurements from zero, retain CPU values above 100%, and explain cumulative I/O counters and host-sized memory limits.
- Refresh visible pages every 30 seconds, mark retained snapshots stale on failure, and explicitly report that exact reboot time and event logs are not supplied.
- Add offline tests for actual endpoint authorization, partial failures, measurement normalization and ranking behavior.
- No host actions, new host agent capabilities, database migrations, provider calls or production deployment.


### Chat: preserve explicitly requested document formats (#22)

- Exclude the XLSX-only server dataset exporter from PDF and DOCX requests.
- Reject wrong-format tool calls before host reads or file generation, and reject mismatched cached or rendered artifacts.
- Preserve deterministic PDF/DOCX rendering after source collection; keep spreadsheet exports available for spreadsheet tasks.
- Add offline regression coverage for the actual agent and tool execution paths. Production deployment and visual review remain separate.

### Projects: file workspace and original downloads (#21)

- Add a larger file browser with search, sorting, images, PDF and bounded text previews.
- Provide authenticated original downloads for every stored file format, enforcing existing project access rules.
- Keep partial text previews read-only and prevent stale preview requests from replacing a newer selection.
- Present text editing and file creation only to users with write access; preserve backend authorization.
- Keep the file workspace mounted across project tabs so unsaved edits survive tab changes.
- Refresh file counts and storage totals after uploads and saves; make overview uploads work before opening Files.
- Scope the visual changes to Projects and retain the main dashboard.
- Add file behavior and download-handler tests plus PostgreSQL-backed access checks in CI.
- No production deployment, explicit database migration, provider requests or telemetry activation.

## 2026-10-14

### UI: chat conversation history and file downloads

- Group the user's existing chat history into readable local-date sections without changing data access.
- Give history rows a clearer visual hierarchy, accessible selection state and useful empty results.
- Unify uploaded and generated chat files under readable download cards with filenames, types and sizes.
- Extend the scoped chat design without creating another dashboard or changing the homepage.
- Add unit regression checks for date grouping and download actions.
- No database migration, provider calls, or production deployment.

### Operations: safeguard persistent production application source (#20)

- Add a one-time guarded maintenance utility to synchronize the host app build source with the already tested 5.9.5 release.
- Pin the existing application Docker image in the base Compose file without changing other services.
- Preserve full original source and Compose backups, validate the rendered configuration, and attempt restoration if the host changes fail.
- Reject overlapping app, worker and runner mounts/build contexts; verify the Compose backup matches the candidate source and preserve live file permissions on rollback.
- Document the recovery paths and verify the Python maintenance script in CI.
- No database migration, external model calls, automatic production deployment, or telemetry activation.

### UI: workspace navigation and model intelligence refinement (#18)

- Keep the home dashboard as the only global usage dashboard and move per-provider intelligence beneath API connections.
- Present unavailable pages as optional locked navigation items with friendly messages; permissions remain enforced on the server.
- Improve the Models & APIs and Audit log labels and provide a themed missing-page experience.
- Redesign the user-management form for accessible account, budget and feature controls.
- Prevent user-editor request races and make project sharing updates transactional; validate grant selections and add an isolated PostgreSQL regression test.
- Display account expiry as local wall-clock time so editing and saving an unchanged expiry preserves its instant.
- Replace soft login/logout navigation with full document transitions to discard previous-account UI state; add regression coverage.
- Test logout response ordering and failure cases with a mocked server request, preventing navigation when session revocation fails.
- No telemetry migration, provider calls or automatic production deployment.

### Security: isolate dashboard data and enforce feature access (#17)

- Scope home usage, charts, models and recent projects to each member; preserve the global view for the platform owner.
- Hide all project summaries from accounts without project access, including shared membership leftovers.
- Require feature permission for chat, attachments, activity, Models & APIs and their relevant HTTP APIs; restrict global usage controls to the owner.
- Add authenticated HTTP regression coverage for tenant isolation, project visibility and denied features.
- No database migration, telemetry activation or production deployment in this pull request.

### docs: standardize changelog and release documentation (#16)

- Restore dated and commit-attributed entries for PR #13, #14 and #15.
- Document the separately committed screenshot assets.
- Add changelog requirements to development instructions and PR reviews.
- Update telemetry documentation and record the production preflight.
- No production deployment, database migration or service change.

### `b714f5a` — feat: add owner-only Model Intelligence dashboard (#15)

- Add Model Intelligence to the existing Models & APIs interface.
- Display 7-day and 30-day provider statistics, including request counts,
  success rates, response latency and reported token usage.
- Introduce a read-only API with server-side owner authorization and
  provider-credential isolation.
- Add authenticated PostgreSQL integration tests for access controls,
  tenant isolation, date filtering and missing telemetry data.
- Correct token-completeness reporting to distinguish input and output
  samples instead of treating them as paired observations.
- Pass application build, security scanning and documentation checks.
- Keep provider telemetry opt-in; no migration or production deployment
  is performed by merging this pull request.

### `74a9436` — docs: add product screenshots to README (#14)

- Embed the existing Vector login and dashboard screenshots into
  the README with captions and descriptive alternative text.
- Update screenshot documentation to match the actual filenames.
- Preserve privacy guidance for published screenshots.

### `c5bc109` — chore: add Vector screenshot assets

- Add the login and workspace dashboard image files to the repository.
- These assets were added separately before pull request #14.

### `ba81d16` — docs: complete changelog history (#13)

- Expand the changelog to cover previously undocumented repository commits.
- Add commit-specific summaries for the initial application snapshot,
  documentation, security, CI, model broker and telemetry development.
- Preserve chronological traceability without claiming a production release.

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




