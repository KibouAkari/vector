<div align="center">
  <img src="docs/assets/vector-banner.svg" width="100%"
       alt="Vector — Reliable intelligence. Deliberate execution." />

  <p><strong>
    An independent, self-hosted AI workbench for reliable work,
    controlled autonomy and measurable quality.
  </strong></p>

  <p>
    <a href="VISION.md">Vision</a> ·
    <a href="docs/ARCHITECTURE.md">Architecture</a> ·
    <a href="docs/ROADMAP.md">Roadmap</a> ·
    <a href="docs/DEVELOPMENT.md">Development</a> ·
    <a href="docs/THIRD_PARTY.md">Credits</a>
  </p>

  <p>
    <img alt="Next.js"
         src="https://img.shields.io/badge/Next.js-16.4-151d1b?style=flat-square" />
    <img alt="React"
         src="https://img.shields.io/badge/React-19.3-151d1b?style=flat-square" />
    <img alt="PostgreSQL"
         src="https://img.shields.io/badge/PostgreSQL-17-244b43?style=flat-square" />
    <img alt="Status"
         src="https://img.shields.io/badge/Status-active%20development-60c59a?style=flat-square" />
  </p>
</div>

## The workspace

Vector combines conversational AI, projects, file workflows,
model connections, usage reporting, background jobs and
owner-controlled permissions in one interface.

Its long-term direction is a personal **AI operating system**,
not just another chat wrapper.

<table>
<tr>
<td width="50%">
<img src="docs/assets/chat.svg" width="30"/>
<br/><strong>Chat & projects</strong>
<br/>Conversations, structured workspaces and generated files.
</td>
<td>
<img src="docs/assets/routing.svg" width="30"/>
<br/><strong>Model infrastructure</strong>
<br/>Provider connections, usage and evolving task routing.
</td>
</tr>
<tr>
<td>
<img src="docs/assets/artifact.svg" width="30"/>
<br/><strong>Artifacts</strong>
<br/>Document generation and file handling,
with richer editing planned.
</td>
<td>
<img src="docs/assets/security.svg" width="30"/>
<br/><strong>Control & permissions</strong>
<br/>Privacy rules, owner approvals and audit-oriented execution.
</td>
</tr>
</table>

## Product screenshots

The current interface includes a cinematic login, usage dashboard,
conversation workspace, model administration and server overview.

Genuine, reviewed images will appear here after the
[privacy checklist](docs/screenshots/README.md) is completed.

**No mockups are presented as working product screenshots.**

## Architecture at a glance

```mermaid
flowchart TD
    A[Chat · Projects · Future channels] --> B[Identity · Policy · Cost guardrails]
    B --> C{Task router}
    C -->|Simple| D[Fast path: direct model]
    C -->|Files| E[Artifact path: structured content + renderer]
    C -->|Tools| F[Agent path: plan · execute · verify]
    D --> G[Provider selection & telemetry]
    E --> G
    F --> G
    F --> H[Sandbox · Approvals · Audit]
```

The gateway, AG-UI event model, advanced agent runtime and
self-improvement workflows are **target architecture**,
not claims of deployed integrations.

Read the [architecture](docs/ARCHITECTURE.md) for details.

## Codebase

```text
app/          Next.js pages and API routes
components/   UI, cinematic transitions and reusable controls
lib/          Routing, providers, agents, artifacts and policies
public/       Brand assets and licensed third-party assets
docs/         Vision, architecture, roadmap, security and credits
```

## Development

This is a private development snapshot,
**not a ready-to-run public deployment**.

Production secrets, user data, databases and infrastructure
configurations are intentionally excluded.

```bash
# For a vetted development checkout only
npm ci
npm run build
```

A working deployment also requires environment-specific services
and configuration. Do not assume this starts a production environment.

## Principles

**Fast by default. Verified when needed. Secure by design.**

Vector favors a direct answer for simple tasks, deterministic
rendering for artifacts, and specialized agents only when
tools or deeper reasoning are justified.

See [Vision](VISION.md) ·
[Security](docs/SECURITY.md) ·
[Contributing](CONTRIBUTING.md) ·
[Acknowledgements](docs/THIRD_PARTY.md).

<sub>
Vector is under active development.
No general open-source license has been selected for Vector itself.
</sub>
