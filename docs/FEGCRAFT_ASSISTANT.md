# FEGCraft Minecraft chat integration

Status: source components and offline checks, not installed or activated. The owner requested Minecraft chat as the only input; use the existing Discord Integration 3.2.1 for forwarding replies to its configured chat output channel. No separate Discord bot, token, webhook or message listener is introduced.

## Verified API and packaging

The official 26.2 integration branch at 0aae1d0818f8fbced5aa12f99c4c56208448c8aa calls the common onMinecraftMessage hook for genuine player chat, after its permissions/vanish/link privacy checks. Discord-origin messages use sendIngameMessage and do not invoke this hook. Therefore Discord-origin questions do not automatically trigger Vector in this scope.

The actual public Fabric 26.2 / 3.2.1 release from the project's Modrinth distribution has SHA256 75e039ac6c8edad3c9423c91638ffd15d7c9b95dadb60bf69349da838afbf337 (upstream SHA512 also verified). Its common API is a nested META-INF/jars/dcintegration.common-3.2.1.jar, not root classes. Build and preflight handle this packaging explicitly. Its fabric.mod.json declares MIT. We compile against its shaded API, bundle only our classes/metadata, and do not redistribute its library.

Primary sources:
- https://github.com/ErdbeerbaerLP/DiscordIntegration/tree/0aae1d0818f8fbced5aa12f99c4c56208448c8aa
- https://github.com/ErdbeerbaerLP/DiscordIntegration-Core
- https://modrinth.com/plugin/dcintegration/version/3.2.1-26.2

## Components and boundaries

integrations/fegcraft-addon is a Discord Integration addon, not a second Fabric mod/bot. It returns false from the player-chat hook, preserving ordinary forwarding. It captures plain text, resolves the current authenticated UUID/name on the Minecraft server thread and sends only addressed messages to the fixed private local endpoint. HTTP/model work never blocks the game thread. One active HTTP request with a single bounded completion-handoff slot (admission reopens before visible delivery), bounded request/response sizes, no redirects/proxies and fixed deadlines protect latency/resources. Unaddressed/unsupported/busy events do not produce public spam.

The addon schedules all game access back onto the server thread, prints a mint [Vector] prefix and sends the answer exactly once through the existing integration's configured chat output channel. A separately configurable public PNG avatar is optional. A custom Minecraft head/logo has NOT been implemented: this needs supported client presentation/resource assets. It is not silently claimed by the text prefix.

services/fegcraft-assistant is a separate private Python service. HMAC-SHA256 signs the exact request body and a short-lived timestamp. Requests carry an authenticated UUID/name plus per-session event ID. SQLite stores HMAC-hashed principal/event IDs and admission times only, never prompts, replies, names or UUID plaintext. Three requests per user and twelve globally per minute, replay rejection and bounded state survive restart. One active service request, at most eight transport connections and no HTTP command/tool API.

Saved statistics use the existing bounded collector and seven-counter distance convention. Rankings, ties, player records and totals are calculated deterministically without a model. Missing/unnamed/unreadable data refuses definitive rankings. Unknown player queries are not silently replaced with leaders. Responses identify saved-file provenance; they are not claims about unsaved live player state.

The optional knowledge adapter has one fixed local Ollama destination and Qwen model, no cloud fallback and no private Vector memory. It acquires the same PostgreSQL advisory CPU slot as NER/Ollama work, using a future dedicated restricted role rather than application credentials. Only bounded Minecraft questions and approved mod IDs reach it. Request policy, short structured model output and a second addon filter reject commands, secrets/administrative topics, links, mentions, control codes and emoji. These filters and model instructions do NOT establish complete topic/factual reliability. Real-model adversarial/topic/recipe/version qualification, effective DB privilege checks and native usage accounting are required before enabling knowledge.

The service defaults to knowledge disabled. No DB secret is read and no model is called in deterministic statistics mode. Do not enable it merely because the offline mock tests pass.

## Introduction

Both the addon and introduction default disabled. After final owner qualification/activation, introductionEnabled may be explicitly enabled. The first answered addressed Minecraft question claims an fsynced CREATE_NEW marker before requesting delivery to Minecraft and the existing Discord output. Reload/restart/uncertain delivery never automatically resends it. The bridge API does not provide combined delivery acknowledgements; the marker records an attempted, potentially partial delivery, not a guaranteed announcement. Operator review is needed after uncertain/partial outcomes. No introduction has been sent by development/tests.

## Verification and remaining deployment work

The addon compiles against the actual nested API from the public Fabric 26.2 / 3.2.1 JAR, as well as the Maven common API. Java checks cover cross-language HMAC, output policy, response-size cancellation and a durable single introduction claim. Nine Python runtime tests cover real deterministic synthetic statistics, private-topic refusal, ordinary chat, unknown/incomplete data, persistent/global limits, hashed-state privacy, local-only routing and actual authenticated HTTP/replay/stale/busy/size boundaries. The existing ten collector/admission tests remain in CI. No owner player data or configuration is committed.

Build with JDK 17+:
    python3 scripts/build-fegcraft-addon.py
Or compile against the exact installed mod:
    python3 scripts/build-fegcraft-addon.py --dependency /path/to/dcintegration-fabric-MC26.2-3.2.1.jar

Build output/dependency cache lives under integrations/fegcraft-addon/build (already ignored). No addon is installed by the builder.

The owner completed scripts/diagnostics/fegcraft-chat-preflight.py at cbc7cc8b5a9502de58085db8e3651f14caa980ea. It reads installed metadata, container network names, saved-statistics coverage and local model availability. It reports no player names, raw config, environment or token values. It does not modify Compose, start/restart containers, install addons, infer, send messages or write a database. Owner evidence matches the exact public JAR hash, version and API. All 50 saved-stat files are readable and named, 63 mod metadata IDs are readable, and qualified Qwen exists. Minecraft runs on mc-net, Ollama on vector-local-inference; no existing Vector addon or host javac. Production Compose and container identities stayed unchanged.

Still required before production activation: isolated real Minecraft callback/thread/relay test with captured output; service image/dependency pinning, token/state permissions and read-only mounts; exact private network delta; dedicated CPU-slot role and effective privilege verification if knowledge is enabled; real local model/factual/adversarial evaluation and local usage recording; channel presentation/logo decisions; guarded install, rollback and health checks. Existing app/NER/Ollama images/source must be preserved. A source merge does not imply operational integration.

Rollback plan for future install: deactivate/unregister addon, restore backed-up addon/config and the exact previous Compose profile, recreate only the newly affected services, retain introduction/event state to avoid repeats, and verify game/Discord relay health. Do not change production or send the introduction during this read-only phase.

## Isolated captured container qualification

scripts/deploy/evaluate-fegcraft-bridge.py prepares a private release directory from pinned Git blobs and synthetic fixtures. It downloads only a pinned official linux/amd64 Eclipse Temurin JDK image if absent, compiles against the exact installed nested integration API as UID 65534 with no network, and reuses the already qualified native Python image without loading its model. No host compiler/packages are installed. No production data/configuration/Discord or model credentials are mounted into test containers.

An internal throwaway network connects a temporary Python statistics service and Java addon fixture. No published ports, Docker socket or production network access. Read-only root/code/inputs, dropped capabilities, no-new-privileges, CPU/memory/PID limits and dedicated disposable writable state apply. The normal addon flow uses a small Bridge interface; production wraps the verified server-thread scheduler, player map and existing output calls. The fixture schedules and captures only those host interactions, while executing the actual addon parsing, signed HTTP, response handling and intro policy.

The captured run verifies ordinary/unidentified chat stays silent, callbacks do not block, the authenticated author is used, saved-stat values and mod IDs are returned, private topics are refused, and normal forwarding is preserved. A temporary service restart reuses SQLite and intro state to verify rate limits and no repeated announcement. All deliveries are recorded internally; real Minecraft callback registration/thread behavior and real Discord delivery remain explicitly untested. General knowledge is disabled; zero model/cloud calls and zero external messages.

Nine evaluator regressions cover restrictive-umask mount traversal, resource limits, refusal to remove foreign resources, unsafe Git export rejection, incomplete/interrupted qualification, bounded timeout/completed logs and inspection failure handling. An immediate-next-question regression delays worker completion after visible delivery and verifies that the next reply is not lost. The full captured addon/HTTP sequence passes locally; CI repeats it with Java 17 and 25. Actual owner Docker qualification remains pending. Cleanup removes only owned temporary containers/network and the synthetic key; compiler image cache and private evidence/artifact remain. Existing Compose hashes, production container identities/networks and the installed integration hash are compared before/after. All completion flags are mandatory. Interruptions, uncertain Docker inspection, cleanup or verification failures keep the gate closed. Step diagnostics retain at most 128 KiB including partial timeout output.

After this captured test, actual Minecraft/relay qualification and local knowledge/slot-role/usage qualification are still required before final production activation. Do not describe captured delivery as a real game or Discord test.
