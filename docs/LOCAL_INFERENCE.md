# Local inference rollout

Status: isolated installation and smoke benchmark prepared; no observed server installation or Vector activation yet.

## Execution model

Use existing deterministic host inspection and local aggregations first. A local
model can classify requests, extract structured fields and summarize bounded
evidence. Invoke a cloud model only for a capability gap or a justified review,
not automatically after every local response. Count local tokens separately from
paid API tokens; zero API spend does not mean zero infrastructure cost.

Reuse the existing conversation/project retrieval, user isolation, privacy,
skills registry and tool permissions. Memory belongs to Vector's retrieval
layer and must not be stored by mixing users into shared model prompts or weights.
The model proposes tool calls; existing trusted tool executors perform scans.
No unrestricted host shell or Docker socket is added to an inference container.

## Hardware and serving

Run `scripts/diagnostics/local-inference-capacity.py` on the actual server before
choosing a model or resource limits. Free RAM alone is not a throughput benchmark.
Measure GPU VRAM, CPU capability, competing service load and memory headroom.

Prefer an internal Ollama service for the initial Linux server evaluation.
Bind its endpoint only on the trusted container network, pin the runtime image and
model artifact, and connect through Vector's existing local provider adapter.
Start with one loaded model and bounded concurrency/context. Select CPU/RAM/GPU
limits after measurement so Minecraft, PostgreSQL and Vector retain headroom.

Ollama supports timed unloading with `OLLAMA_KEEP_ALIVE` and per-request
`keep_alive` on its native API. A short warm window avoids reloading weights
for each follow-up. Unloading model weights and stopping the server process are
different operations; record cold-start latency separately from warm latency.
Do not assume the OpenAI-compatible endpoint accepts native Ollama options.

## Candidate evaluation

The user's named candidates are Qwen3 8B, Hermes 3 Llama 3.1 8B and Dolphin 3.0
Llama 3.1 8B. Compare quantized artifacts on the measured hardware rather than
declaring a winner from size or an "uncensored" label. For a community-modified
Qwen checkpoint, verify the exact publisher, revision, license and quantization;
the base Qwen model card does not certify the modified checkpoint's behavior.

If CPU inference is too slow, include a smaller model in the benchmark. For
Qwen3, test non-thinking mode for routine extraction. Do not assume a GPU is
present or promise a tokens-per-second figure before measurement.

Acceptance fixtures should cover valid tool JSON, complete field extraction,
source-faithful summaries, authorized security diagnostics, missing evidence,
project/user isolation and refusal/error handling. Measure task success,
wrong tool calls, cold/warm latency, output speed, peak RAM/VRAM, and impact on
existing services. Promote the exact model/runtime configuration only after
these checks, with a fallback and a reversible activation plan.

## Primary references checked on 2026-10-15

- [Ollama FAQ and unloading](https://docs.ollama.com/faq)
- [Qwen3 8B model card](https://huggingface.co/Qwen/Qwen3-8B)
- [Nous Hermes 3 8B GGUF](https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF)
- [Dolphin 3.0 Llama 3.1 8B](https://huggingface.co/dphn/Dolphin3.0-Llama3.1-8B)


## CPU pilot (2026-10-15)

Measured host: i7-7700, eight logical CPUs, 62.59 GiB RAM, 42.97 GiB available,
Intel integrated graphics and no NVIDIA GPU. Existing swap usage means headroom
must be monitored rather than treating all RAM as unused.

`scripts/deploy/local-inference-pilot.py` installs Ollama 0.40.4 by the immutable
Linux/amd64 image digest and imports two publisher GGUF artifacts by exact commit,
size and SHA-256. The model files total approximately 5.56 GB; imports and Ollama
storage retain separate copies. Allow at least 20 GiB free disk space.

| Model | Intended evaluation role | License |
| --- | --- | --- |
| Nous Hermes 3 Llama 3.1 8B Q4_K_M | Bounded summaries and technical interpretation | Llama 3.1 community license and use policy, inherited by the fine-tune |
| Qwen3 0.6B Q8_0 | Short extraction and classification; non-thinking mode | Apache-2.0 |

Hermes model weights and the separate Nous Hermes Agent application are different
components. This pilot installs weights in Ollama and adds no independent agent
application or unrestricted shell. The small Qwen model is an evaluation helper,
not an assertion of equivalent quality or uncensored behavior.

The service uses a dedicated internal Docker network with no published ports,
no host or Docker socket, read-only imports/root filesystem, bounded logs,
12 GiB memory without container swap, two CPU equivalents, two inference threads,
one loaded model and one concurrent request. Context defaults to 2048 tokens,
output to 256, and inactivity unloads weights after five minutes. The API process
stays available; an unloaded model has a cold-load delay. No Vector network,
container, provider setting, database or user memory is modified.

The script performs public synthetic missing-value extraction once cold and once
warm per model, records token counts, load time, elapsed time and generation rate,
and explicitly unloads weights. This is a smoke test, not a tool-calling,
German/security evaluation, statistical performance study or task-quality approval.
`pilot-result.json` is stored under `/root/vector-workspace/local-inference`.
On test failure the new inference container is stopped. Existing pilot resources
are never silently replaced; inspect a failed run before retrying.

Run the script only through `/root/vector-workspace/bin/run`. To roll back this
pilot, run `sh /root/vector-workspace/local-inference/rollback.sh`. It stops/removes
only the named inference container and network, retaining imported model files
and the dedicated volume. It does not alter production.

### Following the measured pilot

Add bounded worker roles to Vector's existing job execution rather than replacing
its framework: a small extractor, a Hermes summarizer and a selective cloud
reviewer. The shared CPU scheduler must enforce global concurrency one even
across user jobs. Different roles can reuse one model; multiple installed models
do not imply simultaneous inference. Bound total subtask count, context, output,
time and delegation depth. A subagent must inherit the initiating user's project,
retrieval, skill and tool scope, with no escalation or user-memory mixing.
Cloud review is conditional and budgeted, not automatic. Deterministic server
scans stay in the existing Host Agent. Local workers receive compact evidence.

Activation requires the measured pilot, adapter/tool-call and permission tests,
and competing-service latency observations. The pilot does not yet implement
this scheduler, worker routing, embeddings, new MCP servers, or cloud review.
Use the existing PostgreSQL retrieval first; evaluate a separate vector database
only when corpus size and retrieval tests justify the operational cost.


## Observed pilot and first worker integration (#28)

The owner's server run completed successfully on 2026-10-15. Hermes generated
about 5 tokens/s (16.168 s cold, 2.371 s warm for an eleven-token fixture); Qwen
about 35–36 tokens/s (1.942 s cold, 0.407 s warm for thirteen tokens). Both returned
correct missing-value JSON in that one fixture. These are short smoke measurements,
not throughput or reliability guarantees for long prompts or real security tasks.
After explicit unloading, no model weights were loaded and the idle service used
about 214 MiB. Ollama advertises completion only for this Hermes import and tool
support for Qwen. This does not validate Qwen's tool-call accuracy.

The first code integration is `server_local_worker`, behind
`VECTOR_LOCAL_WORKERS=1` and the existing server permission. Disabled by default.
The requesting job must carry an authenticated user/job identity and the server
permission; all evidence is passed explicitly from that job. Workers perform no
additional retrieval, read no global/project memory, inherit no tools and cannot
spawn other workers. Project/skill context can be included only in the compact
already-authorized evidence passed by the parent agent. This is bounded delegation,
not a new autonomous memory or skill system.

Two roles use fixed model IDs: `extract` uses Qwen and requires a JSON object;
`summarize` uses Hermes. The combined serialized task/evidence may not exceed
2048 UTF-8 bytes, with explicit rejection rather than truncation. Native requests
use 4096 context tokens, 192 maximum output tokens, two threads, a 90-second timeout
and no retry or cloud fallback. This context differs from the initial pilot and
must be validated by the new evaluation. One PostgreSQL session advisory lock
limits admission across processes; busy tasks fail promptly. Two attempts are
allowed per shared job context, including failures. Ollama additionally retains
its server-side single-request/single-model limits.

Provider-reported local tokens enter the existing per-response job ledger before
output validation, at zero API rates. Unknown usage remains explicitly incomplete.
Local infrastructure/energy is not included in API spend. Transport failures
without a usage response cannot produce a measured token count. Outputs are marked
interpretation only, not independently verified. The parent decides whether review
is justified. A paid parent orchestration call is still paid; this feature does
not yet make arbitrary Auto chats fully local or guarantee a cost saving per task.

`scripts/deploy/evaluate-local-workers.py` runs the actual worker core in a
short-lived container on the inference-only network. It checks installed runtime
and model digests, uses only synthetic English/German fixtures, captures accounting
in memory without database writes, verifies the app container was unchanged, and
unloads models/removes the evaluator afterwards. It requires an idle inference
service and exact `VECTOR_LOCAL_WORKER_REV`. There is no Vector activation.
`scripts/deploy/stage-local-workers.sh` separately validates the application build,
unit tests, restored isolated PostgreSQL fixture and existing HTTP permissions,
with the feature disabled and no real model calls. Both results are required
before a source/image-pinned application release and persistent network/env
activation. No production connection or provider row is added by this PR.

Rollback after a future activation: disable `VECTOR_LOCAL_WORKERS`, remove only
the added app/worker connections to the inference network and use the release's
source/image rollback. Leave model storage intact. No schema migration or new
package dependency is introduced by worker integration.


### First integration test and corrective evaluation

The owner ran exact revision 17c3e62: application staging passed, but Qwen failed
both extraction fixtures (arrays instead of scalar/null; translated keys/string
numbers). Hermes passed its fixture. Activation remains blocked. Fast generation
alone is insufficient for selecting an extractor.

Extraction now requires one to eight explicit `fields` entries with fixed names
and integer/number/string/boolean types. Each permits null for absent evidence.
The native Ollama `format` receives the resulting closed JSON schema, the prompt
includes that schema, and Vector independently validates exact keys and types.
No silent renaming, coercion or empty-array repair is allowed. Reported usage is
still recorded before validation failures. This guarantees only structure; factual
values still require the expanded real-model fixtures and source checks.
Summary calls use `fields: []`. The tool contract was not yet activated.

The first production fingerprint comparison also reported a difference. Because
that evaluator did not save its snapshots, the logs do not identify which field
changed. Docker mount/alias ordering is now normalized, but a genuine previous
change is not ruled out. New evaluations first require the confirmed live app
image, save private before/after JSON snapshots and name every changed field.
Offline tests verify reordered lists compare equal while actual image, container,
restart, mount-permission and address changes remain detectable. No production
repair or restart is attempted by evaluation.
