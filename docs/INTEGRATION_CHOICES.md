# Integration choices

This comparison records architecture choices, not a claim of universal quality,
price or latency leadership. Documentation was reviewed for the November 2026
source update. Verify installed versions, scopes, licenses and commercial terms
before enabling a connection. No paid provider benchmark was performed.

| Area | Options considered | Choice and tradeoff |
| --- | --- | --- |
| Interface | Next.js/React, Tailwind, Motion, Three.js | Retain the stack. Prefixed Tailwind utilities without preflight protect login/intro; Motion handles transitions; lazy Three.js is limited to an evidence-based traffic view. |
| Agent orchestration | Native executor, LangGraph, CrewAI, Goose | Extend the existing durable executor for bounded teams. LangGraph checkpoint/store abstractions are useful when adding complex resumable graphs; a second executor now would duplicate approval/accounting paths. |
| Model gateway | Existing adapters, LiteLLM, OpenRouter | Preserve the unified accounting boundary. OpenRouter stays an optional provider; LiteLLM can be connected via compatible API configuration, but its own budgets are not substituted for Vector reservations. |
| Memory | Explicit PostgreSQL facts, Letta blocks, mem0, Zep, Qdrant | Small encrypted retrieval avoids another service and automatic extraction calls. Letta shared blocks offer explicit context; vector/temporal retrieval may help larger corpora but needs deletion, provenance and privacy evaluation. |
| Monitoring | Checkmk, Wazuh, PatchMon | Use all three for distinct evidence: monitoring state, endpoint-agent visibility and patch inventory. Normalize a bounded subset rather than pretending one replaces the others. |
| Tool protocol | Native tools, MCP, n8n | Native tools already pass through Vector permissions. A future MCP client must validate resource/audience and avoid token passthrough. An n8n deployment is a separate trusted execution boundary, not just an arbitrary webhook URL. |
| Skills | Agent Skills/Anthropic SKILL.md, local instructions | Import exact public commit content as a draft with provenance. Do not execute bundled scripts or inherit declared tool privileges. Keep manual review and immutable versions. |
| Security | Native probes, Nmap, Nuclei, ZAP, Semgrep, Trivy | Bounded native web/network probes plus retained Nmap imports are implemented. Nuclei/ZAP active testing and Semgrep/Trivy code/image jobs need separate sandboxed adapters, allowlisted templates and scope policy. |
| Search/harvesting | Existing public snapshots, SearXNG, Crawl4AI, Firecrawl | Keep retained static snapshots and provenance. A crawler adds browser execution, robots/rate policy, refresh/removal and SSRF surfaces; no unbounded crawler is installed here. |
| Voice/calls | LiveKit Agents, Pipecat, Whisper/Deepgram, Cartesia/ElevenLabs | LiveKit is a strong candidate for a separate realtime transport; interruptions, recording consent, device permissions and hard voice spend admission must ship together. No voice/call deployment is claimed. |
| Media | ComfyUI, fal.ai, Replicate, Krea/Flora | Keep provider-neutral artifact handling. Local ComfyUI suits controlled own workflows; hosted generation needs explicit asset provenance and per-generation price ceilings. Not installed by this update. |
| Coding/devices | GitHub, Cline/Goose, desktop agents | Retain the isolated runner and scoped GitHub connection. Device pairing, signed updates, screen/input consent and revocation are required before an installable host agent can be called supported. |
| Documents | Existing renderers, Pandoc, Typst, WeasyPrint | Preserve working document generation and evidence checks. Add a renderer only when a concrete export needs it; do not replace tested formats for branding. |

The goal is a coherent control surface with a small number of trusted execution
paths. Installing every named framework would increase failure modes and make
cost/privacy attribution harder to verify. Future adapters should use the same
user identity, exact approval, privacy and reservation boundaries.

## Primary references

- [Web Interface Guidelines](https://vercel.com/design/guidelines)
- [Tailwind PostCSS installation](https://tailwindcss.com/docs/installation/using-postcss) and [preflight control](https://tailwindcss.com/docs/preflight)
- [Agent Skills specification](https://agentskills.io/specification) and [Anthropic reference skills](https://github.com/anthropics/skills)
- [LangGraph persistence](https://docs.langchain.com/oss/javascript/langgraph/persistence) and [source](https://github.com/langchain-ai/langgraph)
- [CrewAI source](https://github.com/crewAIInc/crewAI) and [Goose source](https://github.com/block/goose)
- [Letta memory blocks](https://docs.letta.com/v1-sdk/memory/memory-blocks)
- [LiteLLM virtual keys](https://docs.litellm.ai/docs/proxy/virtual_keys)
- [MCP security guidance](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
- [Checkmk REST API](https://docs.checkmk.com/latest/en/rest_api.html)
- [Wazuh manager API](https://documentation.wazuh.com/current/user-manual/api/getting-started.html)
- [PatchMon integration API](https://patchmon.net/docs/patchmon-api-integrations-guide/integration-api-documentation)
- [GitHub issue API](https://docs.github.com/en/rest/issues/issues)
- [LiveKit Agents](https://docs.livekit.io/agents/)

Licenses are evaluated per dependency and per imported skill. An open GitHub
repository is not an automatic grant to execute or redistribute all its content.
