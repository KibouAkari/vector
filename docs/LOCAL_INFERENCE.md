# Local inference

The web application can use a private native model endpoint for explicit local text requests and bounded local worker tasks. This is a separate execution path from a cloud provider calling a local helper: only the explicit local path has no cloud parent or cloud fallback.

`VECTOR_LOCAL_WORKERS=1` enables the existing native adapter. The runtime must supply the private service, pinned model files, offline operation, strict CPU/memory limits and the shared admission lock. Keep model endpoints unexposed and avoid host/Docker socket access in inference containers. Light health checks should not wake model weights; idle unloading returns memory between bursts.

Local text context is bounded. The current user request stays exact; oldest complete conversation turns are omitted when needed. An oversized current request is rejected explicitly. Native text chat does not gain arbitrary host tools. Supported, configured Minecraft statistics take a deterministic read-only path; other live investigations require the existing authorized server-tool route. Never substitute an invented answer for absent data.

The web native text adapter and optional Minecraft assistant are separately versioned consumers. Do not replace their models, mounts or admission roles as an incidental web deployment. Small models can answer confidently and incorrectly even with a valid transport/template. Qualify factual correctness, output policy, cold/warm latency and actual usage on representative tasks before selecting a candidate. Do not weaken safety or completeness checks to pass a failed model.

Record real native prompt/generation tokens and time where returned; preserve unknown usage as unknown. Local model calls incur no provider API fee but still consume CPU, memory and latency. Encoder privacy scans have separate metrics. Shared-slot contention, deadlines, cancellation and release after exceptions need meaningful regression coverage.

Operator benchmarks, runtime image/model hashes, source pins, live database roles and rollout/rollback evidence are private operating material. A source test or README statement is not a completed live model qualification.
