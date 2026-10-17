# Local FEGCraft help: candidate and operational limits

PR #63 refines PR #61's broader adapter after actual PR #62 diagnostics; it is not a production activation. Observed active backend is PR #59 (`70f3adc9e6516c4fb4531cf5289a6cd99c29c7b1`), release `vector-fegcraft-mod-help-20261017T163203Z-4d3601`; its model mode is off. Do not reuse a deploy script that assumes the original pilot code mount. The current installation manifest owns the newer profile.

The new adapter uses only `vector-qwen3:1.7b-q8` at the fixed private Ollama endpoint, with no redirects, proxies, cloud fallback, executable tools, server shell or filesystem exploration. Fresh statistics and catalog recipes precede model inference. Public installed-mod IDs are evidence of installation, not evidence of configuration or model competence for every mod. The small model can still be factually wrong; say when a detail is uncertain, and qualify representative questions before activation.

Own model turns are bounded to two, 180 seconds and 256 author/source scopes in RAM. Ordinary unaddressed chat is not read into context. Statistics, recipe and inventory answers clear old model context; users in Minecraft and Discord do not share a conversation merely because their channel is linked. No user transcript or private Vector project memory is persisted or supplied. Native token metrics retain unknowns as NULL and rejected completions still count. These local SQLite metrics do not yet appear in Vector's web billing dashboard and have zero external API fee.

Input and output guards independently prohibit commands, console output, seed, gamemode/cheating, administrative secrets and links. Model output cannot authorize any operation. Fixed schema, response length and completion checks apply; no automatic retry. The rate/replay/signature boundaries remain. Claims/party ownership, membership, actual rights and server limits are not readable through this interface and must not be invented.

## Qualification and next activation requirements

Run `scripts/deploy/evaluate-fegcraft-general-help.py` as owner with exact `VECTOR_FEGCRAFT_REV`, after fetching that merged revision. It holds the actual shared CPU advisory lock through a read-only coordinator, sends only synthetic questions from an isolated client, checks claims/parties/followups/redstone and forbidden-topic routes, then unloads its model and verifies unchanged production. It does not install code, activate model mode, restart Minecraft, send a message or qualify universal mod accuracy. A failed fixture must remain a failed gate; do not substitute transport stubs for actual-model evidence.

The eventual service-only update needs a qualified `psycopg` driver and a dedicated PostgreSQL role with CONNECT only, no table/creation/admin privileges, no app DB credential in the assistant, and verified use of shared lock `6194261933202610`. The current isolated model test deliberately does not qualify that role/driver. Do not enable `VECTOR_FEGCRAFT_KNOWLEDGE=2` manually beforehand. Preserve current token, SQLite state, narrow read-only data mounts and all other services; provide health-tested rollback. The old addon/identity/native welcome cutover still has separate persistence gates.

## Reviewed public hints

- Carry On author instructions: https://tschipp.ch/ — empty hands, sneak (default Shift), right click to pick up, right click to place; server configuration/protection can restrict this. Owner separately observed the small-villager interaction working.
- Open Parties and Claims author repository: https://github.com/thexaero/open-parties-and-claims — chunk claims, player parties, configurable protection and Xaero map integration. No inference about actual server limits, privileges, menu availability or hotkeys.
- Ollama API: https://docs.ollama.com/api/chat — structured response schema, no thinking, bounded generation and five-minute residency. Unload is explicit after the isolated benchmark.

No third-party mod code or documentation text is redistributed by these short factual hints. Existing model/source licenses still apply. The model is not granted more capability because it is described as uncensored.

## Observed failure and focused diagnostics

Owner's full real-model evaluation at `vector-fegcraft-general-20261017T172631Z-d8d45e` failed. Broad mode stays OFF. Run the same revision-pinned evaluator with `VECTOR_FEGCRAFT_GENERAL_DIAGNOSTIC=1` to observe four failed independent synthetic cases without changing the runtime or prompt. The wrapper records bounded synthetic raw model output, exact safe rejection code, native completion reason, actual durations and usage; no real messages or private context are accepted. Known token subsets and unknown-call count supplement NULL exact totals after a timeout. Diagnostic reports always remain activation-ineligible, even if all focused cases happen to pass. A successful diagnostic command means collection/cleanup succeeded, not that the quality gate passed. Full qualification remains required after a targeted fix.

## Compact candidate after actual diagnostics (PR #63)

The actual focused diagnostic (`vector-fegcraft-general-diagnostic-20261017T174253Z-a7cc68`) observed a cold timeout, inaccurate comparator text, repeated invented party features until truncation, and wrong off-topic routing. All broad mode activation stays blocked. Thinking was off; increasing the timeout alone would not fix wrong answers.

Use Qwen3 author's non-thinking settings: temperature 0.7, top-p 0.8, top-k 20, min-p 0. Greedy decoding was a configuration mistake; the author warns of repetition/degradation. Source: https://huggingface.co/Qwen/Qwen3-1.7B . The candidate first classifies game/other with a small schema (24-token ceiling), then generates an answer capped at 200 characters/96 tokens. An explicit application-writing request needs neither stage; a novel other-topic request needs classification only. Both native stages count separately, including rejected completions and unknown usage after a timeout. The two requests share one CPU lease and checked 24s budget; socket timeouts do not constitute a guaranteed end-to-end hard wall deadline. Validate actual installed addon deadlines before deployment.

All public installed IDs are searched locally. Only up to three relevant IDs and applicable short public hints enter each prompt; omitted subjects may use that author's accepted two own turns. This is not a manual for all 63 mods or a claim of universal factual accuracy. Generic Minecraft/mod answers must still pass real-model evaluation. Grammar length/character constraints complement independent validation; unsupported runtime grammar features must not weaken output checks. No emoji stripping or turning rejected content into a player reply.

Public factual hints: https://www.minecraft.net/en-us/article/block-week-piston (normal piston pushes up to 12 blocks; sticky variant pulls), https://www.minecraft.net/en-us/article/taking-inventory--redstone-comparator (compare/subtract side signals and measure container fullness). Author OPaC hints above do not support invented quests/events or live configuration claims.

Run full mode with `VECTOR_FEGCRAFT_GENERAL_DIAGNOSTIC=0`. It now includes comparator/party factual negatives, generic cow breeding and backpack purpose, novel off-topic classification, scoped followups and existing privacy routes. Require cold <=25s, all warm cases <=12s and warm median <=8s, plus every semantic/security fixture. These are qualification targets, not achieved performance claims. Actual owner full-model results remain pending. No changes to installed 03:00 incremental backup or game/addon are part of this candidate.
