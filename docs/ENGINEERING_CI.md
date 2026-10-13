# Engineering Checks

## Purpose

Vector uses automated pull request checks to detect
build failures and potential security issues before
changes are merged.

## Current checks

### Next.js production build

- Runs on GitHub-hosted Ubuntu runners.
- Uses Node.js 22.
- Installs dependencies from `package-lock.json`.
- Executes the repository's `npm run build` script.
- Requires no production API keys or server credentials.

### Secret scanning

- Runs Gitleaks against the checked-out source tree.
- Detects recognizable credentials and other secrets.
- Uses a pinned Gitleaks container image.
- Does not replace manual security review.

### Documentation validation

The existing documentation workflow checks Markdown
links, SVG assets and image alternatives. It also runs
the documentation validator regression tests.

## Deployment boundary

This workflow contains no deployment steps and does not
connect to the production Hetzner server.

However, external deployment triggers and host-side
automation have not yet been independently audited.

See [Deployment Policy](DEPLOYMENT.md).

## CI limitations

The first application build may reveal dependencies on
production-only environment variables or live services.

These issues must be resolved through test isolation or
safe configuration changes, not by copying production
credentials into GitHub Actions.

## Future improvements

- Targeted unit and integration tests.
- Dependency vulnerability checks.
- Branch protection and required status checks.
- Isolated development and staging environments.
- Versioned releases and controlled rollback.
- Automated evaluation of agent and provider changes.
