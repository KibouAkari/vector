# Security Policy

Vector is private by default.

## Secrets

Never commit:

- API keys or provider credentials.
- Environment files.
- Database contents or exports.
- Customer and personal records.
- Runtime files and uploaded attachments.
- Host access tokens, certificates or private keys.

A .gitignore does not guarantee safety.

Run a secret scanner and manually inspect staged changes
before the first push.

If credentials are exposed in Git history, rotate them.
Deleting a file does not remove it from previous commits.

## Approval

Production changes, outbound messages, destructive
operations and autonomous code modifications require
explicit owner approval.

## Deployment

A GitHub push must not automatically deploy changes
to the production Hetzner server.

Use staging, testing, approval and rollback procedures.

## Screenshots

Remove usernames, addresses, passwords, API information
and sensitive infrastructure details before publication.
