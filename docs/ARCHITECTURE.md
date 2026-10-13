# Architecture

> This document separates **existing source modules**
> from the **target stack**.

The presence of a source module is not proof that
the complete feature is production-ready.

## Existing foundation

- **Next.js 16 / React 19** application and API routes.
- **PostgreSQL / Redis** and background-job modules.
- Model routing, provider configuration and usage modules.
- Agent execution, workflows and artifacts.
- Privacy, permission, approval and cost-control modules.
- Docker-backed deployment managed outside this Git snapshot.

## Target execution model

```mermaid
flowchart LR
    UI[Web · Projects · Channels] --> P[Policy and intent router]
    P --> F[FAST · direct provider]
    P --> A[ARTIFACT · deterministic renderer]
    P --> G[AGENT · runtime and tools]
    F --> R[Cost · health · quality router]
    A --> R
    G --> R
    G --> X[Sandbox / HITL approval]
```

## Stack candidates

| Layer | Approach |
| :-- | :-- |
| UI | Vector Design System and selected assistant-ui primitives |
| Run state | Conversation-scoped AG-UI-style events |
| Agents | Mastra vs Pydantic AI benchmark; select one |
| Provider gateway | LiteLLM vs TensorZero benchmark; select one |
| Model selection | vLLM Semantic Router concepts and Vector telemetry |
| Skills | Agent Skills standard, curated Vector registry |
| Evaluations | Promptfoo, Langfuse, OpenTelemetry and custom fixtures |
| Security | Vector Permissions, Presidio, MCP Scan candidates |
| Tools | MCP registry; search → fetch → extract → browser |
| Documents | Existing renderers, Docling, future lossless OOXML edits |
| Execution | Sandboxes and approved host-agent actions |

Heavy services should run on demand to conserve Hetzner resources.

## Agent policy

- Simple rewrites use one model call.
- Documents use structured content and deterministic rendering.
- Research may run independent researchers and synthesize evidence.
- Coding uses exploration, implementation and testing.
- Reviewers run when justified, not on every trivial task.
- Critical changes require explicit owner approval.

## Skill lifecycle

Discover → Source/license check → Schema validation →
Security scan → Sandbox → Offline evaluation →
Compare against existing skill → Approval → Activation.

## Web capability ladder

1. Search with SearXNG.
2. Fetch and parse using HTTP/readability.
3. Extract with Firecrawl or Docling when needed.
4. Interact using Playwright MCP or Browser Use when justified.

## Reliability and privacy

Check capabilities, privacy, budget and provider health before
routing. Record predicted and actual cost, task success,
P50/P95 latency and fallback outcomes.

Never replay an irreversible action without appropriate
idempotency safeguards and authorization.
