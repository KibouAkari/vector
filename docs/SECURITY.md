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
