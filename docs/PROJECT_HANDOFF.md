# Engineering handoff

The public handoff describes source boundaries. Operator-specific instructions, live image IDs, paths, user records, credentials and rollback evidence are maintained privately.

## Current source

- Web privacy review, exact-request consent, privacy-off and local-only routing are independent of server authorization.
- Original-send approval covers the reviewed prompt/context. A separately disclosed, signed preference masks newly read evidence; old jobs without that preference remain blocked for unapproved data.
- Local native text requests retain the current input and drop oldest complete turns within the context budget. Explicit local mode never falls back to a cloud provider.
- Supported Minecraft statistics use fresh, complete, operator-configured read-only sources. Unknown or incomplete evidence must not become a record claim.
- The optional Minecraft service/addon has its own release boundary. Renaming its source or examples does not update an installed service.

## Next verification

1. Run the application, privacy/routing tests and synthetic database integration checks on the exact release head.
2. Inspect the live web deployment read-only before producing an app-specific plan. Establish app/worker code identity and mounts without printing environment values.
3. Qualify privacy-on original-send, replacement, privacy-off and detector outage on an isolated database with synthetic data. Do not execute real queued jobs or call cloud providers for this qualification.
4. Build and roll out only the authorized web components. Preserve the game, assistant, local inference, networking and backups.
5. Record actual deployment evidence privately. Do not infer a live fix from a merged PR.

See [architecture](ARCHITECTURE.md), [security](SECURITY.md), [deployment](DEPLOYMENT.md), [Minecraft](MINECRAFT.md), [publication](PUBLICATION.md) and [roadmap](ROADMAP.md).

## Platform source update

Global approvals and policy administration require platform owner. Project skills
are immutable instruction drafts activated against an exact content hash and
selected explicitly before privacy review. The security workbench now runs authorized bounded checks; the previous scoped
Nmap XML importer is retained separately. See
[platform delivery](PLATFORM_DELIVERY.md) for tests, boundaries and unfinished adapters.

## Privacy and cost source update

Individual placeholder choices and the initial rules-only outage dialog are source-qualified with offline fixtures. Free inference is retained through durable routing; no key provisioning or paid fallback is added. The own-account ledger distinguishes OpenRouter reported USD costs from estimates, unknown usage and CHF conversion. Qualify the fast rules path, optional native detector and exact app/worker release on the host before claiming deployment. See [delivery contracts](FREE_USAGE_PRIVACY_ACCOUNTING.md).

## Control centre handoff

Direct navigation replaces the platform inventory. Source includes global/project
skill versions and typed parameters, exact single-use critical tool grants,
read-only account enforcement, model/tool policy and shared call reservations.
Active scans require a saved authorization scope, matching addresses and the
existing worker. Private networks require an operator allowlist. Optional
advisory disclosure is separate. Uncertain call reservations are retained until
reconciliation; they are not actual token usage. Source delivery does not imply
an app or worker deployment. See [setup](CONTROL_CENTRE_SETUP.md) and
[API contracts](CONTROL_CENTRE_API.md). Do not run paid evaluations or real
external scans as implicit release tests.
