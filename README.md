<div align="center">

<img src="docs/assets/vector-readme-logo.svg" width="88" alt="Vector logo" />

# Vector

**A personal AI workbench for reliable, controlled execution.**

Self-hosted · Private development · Built with Next.js

[Vision](VISION.md) &nbsp;·&nbsp; [Architecture](docs/ARCHITECTURE.md) &nbsp;·&nbsp; [Roadmap](docs/ROADMAP.md) &nbsp;·&nbsp; [Security](docs/SECURITY.md)

</div>

---

## A workspace, not another chat wrapper

Vector brings conversations, project work, model providers and file workflows into one application. Its goal is simple: **finish useful work with predictable quality, sensible costs and clear human control.**

The experience is deliberately restrained: dark surfaces, clear typography, precise interactions and no ornamental dashboards.

## Inside Vector

**Conversations and projects.** Work in persistent chat threads, organize tasks in projects and inspect generated files without switching between tools.

**Models and execution.** Configure providers, inspect usage and run background work. Routing, agent execution and workflow modules already exist; their advanced behavior is being benchmarked and improved.

**Control and visibility.** Privacy checks, permissions, approvals and server inspection are part of the existing application. Critical automation is designed to remain subject to owner approval.

The interface is under active development. The current implementation is not presented as a complete autonomous system.

## The interface

Vector includes a cinematic black-hole login, workspace dashboard, conversations, model administration and a server view. Only genuine, privacy-reviewed product captures will be shown here.

[Where to add screenshots and what to capture →](docs/screenshots/README.md)

<!-- SCREENSHOT_GALLERY_START -->
<!-- Add reviewed screenshots here after uploading to docs/screenshots/. -->
<!-- SCREENSHOT_GALLERY_END -->

## How Vector works

Vector chooses its execution strategy based on the work, rather than running an agent team for every request.

**Fast path** — a direct model call for a question, summary or rewrite.

**Artifact path** — structured generation and deterministic renderers for documents and other files.

**Agent path** — tools, investigation and verification for work that genuinely needs multiple steps. Privileged actions require an approval boundary.

Provider quality, cost, latency, privacy and availability are intended to guide routing decisions. That advanced policy layer is still being developed and evaluated.

[Technical architecture and target stack →](docs/ARCHITECTURE.md)

## Technology

The current source contains a **Next.js 16 / React 19** application, with **PostgreSQL**, **Redis**, and application modules for providers, background jobs, artifacts and security policies.

```text
app/          UI, pages and API routes
components/   Interface and cinematic experience
lib/          Providers, routing, jobs, agents and artifacts
public/       Brand and third-party assets
docs/         Architecture, development and security
```

This repository is a **sanitized application snapshot**, not a turnkey deployment. The production environment has configuration and services that are intentionally excluded.

[Development guide](docs/DEVELOPMENT.md) · [Engineering checks](docs/ENGINEERING_CI.md)

## What comes next

Immediate work focuses on reliable model selection, provider fallbacks and measurable quality. Artifact editing, selective agent orchestration, curated skills and additional communication channels follow in later phases.

[See the planned milestones →](docs/ROADMAP.md)

## Security and acknowledgements

Production changes and outgoing messages require explicit approval under Vector's intended operating policy. Deployment integrations outside this repository are **not yet fully audited**. [Read the deployment policy](docs/DEPLOYMENT.md).

The cinematic black-hole experience is adapted from [Gargantua by hasnain7abbas](https://github.com/hasnain7abbas/gargantua-blackhole). Vendored libraries retain their own licensing requirements. [Credits and third-party notices](docs/THIRD_PARTY.md).

---

<div align="center"><sub>Vector · Private project in active development · No general open-source license selected</sub></div>
