# Vector workspace and harvester plan

Status: proposed product direction, 26 November 2026. This document is a
source-based assessment, not a production audit or a claim of feature parity.

## Product promise

Bring a goal, a document or a source. Vector finds the relevant information,
keeps its origin and permissions, performs useful work and leaves an editable,
verifiable result in the project. The user can follow progress and continue
later without reconstructing the task.

The first complete journey is **collect sources → understand them → answer
with evidence → create an artifact → revisit it when the sources change**.
Finish that journey before adding a gallery of unrelated integrations.

## What the source establishes

| Area | Evidence in this repository | Remaining qualification |
| --- | --- | --- |
| Workspace | Project, conversation, file and task routes | Real user journeys, usability and recovery |
| Knowledge | Encrypted file storage; PostgreSQL text chunks and full-text search | Extraction coverage, revision tracking, citations and retrieval quality |
| Execution | Agent, workflow and background-job modules | Restart recovery, cancellation and duplicate-action tests across the full journey |
| Models | Provider configuration, usage and routing modules | Quality, latency and actual cost on representative tasks |
| Control | Privacy, project access, permission and approval modules with tests | Exact-release live qualification; new connectors must preserve these boundaries |
| Research | Provider web-search integration in the agent | A reusable, project-owned collection with fetch/extract state and source revisions |

A module name or passing unit test is not proof of a complete user capability.
No current live server configuration was inspected for this plan.

## First implementation in this change

Project indexing previously deleted the old chunks before inserting their
replacements one at a time outside a transaction. A later insert failure could
leave a partial searchable document. Replacement now uses one PostgreSQL
transaction and locks the owning file row. Other readers see the prior committed
index until replacement commits; failure rolls back the whole replacement.
Indexing a file under a different project is rejected.

This protects index replacement, not the entire upload/edit pipeline. File
storage, file metadata and extraction still need a versioned ingestion lifecycle.
The previous index may describe an older file revision after a failed update.
This change does not claim fresh provenance or a complete harvester.

## Delivery sequence

Acceptance targets below are proposed gates, not measured results. Start with
synthetic fixtures, then a small owner-authorized staging collection. Keep
private records and deployment evidence outside Git.

| Milestone | User-visible result | Acceptance gate |
| --- | --- | --- |
| 1. Source collection | Import a URL or file into a project; see queued, extracting, indexed, partial or failed state and retry safely | Every imported item has a visible outcome; original content hash, origin, acquisition time and extraction method retained; no silent partial success |
| 2. Evidence workspace | Ask questions across the collection; open the exact supporting passage | Each source-dependent factual claim in the evaluation set links to a retained passage; unavailable or conflicting evidence is disclosed; no cross-project retrieval |
| 3. Reliable execution | Follow a research/artifact job, interrupt it and resume it | Restart and timeout fixtures retain progress; cancellation is visible; repeated delivery does not repeat external side effects |
| 4. Useful memory | Retain approved preferences, decisions and project facts; inspect, correct and remove them | User/project scopes, provenance and expiry are explicit; corrections supersede prior facts; private memories never leak between users |
| 5. Action workspace | Search connectors and run bounded workflows with previews for writes | Connector health, permissions, estimated cost and effects are visible; revocation applies before execution; irreversible actions are never silently replayed |
| 6. Artifact and media studio | Produce and edit documents, images and later audio/video in the same project | Original and derived files remain linked; editable outputs and previews work; failures are recoverable; provider costs recorded |

For milestone 1, use the existing database, file storage and worker boundary.
Do not introduce a graph database, a second vector database or an orchestration
framework merely to rename existing functionality. Start with one import
adapter and one extraction path; introduce alternatives when a measured gap
requires them. A source record is not a generated summary: preserve both.

Web ingestion must enforce HTTP(S), redirect and resolved-address checks, bounded
size/time, content-type handling and project authorization at acquisition and
retrieval. Website text remains untrusted evidence, never a tool instruction.
Private sources must retain the existing outbound-data consent rules.

## How the named tools fit

These are candidate roles to evaluate, not installed integrations, endorsements
or a feature-by-feature market comparison. Confirm APIs, licenses, hosting,
privacy and costs for the exact selected version before adoption.

| Capability | Candidates and references from the product discussion | Decision |
| --- | --- | --- |
| Assistant and coding experience | ChatGPT, Claude, Gemini, Hermes, OpenClaw, Goose, Cline, Antigravity, Windsurf | Benchmark task completion and interaction patterns; keep Vector's own workspace and access model |
| Connected knowledge | Obsidian, Logseq, Tana, Capacities, Mem, Recall, NotebookLM | Support useful linking, source inspection and export; import through documented formats/APIs where permitted |
| Memory and retrieval | Letta, mem0, Zep, Qdrant | First define scope, provenance, correction and retrieval evaluations; adopt only the missing layer |
| Model access | LiteLLM, OpenRouter | Evaluate one gateway against current routing; preserve explicit local-only mode and cost attribution |
| Tools and durable work | MCP, n8n, LangGraph, CrewAI | One tool contract and one execution owner; add adapters rather than several competing agent loops |
| Search and ingestion | SearXNG, Crawl4AI, Firecrawl | Search identifies candidates; fetching and extraction create retained evidence; snippets alone are insufficient |
| Documents | Existing Vector renderers, Pandoc, Typst, WeasyPrint | Select by output fidelity, editability and measured conversion gaps |
| Creative studio | ComfyUI, Higgsfield, Krea, Flora, Fal.ai, Replicate; Flux, Kling, Wan | Optional job adapters with versioned assets, status, cancellation and per-job spend |
| Voice | LiveKit Agents, Pipecat, Whisper, Deepgram, Cartesia, ElevenLabs | Later end-to-end voice journey with explicit recording and retention controls |
| Security workspace | Sentra, PentestGPT, CAI, Nuclei, Nmap, OWASP ZAP, Semgrep, Trivy | Separate authorized targets, read-only assessment and approved changes; normalize evidence rather than treating generated findings as confirmed |
| Hosting | Coolify and existing deployment tooling | Keep one accountable release process with health checks and rollback |
| Trading | Freqtrade, NautilusTrader | Separate optional domain; simulation first, with explicit limits and authorization before any live account action |

The primary documentation supports evaluating human-reviewed tool calls in
[n8n](https://docs.n8n.io/advanced-ai/human-in-the-loop-tools/), thread checkpoints
versus longer-term stores in
[LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence), and
provider access/accounting through
[LiteLLM](https://docs.litellm.ai/docs/proxy/quick_start).
These capabilities do not by themselves establish that adding those systems
will improve Vector. Evaluate against the current implementation first.

## Measure the product, not the integration count

Maintain a small published synthetic task suite covering:

1. A question answered from several project sources, with passage links.
2. A changed document whose previous claim must no longer be presented as fresh.
3. Conflicting sources and a source that cannot be extracted.
4. A research report with working source links and an editable artifact.
5. A stopped/restarted job and an explicitly cancelled job.
6. A private project, revoked connector and malicious source instruction.
7. A normal short question that must not start an expensive workflow.

Record completion, unsupported claims, citation support, retrieval coverage,
P50/P95 time to useful output, actual CHF per task and duplicate effects. Compare
with the current Vector baseline before adopting any new framework. Agree latency
and cost limits per task class instead of promising one universal response time.

## Release and external reporting

Keep Minecraft independent. No service deployment is performed by this plan.
Qualify the exact web app/worker release in staging before an owner-authorized
rollout, and retain immutable rollback evidence privately.

The linked Undercode article could not be retrieved during this assessment.
No findings are attributed to its body. Obtain a copy before answering its
specific criticisms. Publish a release with concrete demonstrated journeys,
known limitations and reproducible checks; favourable coverage should follow
verifiable product improvements, not unsupported comparison claims.
