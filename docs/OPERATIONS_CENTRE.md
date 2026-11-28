# Operations centre

This source update rebuilds the authenticated interface around grouped navigation,
a compact command palette and operational data. The Vector logo, login and intro
source are unchanged. It is not evidence that a live installation has been updated.

## Interface

Workspace contains Overview, Chat, Projects and Agent teams. Knowledge contains
Brain and Skills. Operations contains Infrastructure, Connections, Traffic and
Security. Control contains approvals, activity, models, usage and account policies.
Navigation respects account permissions. Cmd/Ctrl K opens page search. Interface
preferences change accent, density, ambient light and motion per account/browser.
Reduced motion takes precedence. Numeric counters use tabular figures. Dashboard
charts use the scoped usage ledger, not invented service health or quality scores.
The period is 30 UTC calendar days. No data is an empty state, not a fake timeline.

## Brain

Brain is private to the authenticated account and shared across that account's
model requests. It is not a global memory visible to every user. Save a fact,
preference or decision explicitly, edit using its revision, optionally pin it, or
set expiry. The body is encrypted with the existing FILE_ENCRYPTION_KEY. Titles,
tags and provenance are metadata; do not put credentials in them. Obvious secrets
in bodies are rejected. This is a guard, not comprehensive secret detection.

Retrieval intersects HMAC keyword indexes, prioritizes pinned entries and returns
at most six memories within 2,400 UTF-8 bytes. It performs no model request and
uses no embedding service. This byte bound is not an exact token guarantee;
tokenization varies by model and language. Relevant facts enter the existing
privacy review together with prompt, files and history. The durable job receives
the reviewed snapshot. A new memory is never silently added to an already queued
job. Chat's Brain toggle disables retrieval for subsequent turns.

Corrections require the last revision and reject stale updates. Forgetting removes
the live record and its keyword index. Expired facts are excluded immediately.
Previously sent or retained conversation context is not erased by forgetting.
Export contains plaintext and should be handled like other private downloads.
The system learns user-supplied context; it does not silently train models or
claim to improve model weights. Project-shared memory and automatic memory
extraction are not enabled by this update.

## Agent teams

Use Agent teams to choose a project, task, one to three specialists and a shared
request limit of four to eight. Roles include research, design, sales, support,
data, automation, coding and security. At most two independent specialists run
at once. Specialists receive the reviewed context and cannot execute tools. The
worker can use the existing authorized tool path; a separate quality call checks
its result when the shared request budget remains. Reviewer limitations are shown
with the answer. A review is not evidence that an external action succeeded.

Each role goes through the existing provider policy, free-only enforcement,
monetary reservation, privacy filter and usage capture. A PostgreSQL compare-and-
swap counter admits provider requests across asynchronous branches and retries.
The counter is conservative: rejected or uncertain admissions need not be refunded.
It counts calls, not billed tokens. The Usage ledger remains the authority for
reported tokens and cost attribution. A team cannot bypass tool approvals or
project/account limits. A retry does not reset the counter. Ordinary chat remains
single-agent. Local-only jobs use the single local path; teams do not fall back to
cloud when local mode is selected. Provider-specific live team quality is not
benchmarked by the free release checks.

## Connections

Connections are private to their owner and restricted to operator accounts.
Credentials and saved snapshots are encrypted. A successful save only validates
configuration and resolves allowed destinations. It does not call the service.
Press Sync to make the documented bounded read request. Snapshots show their
last fetch time and errors; no status is presented as continuous monitoring.

| Adapter | Credential | Read behavior |
| --- | --- | --- |
| Checkmk | Automation username + secret | Host status collection under your configured site and API version |
| Wazuh | Manager API username + password | Short-lived JWT authentication, first 100 agents and total count |
| PatchMon | Scoped integration token key + secret | `/api/v1/api/hosts` when base ends in `/api/v1` |
| GitHub | Fine-grained token | Account metadata |
| Slack | Bot token | Workspace/account identity via `auth.test` |
| Notion | Integration token | Integration/workspace identity |
| Gmail | Scoped OAuth access token | Mailbox profile counters |
| Figma | Personal access token | Current account metadata |
| Salesforce | OAuth access token | API limits under the configured instance/version |
| HTTP API | Bearer token | Fixed-origin JSON endpoint, response shape/count only |

Check each installed service version and grant only the necessary read scopes.
PatchMon host credentials are different from integration tokens. Wazuh's manager
agent endpoint does not expose the full indexer's vulnerability inventory. OAuth
consent, refresh-token rotation, webhook subscriptions and comprehensive Gmail,
Notion, Figma or Salesforce workflows remain separate implementation work. An
expired token produces a visible error; it is not silently replaced.

HTTPS verification remains enabled. Supply a trusted CA through the Node runtime
for private certificate authorities. Never disable TLS verification. Private
RFC1918 addresses require VECTOR_CONNECTOR_PRIVATE_CIDRS. Loopback, link-local,
cloud metadata and other special addresses stay blocked. Plain HTTP additionally
requires VECTOR_CONNECTOR_ALLOW_PRIVATE_HTTP=true and an explicit private CIDR.
DNS addresses are pinned when saved and rechecked before requests; changes
require re-adding the connection. Redirects, URL credentials and origin escapes
are refused. Reads have an 8-second deadline, 1 MiB response cap, no decompression,
up to 100 displayed resources and a 15-second per-connection sync cooldown.

### Controlled actions

The implemented writes are GitHub issue creation and Slack message posting.
Prepare exact content in Connections or through the assistant's operator tools.
Owner approval binds the destination, method, path and body digest. Inspect all
content in Approvals, approve it, then execute once in Connections. Approval alone
does not transmit the content. Uncertain outcomes are marked uncertain and are
not replayed automatically. Confirm externally before preparing any replacement.
The assistant can read saved snapshots and request actions, but cannot execute
these writes by itself. Additional restart, patching, mail-send and deletion
adapters are not implied by connecting a service.

## Traffic

Set VECTOR_TRAFFIC_INGEST_TOKEN to a random value of at least 32 characters on
app and collector. Ingestion remains disabled when absent. The signed request
binds exact body bytes, a timestamp within 60 seconds and a single-use nonce.
The app accepts at most 500 events / 256 KB per batch and 60 batches per minute.
Events are encrypted at rest. Ingest prunes records older than 24 hours; queries
exclude them even before physical pruning. The UI reads the latest 10,000 events
and labels the cap. Country and coordinates must come from a trusted collector,
for example a local GeoIP database. Unknown geography remains unknown.

Run `scripts/collectors/traffic.py --endpoint https://vector.example.org/api/traffic
--services /private/service-map.json` with nginx JSON lines on stdin. Each line
contains `remote_addr`, `server_name` and timezone-aware `time_iso8601`. The private
JSON map relates exact server names to service labels. Optional `country_code`,
`latitude` and `longitude` may be emitted by trusted local GeoIP processing.
Untrusted forwarded-IP headers are not used. Never commit populated logs or maps.

The first-party collector supports HTTP request logs. TCP/Minecraft/NAS connection
telemetry can be posted by a trusted external collector with kind
`connection-snapshot`; Vector does not pretend nginx request counts measure live
TCP sessions. The lazy Three.js globe plots only supplied coordinates and has a
non-WebGL table fallback. It is an observation view, not threat attribution.

## Public service security

Authorize a saved Website or API asset using a public domain, including a Vercel
application/custom domain. The web profile sends bounded Host/SNI requests to
80/443 or the explicit URL port. It does not run TCP discovery against shared
hosting infrastructure. Network/NAS/Minecraft profiles remain for owned hosts.
Known shared hosting suffixes require a web profile. Older broad website scopes
must be reauthorized. DNS pinning and approval digest checks remain enforced.

The scanner checks reachable services, TLS/headers, bounded exposure probes and
optional advisory candidates. It does not prove exploitability, reveal Minecraft
online-mode from the public status protocol, or replace a scoped penetration test.
Optional AI analysis must be an explicitly requested paid/local chat task; viewing
scan results causes no model charge. No real target scan runs during release tests.

## API additions

| Endpoint | Methods | Boundary |
| --- | --- | --- |
| `/api/brain` | GET, POST, DELETE | Own memory only; revision-checked mutations; readonly denied |
| `/api/connections` | GET, POST | Own operator connections, sync, request-action, execute, remove |
| `/api/traffic` | GET, POST | Operator read; separate HMAC collector ingest |
| `/api/teams` | GET | Own role progress and shared call counters |
| `/api/projects/:id/chat` | POST | Existing API with optional validated `team` and `brainEnabled` |
| `/api/chat` | POST | Existing API with optional boolean `brainEnabled` |
| `/api/skills/import` | POST | Preview/import a public pinned SKILL.md into an authorized draft inventory |

Schema initialization is additive and idempotent, matching the repository's
current architecture. No new database daemon, worker contract or Docker socket
permission is introduced. Existing worker polling executes teams through the
normal job path. Existing deployments must build and deploy the new web image;
updating a Git checkout alone does not update running containers.

## Source validation

The source was checked with a production Next.js build, 296 deterministic Node
tests and 46 isolated PostgreSQL/API tests. The browser pass covered 13 authenticated
pages at 1440px and 390px widths, command navigation and memory creation, with no
page errors or document-level horizontal overflow. A known reduced-motion route
hydration mismatch was repaired. Dependency audit reported zero known advisories
at check time; this is not a guarantee against undisclosed vulnerabilities.
Provider calls were stubbed for team admission tests. Live provider quality,
vendor credentials, service versions, external scans and production deployment
were not exercised by these checks.

## Pinned app update

`scripts/deploy/update-operations-web.py --workspace /private/operator-workspace --revision <40-character-main-commit>`
builds the exact checkout using the existing Docker/Compose app identity. It
retains secrets/mounts/networks, escapes literal Compose dollar values, qualifies
packaged routes without network or credentials, waits for observed running work
and recreates only the web app. Health checks cover database/cache and anonymous
access guards. An unsuccessful activation restores the previous app configuration
while the script still holds it in memory. No database backup or worker/game
restart is performed. Build/deployment logs stay in a private operator release
directory. The caller must fetch and pin an already qualified revision first.
