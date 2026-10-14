# Deployment policy and verification

**Status: production deployment triggers have not been
independently audited.**

A repository push or pull request **must not** change the live
Vector installation without explicit release approval.

This is a policy and required control, **not** a claim that
every external deployment mechanism has been inspected.

## Before enabling automated releases

- Review GitHub Actions, repository webhooks and authorized
  third-party applications.
- Check external CI/CD systems and server-side Git polling.
- Audit relevant systemd timers, cron jobs and deployment
  scripts on the host.
- Verify container image update policies and auto-updaters.
- Confirm who can approve releases and which credentials
  are available.
- Test a staging deployment with a documented rollback.
- Record verification results and the date of the audit.

Until this review is complete, treat the production
deployment boundary as **unverified**.

Do not enable unattended deployment from GitHub.

## Read-only production inventory — 2026-10-14

The server-side preflight reported:

- Vector Compose project at `/opt/vector/docker-compose.yml`.
- Five running Vector containers: app, worker, runner, Redis and PostgreSQL.
- Application source directory at `/opt/vector/app`; not a Git checkout.
- `vector-host-agent.service` is enabled.
- No matching Vector deployment timers were listed by the initial check.
- The production application's code revision was not independently verified.

These observations do not establish that automated deployment is absent.

Before a release, confirm Compose build sources, application-file
differences, persistent volumes, backup and restore procedures,
deployment automation, and a safe rollback strategy.

No database migration or production deployment was authorized
by this documentation update.
