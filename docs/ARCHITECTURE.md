# Vector Architecture

## Current application

Next.js and React provide the web interface and APIs.
PostgreSQL and Redis support persistent and runtime state.

Vector already contains model routing, agent, workflow,
artifact, privacy, permission and background-job modules.

The implementation of each capability must be verified
before treating it as complete.

## Target execution model

```text
Web / Email / WhatsApp / Discord / Voice
                   |
           Identity & Permissions
                   |
            Privacy / Budget
                   |
            Task Classification
              /    |     \\
          Fast  Artifact  Agent
          Path    Path     Path
              \\    |     /
            Events & Telemetry
                   |
          Tools / Sandbox / Approval
```

## Product and interface

Next.js, the Vector design system and selectively chosen
assistant-ui primitives.

Conversation-scoped AG-UI-style events provide run state.

## Agent runtime

Mastra and Pydantic AI will be compared against real tasks.
Only one primary runtime should be selected.

Simple requests use a direct model fast path.

## Provider infrastructure

Benchmark LiteLLM and TensorZero before making a decision.

Dynamic routing should consider:

- Model capability and privacy requirements.
- Task complexity and predicted answer quality.
- Provider health and previous success rate.
- P50 and P95 response latency.
- Token costs and cache probability.
- User permissions, budget and preferences.

## Skills

Agent Skills standard with a curated Vector registry.

Skill lifecycle:

Discover → Validate → License check → Security scan
→ Sandbox → Offline evaluation → Comparison
→ Approval if required → Activation.

Separate Builder Skills from Runtime Skills.

## Web access

1. SearXNG search.
2. HTTP fetch and readability.
3. Firecrawl or Docling extraction.
4. Playwright MCP / Browser Use when interaction is needed.

## Observability and evaluation

Langfuse, OpenTelemetry and Promptfoo are evaluation
candidates alongside Vector-specific measurements.

## Security

Presidio, MCP Scan, permission enforcement, approval
workflows, audit logging and isolated execution.

## Artifacts

Existing renderers remain the foundation.

Docling provides document input intelligence.

A future lossless OOXML edit engine should preserve
existing files, formatting and unchanged content.

## Infrastructure

Use expensive or resource-intensive services on demand.

Developer execution should be isolated in a sandbox,
with trusted host operations going through an approved
host agent.
