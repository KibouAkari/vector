<div align="center">
<img src="docs/assets/vector-readme-logo.svg" width="88" alt="Vector logo" />

# Vector

**A self-hosted AI workspace for conversations, projects and controlled execution.**

[Architecture](docs/ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md) · [Development](docs/DEVELOPMENT.md) · [Security](docs/SECURITY.md)
</div>

## What works today

Vector combines persistent conversations, project files, configurable providers, background jobs, usage tracking, artifact generation and permissioned server tools. The application uses Next.js 16, React 19, PostgreSQL and Redis. It is under active development; deployment and provider behavior still need environment-specific qualification.

The composer shows one active mode: **Auto, Low, Normal, High, Search or Lokal**. Auto uses a deterministic local path for supported, authorized Minecraft statistics and the existing provider/tool paths for other tasks. It is not a universal learned routing policy. Explicit Lokal has no cloud fallback. Its native text path retains the current request and bounds older complete conversation turns.

**Privacy is a separate switch.** With privacy enabled, Vector reviews the outbound message and included context locally. You can cancel, use reversible placeholders, or explicitly send the reviewed text unchanged. Newly read tool evidence is separately protected with placeholders and restored locally in the answer. Original-send is not blanket approval for unknown future secrets. If inspection fails, external submission is blocked. Detection can miss private values; it is not a guarantee of anonymization. Switching privacy off does not grant server permissions or override local-only project routing.

## Execution boundaries

Simple text tasks use a direct path. File work uses artifact builders and renderers. Investigation uses authorized tools and background jobs. Ownership, project access, cost limits and privileged-action approvals remain independent of model choice.

The optional [Minecraft integration](docs/MINECRAFT.md) is a separate service and addon with authenticated transport, local inference, fresh statistics and rate limits. Web releases must not rebuild, restart or reconfigure a running game integration. No server's player records, world, credentials or deployment diary belong in this source tree.

## Source layout

| Directory | Purpose |
| --- | --- |
| `app/`, `components/` | Web UI and authenticated APIs |
| `lib/` | Routing, providers, jobs, permissions, artifacts and privacy |
| `services/` | Separate local services, including optional privacy and Minecraft adapters |
| `integrations/` | Optional Minecraft bridge source |
| `tests/` | Synthetic regression and database integration fixtures |
| `docs/` | Architecture, setup boundaries and engineering guidance |

Start with the [development guide](docs/DEVELOPMENT.md). See [engineering checks](docs/ENGINEERING_CI.md), [deployment policy](docs/DEPLOYMENT.md), [privacy details](docs/PRIVACY_REVIEW.md) and [third-party notices](docs/THIRD_PARTY.md). Secrets and host-specific setup are operator-managed. This is not a one-command production installer.

## Publication status

The current source is being separated from private operating material. Historical Git commits, branches, pull requests and artifacts require a separate review before changing repository visibility. Cleaning the current tree does not erase its history. See [publication checklist](docs/PUBLICATION.md).

[Vision](VISION.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md)
