# Security

Vector is private by default.

Never commit environment files, access tokens,
credentials, private keys, logs, customer data,
database contents, uploads or confidential screenshots.

## Execution boundaries

- Tools run with least privilege and explicit scopes.
- Production changes and outbound messages need owner approval.
- Self-modification must be reviewed and evaluated.
- Non-idempotent actions must not be silently retried.
- Untrusted websites and MCP output are not instructions.
- External skills require security and license checks.
- Untrusted code runs in an isolated sandbox.

## Repository hygiene

Run a secret scanner and inspect staged changes before pushing.

A clean secret scan does not guarantee that every sensitive
piece of information has been removed.

Keep GitHub credentials restricted and establish
a reviewed staging and release process.

## Screenshots

Redact real names, addresses, internal infrastructure,
identifiers, API details and private project content.

Never present a mockup as an actual application screenshot.

## Privacy review and provider cost boundaries

Selected skill text is scanned before provider JSON serialization. Original send is explicit consent for the exact reviewed snapshot, not blanket approval to disclose newly discovered tool secrets. Detector outages offer a clearly labelled rules-only review. Free inference uses explicit eligible models and an adapter price ceiling, not quota evasion. See [privacy and accounting boundaries](FREE_USAGE_PRIVACY_ACCOUNTING.md).

## Active scanner and control policies

Only owner/admin can save an asset scope; admins need an owner grant before a
run. Scope digests bind resolved addresses, ports and optional advisory consent.
Revalidate addresses, block metadata/reserved targets and pin socket destinations.
Reports describe observed evidence and version candidates, never confirmed
exploitation by inference. Keep secret response bodies out of reports. See
[scanner boundaries](SECURITY_SCANNER.md).

Read-only accounts cannot enqueue spending or mutate workspace records, but can
log out normally. Model/tool allowlists are checked at actual execution. Critical
sandbox/network tool grants bind exact arguments and are consumed once. Budget
reservations serialize admission, retain unknown completion and do not pretend
to be reconciled provider invoices. [Operational contracts](CONTROL_CENTRE.md).
