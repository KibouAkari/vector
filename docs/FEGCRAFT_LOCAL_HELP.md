# Local FEGCraft help: candidate and operational limits

PR #61 prepares a broader adapter, not a production activation. Observed active backend is PR #59 (`70f3adc9e6516c4fb4531cf5289a6cd99c29c7b1`), release `vector-fegcraft-mod-help-20261017T163203Z-4d3601`; its model mode is off. Do not reuse a deploy script that assumes the original pilot code mount. The current installation manifest owns the newer profile.

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
