# Local inference rollout

Status: hardware assessment and evaluation plan, not an installed or activated model.

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
