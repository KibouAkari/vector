# Development

## Repository scope

The current source tree contains reusable application and optional integration source. Historical private Git material requires separate review before publication.

It deliberately excludes production databases,
environment secrets, runtime files and complete
host-specific deployment configuration.

## Workflow

```bash
git switch main
git pull --ff-only
git switch -c feat/short-description

# Work and test in an isolated development environment
npm ci
npm run build

git add -A
git diff --cached --check
git commit -m "feat: describe the change"
git push -u origin HEAD
```

Open a pull request and provide verification evidence.

**Deployment policy:** pushes and pull requests must not deploy to production without explicit release approval. This has not yet been verified against external webhooks or server-side automation. See [Deployment verification](DEPLOYMENT.md).

## Changelog policy

Every feature, fix, security or documentation PR must update
`CHANGELOG.md` in the same change.

- Use chronological headings such as `## 2026-10-14`.
- Identify the PR number once it has been assigned.
- Keep exact live image IDs and operator-specific release evidence in private operating notes.
- Do not invent commit hashes, release dates or deployments.
- Describe technical changes, user impact and relevant limitations.
- Record production deployment separately from GitHub merges.

## Verification checklist

- Builds and relevant tests succeed.
- Existing API contracts remain compatible.
- Secrets and private data are excluded.
- Third-party licenses are reviewed.
- Mobile and keyboard interactions are checked.
- Costs and latency are measured for AI routing changes.
- Rollback steps are documented before deployment.
