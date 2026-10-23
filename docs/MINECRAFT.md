# Optional Minecraft integration

## Separate CPU model preparation

`scripts/deploy/prepare-minecraft-model-candidate.py` can prepare the publisher's
`LiquidAI/lfm2.5-1.2b-instruct:latest` candidate only with explicit `--download`.
It uses the existing inference container and downloads about 731 MB. Its GGUF
weight digest is checked against the [publisher's file](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/blob/main/LFM2.5-1.2B-Instruct-Q4_K_M.gguf).
The model is separately licensed under the [LFM Open License](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct/blob/main/LICENSE).

The preparer requires a confirmed operator baseline and the existing release
lock before any download. It does not generate answers, change the assistant's
model, install a runtime update, alter resources or restart any service. Existing
tags are retained; a previously registered candidate with the wrong weights is
rejected. Cache additions are intentional and are not described as an unchanged
model registry. A timed-out download may continue inside the model runtime and
is reported as uncertain; the preparer does not delete existing models or blobs.

Preparation records the actual manifest and template hashes. It does not prove
that this runtime can execute the architecture, preserve conversational context,
follow German instructions or use tools correctly. Qualification must use the
model's documented sampling settings and the same scoped inputs, output checks,
CPU admission and deadlines before a separate guarded activation. This model is
a candidate for conversation and retrieval-backed tasks, not a replacement for
fresh statistics, installed recipes or verified server configuration.

The bridge consists of a Java DiscordIntegration addon and a separate Python assistant. It is not part of a web app restart. Operators supply their own world, identities, configuration, tokens and model runtime. No real player data or server inventory is distributed here.

## Components

- `integrations/minecraft-addon`: case-insensitive addressed greetings, Minecraft/Discord input hooks and authenticated private delivery.
- `services/minecraft-assistant`: policy filters, replay protection, bounded per-user context, rate limits, statistics, recipe/catalog adapters and local knowledge composition.
- `scripts/build-minecraft-addon.py`: compile and test against the pinned integration API; it installs nothing.
- `scripts/build-minecraft-identity.py`: generate brand-only chat assets. A Minecraft head needs a compatible client resource pack; a Discord avatar needs a reachable PNG and webhook configuration.

Ordinary unaddressed chat is ignored. The service has no command execution API or cloud fallback. Commands and their output, seeds, credentials, administrative state, gamemode and cheating questions remain excluded. Discord display names are not trusted Minecraft identity links. First-person queries require an authenticated Minecraft UUID or a verified operator-managed link.

## Data and knowledge

Mount only the required input files read-only. Persist rate-limit/replay state separately and protect token/DSN files with strict ownership and mode. A restricted database role coordinates the shared local CPU slot; it must not read application data. The deployment must qualify actual database privileges, including inherited PUBLIC grants.

Statistics are read afresh for each query. Rankings require complete saved data and retain ties. Saved files can lag ongoing play. Advancements and item-use counters do not prove who killed whom or how a kill occurred. Humorous portraits must stay grounded in the available game counters.

The generic knowledge pack is a set of reviewed, paraphrased source-backed facts, not proof that every mod, version or server setting is understood. Operators provide their own installed-mod list and recipe catalog. Base recipes are not guaranteed to match a server's effective datapack/mod recipes. Keep source attribution and verify version-specific recipes/settings before claiming certainty.

## Web statistics configuration

These settings belong to the web app's private runtime configuration, never to a chat request:

| Variable | Meaning |
| --- | --- |
| `VECTOR_MINECRAFT_DATA_PATH` | Absolute read-only data root reachable through the existing authorized Host Agent |
| `VECTOR_MINECRAFT_STATS_PATH` | Relative statistics path beneath that root; default `world/players/stats`, adjust to the actual layout |
| `VECTOR_MINECRAFT_SERVER_ALIASES` | Optional comma-separated server labels for intent normalization |

The web adapter reads `usercache.json` and the configured statistics folder. Paths from a user's prompt cannot override this configuration. An unconfigured or incomplete source fails clearly; it is never silently replaced with an invented answer.

## Rollout boundaries

The generic source intentionally uses Minecraft-specific names, role names and example paths. It is not a migration for an existing installation. Do not replace live mounts, secrets or database roles merely because source names changed. Qualify a separate game rollout against the installed API, preserve world/player/mod state and tested backups, and keep rollback evidence. A one-time welcome needs durable replay protection and readiness confirmation. Never replay it during a web release.

## Narrow ranking runtime update

`scripts/deploy/update-minecraft-ranking-runtime.py` accepts private operator pins for a dedicated single-service Compose profile and its healthy current assistant. It stages a copy of the installed code, replaces only `runtime.py`, retains a uniquely identified configured best-player joke, and runs synthetic ranking tests in the same image without networking or secrets. Unknown code/profile shapes fail closed.

The default only qualifies. Explicit `--activate` changes the read-only code bind and recreates only that assistant. Existing state, image, environment, input mounts and the game addon remain unchanged. Rollback verifies the owned Compose/code/container generation before restoring it. This updater does not migrate generic names into an existing installation or restart the Minecraft server. Keep its private configuration, observed hashes and release record outside Git.


The runtime updater requires `expected_project_name` in its private operator JSON. Obtain it from the running container's Compose project label and render the baseline using the same explicit project name. Deriving a project from the release directory can select a different Compose project; a failed identity guard must not be bypassed.

## Experimental local dialogue qualification

Mode `6` is an opt-in conversational candidate, not an automatic upgrade to an installed assistant. It generates short local answers and may request one allowlisted public lookup followed by a final answer. A single-key answer-or-tool envelope limits output overhead; the shared policy, authenticated identity, restricted CPU role and existing deadlines still apply. Own recent context is scoped by authenticated source and author. Available tools do not expose private inventories, commands, secrets or arbitrary files.

`scripts/deploy/evaluate-minecraft-dialogue.py` preserves the exact confirmed installation and uses synthetic temporary state. Native metadata excludes prompts and generated text; synthetic test answers are reported separately. Evaluation stops after the first timeout, and incomplete coverage cannot pass. Unknown token usage is reported as unknown. Smaller prompts, schema validation and successful mocked tests do not establish semantic correctness, good latency or eligibility for a production rollout. Review native evidence before any separate guarded activation.

For a repeated native timeout, `--profile-only` measures one synthetic request using streaming with the same generation parameters and existing deadlines. It reports first-chunk timing, content/thinking sizes and final native counters when available; partial text is not exposed as an answer. `diagnostic_completed` means the measurement and baseline checks finished, while `passed` and `eligible_for_activation` remain false. This is not full conversational qualification or a rollout. Keep private operating evidence and configuration outside the repository.

When observed runner-loading waits need to be distinguished from answer latency, `--preload --profile-only` sends one empty preload under the shared CPU slot with a separate 45-second bound, then releases that admission before the unchanged question budget begins. A failed preload skips the question. The preload contains no user prompt, does not permanently pin weights and never makes the service eligible for activation. [Ollama documents empty API preloads](https://docs.ollama.com/faq#how-can-i-preload-a-model-into-ollama-to-get-faster-response-times); a successful preload alone does not prove the subsequent request will meet its deadline.

The experimental dialogue prefix uses concise internal English instructions but requests German answers. It sends verified self identity without automatically attaching own counters or an operator joke to every question; those remain available through a fresh statistics lookup. This reduces unrelated initial context and does not change backend authorization, privacy or forbidden-content checks. Native latency and semantic qualification are still required before any activation.

