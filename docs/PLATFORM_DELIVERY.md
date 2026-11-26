# Platform control, skills and security workspace

Source delivery, 26 November 2026. This is not a production rollout or a claim
that all integrations are connected. No paid model call is needed for the tests,
skill administration, platform inventory or security evidence reports below.

## Delivered in this change

| Capability | Concrete behavior | Boundary |
| --- | --- | --- |
| Platform control | `/platform` and `/api/platform/capabilities` map implemented, partial and planned areas | Owner-only source inventory; not live health or a generic execution gateway |
| Approval administration | Global decision API, approval page and policy inspection require platform owner | A policy entry is not proof that every legacy adapter enforces it |
| Project skills | Editors create instruction drafts; owners activate an exact name/content hash or retire a skill | Immutable records, at most 50 per project, 6000 instruction characters, no executable code or tool grants |
| Skill use | Select up to three active project skills in project chat | Server revalidates project/status; context passes through privacy review; duplicate request identity includes skill content hash |
| Security evidence | Define project scope, approve its digest, import Nmap XML and download PDF/Markdown/original XML | Owner-only evidence workflow; no scan or exploitation is executed by this workbench |
| Economical workflow | Quick mode bypasses separate planner/reviewer stages for routine work | The worker can still need several tool/provider turns; this is not a universal one-call guarantee |

Skill activation is a review decision about text, not execution authority. Skills
are supplied as selected task guidance rather than new privileged system policy.
They cannot add tools, change provider consent or grant host access. Selected text
is covered by project privacy review before a cloud-bound job is stored. A retired
or wrong-project selection fails before enqueue. New revisions are separate
drafts; there is no in-place editing of activated content.

## Security workflow

1. Select a project and declare up to 32 exact IPv4/IPv6 targets, an authorization
   reference and an expiry within seven days. The UI initially uses 24 hours.
2. Review and approve the exact stored scope digest. No network action occurs.
3. Import an Nmap XML result obtained through your separately authorized tooling.
4. Vector validates scope and structure locally and records an immutable evidence
   hash and encrypted original XML. A replay with the same hash is idempotent;
   different evidence cannot replace a completed assessment.
5. Download a paginated PDF, editable Markdown or original XML. Reports disclose
   evidence provenance, authorization, missing-host coverage and limitations.

An open port is informational, not a verified vulnerability. The importer cannot
attest that an uploaded scan was really run or establish exploitability. It does
not invent CVEs, CVSS scores, security grades or a clean bill of health. Missing
addresses prevent a whole-scope coverage conclusion. Existing chat network tools
are a separate execution path; approving an evidence-import scope does not grant
those tools new authority.

Evidence is limited to 2 MiB, 50,000 XML elements, bounded nesting and 2048 explicit
port records. JSON requests are size/time bounded. External/internal entity
schemas, non-Nmap roots, malformed XML, failed runs, unsupported protocols,
duplicate records and out-of-scope addresses are rejected. Original XML is never
served inline. Normalized observations and scope use the existing protected
PostgreSQL storage model; they are not individually field-encrypted. Protect
volumes and backups. Sensitive security data is not sent to model providers by
this importer/report renderer.

SAX parsing uses pinned ISC-licensed `saxes@6.0.0`. Nmap binaries are not vendored
or installed by this change. Any future scanner distribution needs its own
license and runtime review. PDF uses the existing pdf-lib dependency and standard
fonts; unsupported glyphs are visibly replaced. Reports are evidence summaries,
not autonomous penetration-test attestations.

## Integration choices and comparison criteria

The following is an integration decision map, not a paid benchmark or a promise
of superiority. Products may overlap; evaluate the exact API, version, terms,
privacy and license before implementation. Compare against Vector's current task
completion, supported citations, latency, actual CHF and recovery behavior.

| Area | Products under consideration | Direction for Vector |
| --- | --- | --- |
| General assistant | ChatGPT, Claude, Gemini, Hermes, OpenClaw | Use permitted model APIs and learn from task workflows; retain one Vector identity and authorization layer |
| Coding | Goose, Cline, Antigravity, Windsurf, GitHub bot | Isolated worktrees, patch previews, exact repository permissions, tests and approval before publishing changes |
| Knowledge workspace | Obsidian, Logseq, Tana, Capacities, Mem, Recall, NotebookLM | Preserve sources, links, editable artifacts and export; do not replace the existing database before retrieval measurements justify it |
| Memory | Letta, mem0, Zep, Qdrant | Separate conversations, approved memories and source evidence; support correction, provenance, expiry and deletion before choosing an engine |
| Voice/calls | LiveKit Agents, Pipecat, Whisper/Deepgram, Cartesia/ElevenLabs | Evaluate one transport/pipeline with interruption, explicit recording policy and per-session spend limit; no duplicated parallel voice stacks |
| Channels | Mail, Discord, WhatsApp and other providers | Signed inbound events, identity linking, deduplication, scoped secrets, draft/approve/send, delivery receipts and bounded retries |
| Tools/workflows | MCP, n8n, LangGraph, CrewAI | One execution owner and permission/budget contract. Add narrow adapters rather than nesting several agent loops |
| Models | LiteLLM, OpenRouter and current broker | Select eligible providers by task/privacy and measured quality/cost. Keep local-only mode without silent cloud fallback |
| Creative studio | ComfyUI, Higgsfield, Krea, Flora, Fal.ai, Replicate; Flux/Kling/Wan | Optional versioned asset jobs, preview, cancellation and spend controls; GPU work belongs on capable devices or explicitly approved providers |
| Search/extraction | SearXNG, Crawl4AI, Firecrawl | Search discovers; fetch/extraction retains source evidence. Do not equate a snippet with a fully ingested source |
| Security | Sentra, PentestGPT, CAI, Nmap, Nuclei, ZAP, Semgrep, Trivy | Typed evidence imports and explicitly scoped executors. Tool observations and model hypotheses stay separate from confirmed findings |
| Documents | Current renderers, Pandoc, Typst, WeasyPrint | Select by document fidelity and editable output; keep deterministic rendering and provenance |
| Operations | Coolify, monitoring, API/key inventory | Exact release identities, credential revocation/rotation, health, audit, backup/restore and rollback |
| Trading | Freqtrade, NautilusTrader | Optional separate domain, simulation first, explicit account authorization and hard risk controls |

Primary references checked for this direction:

- [LiveKit Agents](https://docs.livekit.io/agents/) documents voice agents,
  frontend/telephony and agent lifecycle capabilities.
- [Pipecat](https://docs.pipecat.ai/overview/introduction) documents a voice and
  multimodal pipeline ecosystem with client SDKs and self-hosted options.
- [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture)
  defines context exchange; it does not itself supply Vector's permissions,
  workflow engine or model policy.
- [n8n tool review](https://docs.n8n.io/advanced-ai/human-in-the-loop-tools/)
  provides a reference for pausing a tool action for human review.
- [Mem0](https://docs.mem0.ai/introduction) documents cross-session memory.
- [ComfyUI](https://docs.comfy.org/) documents node workflows and application/API
  integration for visual generation.
- [Nmap XML](https://nmap.org/book/output-formats-xml-output.html) is the tool's
  recommended programmatic output interface.

These documents establish candidate roles, not tested integration performance or
current prices. No subscriptions, bot accounts or provider keys are created.

## Contracts still needed before connecting privileged adapters

A future device agent should accept a signed, expiring command envelope binding
user, paired device, run ID, nonce, exact capability, resource scope, input digest,
approval and budget reservation. Pairing must be user initiated and revocable.
Screen capture, input injection, files and command execution need separate grants.
Windows, macOS and Linux installers must be signed/verified and support safe
updates. Never expose a generic unauthenticated remote shell.

A future channel adapter must bind external sender to a Vector principal. Incoming
messages are not authorization to send mail, modify GitHub or access another
project. Store delivery idempotency before sending; a lost acknowledgement cannot
trigger a blind repeated message or purchase. Check revocation at execution.

A future multi-agent team needs shared hard call/spend reservations, scoped tool
sets, a bounded task graph, cancellation and independent review criteria. Use
specialists only where their measured result improves on one worker. Model
capability, health and price must be checked before selection; model marketing or
a static score does not prove it is the best option for an actual task.

## Release qualification

The default tests use synthetic data and provider stubs. Real authenticated API
CI exercises scope approval, immutable evidence, reports, owner restrictions and
skill lifecycle. There are no paid model tests, scans, calls or outbound messages.
A live web release still requires staging and exact app/worker qualification.
Keep the independent Minecraft integration and other workloads unchanged.

Remaining release work includes production staging, document ingestion, source
lifecycle controls, cross-adapter budget reservations, real scanner executors,
voice/channel/device adapters and representative model quality evaluation. A
small owner-selected live evaluation can be budget capped later; it is not run
implicitly by this change.
