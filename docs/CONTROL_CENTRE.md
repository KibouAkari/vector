# Control centre

Source update, 27 November 2026. Deployment is a separate operation. The existing
Next.js App Router, React, PostgreSQL and background worker remain in use.

## Navigation and layout

The sidebar links directly to Dashboard, Chat, Projects, Skills, Security Scanner,
Approvals, Models & API Keys, Usage & Budgets and Users & Policies. Access follows
the signed-in account. The owner approval count refreshes every 15 seconds and
after a decision. Infrastructure and audit remain separate operational views.
`/platform` redirects to the dashboard; the old capability API remains compatible.

`app/vector-control.css` is scoped to the authenticated shell. Login and intro
sources are unchanged. Dashboard structure and chart components are unchanged.
Controls use restrained mint accents, 1px borders, tabular data, visible keyboard
focus, reduced-motion support, loading skeletons and bounded table scrolling.
The mobile navigation traps focus, makes the page inert and restores focus on
Escape. A skip link goes directly to the main content.

## Roles and action policy

| Role | Existing allowed project/chat work | Active scanner | Decide global approvals / manage users and policies |
| --- | --- | --- | --- |
| Owner | Yes, subject to configured spend ceilings | Own authorized assets | Yes |
| Admin | Yes, subject to feature, project and role policy | Own assets after owner approval | No |
| Member | Explicit feature/project access and role policy | No | No |
| Read-only | Read explicitly accessible records | No | No |

Read-only accounts cannot enqueue chat, mutate projects/files/skills or spend
through model tests. Background execution rechecks enabled/expiry/role state.
Model allowlists use exact `provider/model` identifiers; tool allowlists use exact
tool names. `null` allows the existing permitted set; an empty array denies it.
Role policy never grants missing project access or bypasses local-only privacy.

Critical chat tools `network_scan`, `sandbox_run` and `sandbox_write_file` use
`network.scan`, `sandbox.execute` and `sandbox.write` policies. The default is
ASK; the owner can choose ASK, ALLOW or DENY. An ASK record binds user, project,
tool and canonical arguments to a digest. It expires after 15 minutes and is
consumed atomically once. Arguments are masked in the displayed request.
After approval, retry the exact action; automatic paused-job continuation is not
implemented. Changed arguments require a new decision. Approval decisions and
audit inserts share a transaction. Existing unrelated adapters do not gain new
capabilities through this queue.

## Accounting and budgets

Every attributed provider response retains its actual available input, output,
cache and reasoning counters. Reasoning is not added twice. OpenRouter response
charges are labelled reported; configured-rate calculations are estimates.
Missing counters/prices remain incomplete. Local execution has no external API
fee, which is distinct from electricity or host cost. CHF uses the configured
exchange rate and is not a provider invoice.

Usage lists only the requesting account's calls, with project/model filters,
latency and cursor pagination. The owner can configure workspace, account and
project monthly warning/hard amounts in CHF or USD. Legacy user monthly/total
budgets and environment daily/monthly ceilings still apply.

Before each attributed provider call, a PostgreSQL transaction serializes budget
admission against recorded spend plus pending/uncertain reservations. The quote
uses configured rates, a conservative serialized-input envelope and the maximum
output allowance. Native OpenAI search has a bounded tool-call allowance. This
quote is **not measured usage** and is never added to the token ledger. After
accounting is persisted, the reservation is released. Failed requests, missing
usage or uncertain completion retain it. There is no automatic expiry that could
silently free spend after a crash. Operators must reconcile uncertain entries
against provider evidence; a reconciliation UI is not implemented yet.

These are admission controls under configured prices, not an invoice guarantee
for opaque provider-side search/image processing, rate changes or external
unattributed integrations. Keep provider credit limits as a second boundary.
Unpriced paid models fail before a call. The environment ceilings cannot be
raised by the budget page. A configured free-inference constraint still forbids
paid fallback.

## Storage and rollout

Startup extends existing tables idempotently and creates scoped tables for asset
scopes, scan runs, skill versions, role policies and call reservations. Migrations
do not replace existing conversations or jobs. Security results and privacy
receipts are account-scoped; protect the database and volumes. The existing
privacy vault encrypts value mappings locally. Rules do not require a native
model or an additional service. A running worker is required for scan execution.

See [setup](CONTROL_CENTRE_SETUP.md), [API](CONTROL_CENTRE_API.md),
[scanner](SECURITY_SCANNER.md), [skills](SKILLS.md) and
[privacy](PRIVACY_REVIEW.md).
