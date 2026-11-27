# Free inference, privacy decisions and truthful accounting

Source implementation, 26 November 2026. These controls are not evidence of a
production rollout, an unlimited quota or a fully connected AI platform. No
provider account, subscription or key is created. Verification uses offline
responses and isolated database/API fixtures, not paid model calls.

## Legitimate free capacity

Use the quotas granted to the account you control. Extra keys normally share
account, project or organization limits. Vector does not harvest keys, create
replacement accounts, evade exhausted quotas or silently move a free-only task
to paid inference. Provider prices, eligible regions and terms can change.

| Source checked | What it provides | Practical boundary |
| --- | --- | --- |
| [publicapis.dev](https://publicapis.dev/) and its [AI directory](https://publicapis.dev/category/ai) | Discovery of public APIs, including free and paid services | A directory is not an API-key issuer, license grant, privacy guarantee or unlimited premium inference pool |
| [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits) and [free router](https://openrouter.ai/openrouter/free) | Account-limited free variants and a free-model router | More accounts/keys do not increase the platform's underlying capacity; free models have quotas and no guaranteed availability |
| [Gemini rate limits](https://aistudio.google.com/docs/rate-limits) | Model/account-dependent free and paid capacity | Limits are per project, not per key. Review the [current terms](https://aistudio.google.com/docs/terms), including paid-service requirements for API clients in Switzerland/EEA/UK and regional data-handling exceptions, before enabling a user-facing integration |
| [Groq limits](https://console.groq.com/docs/rate-limits) | Organization/model-specific capacity | Keys share organization limits. Review [data handling](https://console.groq.com/docs/your-data) and the account's exact allowance; this change does not certify a Groq free-only route |
| Installed local models | No external inference API charge | Host resources, power and administration still cost money; capacity and quality depend on hardware and model |

Configure a provider under Models & APIs using your own key, endpoint and model
ID. Set an explicit `vendor/model:free` model or `openrouter/free` on OpenRouter.
Use a model supporting the task's required tools; the free router is not a
quality guarantee. Do not substitute an unverified proxy endpoint.

Chat and project chat now offer **Gratis-Inferenz**. The durable job carries
`billingPolicy: "free-only"`. Selection retains normal account ownership,
sharing and capability filters, then permits only a configured local provider on an explicit internal/loopback endpoint
or an explicitly free OpenRouter model at `https://openrouter.ai/api/v1`.
The adapter rechecks eligibility immediately before a call and sends a zero
prompt/completion price ceiling with provider fallback disabled. No eligible
model means a visible failure, not paid fallback. Exclusions on a later attempt
cannot remove this restriction. Attributed inference calls do not automatically
retry an uncertain provider attempt; their reservation remains held if
completion cannot be accounted for. No key rotation loop is introduced.

This switch controls **inference fees**, not paid search, image/video generation,
telephony, storage, external tools, taxes or host costs. Those need their own
budget/permission controls. Local-only privacy mode is stronger than free-only:
it forbids cloud inference, whereas a free cloud provider still receives the
approved text. No live free quota or provider performance was measured here.

## Privacy decisions

The default path now uses fast deterministic credential/contact rules, without a
model call. `VECTOR_PRIVACY_DETECTOR=ner` optionally adds the existing local GLiNER encoder. It is a lightweight local recognition pipeline, not a
second cloud model. A larger generative detector was not added just to classify
names. Actual native detector quality and latency still need host qualification.

For a cloud-bound request with privacy enabled:

1. Review covers the message, selected skills, retrieved project context,
   provenance, attachments and the exact owned conversation snapshot.
2. Each finding has a checkbox. Select all, none or individual findings. Secret
   values remain hidden in the finding list. The live preview follows the selected checkboxes. Hidden list values remain masked;
   a deliberately unselected value is visible in the outgoing-message preview.
3. Confirm selected replacements or send the original explicitly. Unselected
   findings are sent unchanged. Consent is encrypted, expires and binds the
   user, scope, content, attachments and billing preference.
4. The worker preserves that exact reviewed snapshot. Newly read tool evidence
   has separate masking consent; it cannot inherit permission to disclose
   unknown secrets from the original-send button.
5. Conversation-scoped mappings restore placeholders locally in results and in
   allowlisted local tool arguments. External search/command arguments do not
   receive automatic restoration of secrets.

Quoted passwords in raw skills and JSON/escaped document strings are scanned
before provider serialization. Selected skills no longer introduce JSON escape
bytes before detection. A regression drives the real project route and privacy
engine through review, confirmation and durable enqueue with a quoted synthetic
password and checks that its full value is absent.

If optional NER is enabled but unavailable or returns an invalid/incomplete response,
initial review shows a **rules-only warning**, even if no rule finding exists.
It does not record a successful native scan or fabricate usage. No cloud job is
queued until the user chooses explicitly. Original-send remains available.
Rules-only replacement is partial protection and the dialog says so. Invalid
consent, ownership failures, oversized context and new unreviewed tool evidence
still fail safely. A detector outage during later tool-evidence processing does
not grant a silent disclosure exception.

Privacy off deliberately sends the full context, including previous local
restorations. Explicit local mode bypasses outbound privacy detection and has no
silent cloud fallback. Authentication, project authorization and tool grants
remain in force in every mode. Detection and placeholders do not guarantee
perfect anonymity or protect an original that the user explicitly sends.

## Accounting without invented certainty

`/api/usage/calls` returns only the authenticated account's own provider-call
records, with bounded cursor pagination and an allowlist of counters/statuses.
The Usage page shows this ledger separately from workspace budget totals.
Prompts, tool evidence, API keys and provider error text are not added to it.

| Label | Source | Meaning |
| --- | --- | --- |
| `reported` | Valid OpenRouter `usage.cost`, including explicit zero | Provider-reported USD request charge; not a reconciled invoice |
| `estimated` | Actual provider token counters multiplied by configured rates | A calculated cost, explicitly not an actual provider bill |
| `incomplete` | Missing/invalid usage, cache counts or pricing | Unknown values remain unknown in the ledger, not free zero-token calls |
| `local-no-api` | Local execution | No external inference API fee; host/energy costs excluded |

Preserve the actual model named in a compatible provider response when present,
plus the requested model in metadata. Cached reads, cache writes and reasoning
are distinct. Reasoning is already part of provider output tokens and must not
be charged twice. Normalize Anthropic cache counters separately from OpenAI
compatible counters. Missing fields, booleans and empty strings are not valid
reported token counts. Existing response IDs deduplicate persisted calls.

The [OpenRouter response format](https://learn.openrouter.ai/courses/first-request/read-the-response)
reports request cost in credits; [pricing](https://openrouter.ai/pricing)
describes USD inference rates and separate credit-purchase fees. The ledger's
CHF amount uses the configured USD/CHF rate, **not a provider-reported CHF bill**.
Database budget columns retain existing six-decimal rounding; provider cost
metadata keeps the response amount. Budget totals may therefore differ from
invoice totals, taxes, FX settlement or credit-purchase charges.

Other providers' calculated costs remain estimates until an official billing
connector reconciles them. The [Anthropic usage/cost APIs](https://platform.claude.com/docs/en/manage-claude/usage-cost-api)
require organization/admin credentials and have product/granularity limits.
No billing-admin key is requested, no invoice is invented and no extra paid
model request is made just to test accounting.

## Release boundary

Also harden malformed JSON handling, large Unicode skill bodies, single root
Nmap completion, bounded per-address PDF rows, retry identity after ambiguous
assessment saves, and navigation to older assessments. These are source fixes
in the existing platform change, not live server measurements.

Before a production web rollout, qualify the exact app/worker image and the
actual local detector with synthetic records, verify key ownership and privacy
choices, back up state and retain rollback evidence. Channel sends, device
agents, live calls and autonomous scanner execution still need their own
implementations and runtime qualification. See [platform delivery](PLATFORM_DELIVERY.md)
and [deployment](DEPLOYMENT.md). No Minecraft deployment is implied.

## Shared call admission

Provider calls now reserve configured-price budget under a shared PostgreSQL lock.
Unknown completion retains the reservation. This is distinct from recorded token
usage and provider-reported charges. See [limits and accounting](CONTROL_CENTRE.md#accounting-and-budgets)
for conservative envelopes, operator pricing and reconciliation boundaries.
