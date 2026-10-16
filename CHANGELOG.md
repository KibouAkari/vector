# Changelog

## 2026-10-16 Captured FEGCraft addon qualification (#40)

Owner preflight confirms the exact installed 26.2/3.2.1 integration hash/API, complete 50-file saved-stat coverage, 63 readable mod metadata IDs and qualified local Qwen; Minecraft and inference use separate networks, and the host has no compiler. Production configuration/container identities stayed unchanged.

Factor only the host scheduling/identity/delivery boundary into a Bridge interface; retain actual addon greeting, signed transport, output and introduction logic. Add a synthetic captured addon-to-real-HTTP flow with temporary service restart, persistent rate limits and no repeated captured introduction. Local first/restart phases, existing 19 Python tests, Java checks and five new evaluator regressions pass. Extend CI to Java 17 and 25. Reproduce and fix the completion handoff race that silently dropped an immediate next question: admit one active HTTP request and one bounded completion handoff, reopening admission before publishing. The delayed-delivery regression fails before the fix and passes after it.

Prepare owner-run isolated container qualification with an exact official JDK image, installed nested API and existing qualified native Python image. Use an internal throwaway network, no published ports/production networks/credentials, unprivileged read-only containers, bounded resources, synthetic state and ownership-checked cleanup. No host package installation, production restart, model/cloud call or real message is performed. Owner Docker execution, real game/Discord delivery and knowledge/role/usage qualification remain pending; captured delivery is not proof of real-channel integration. Update project handoff and next command accordingly. Require every qualification-completion flag before reporting success, including interrupted runs. Retain bounded partial/completed step logs on timeouts/failures, distinguish confirmed Docker absence from daemon/permission failures, and keep uncertain cleanup closed. Nine evaluator regressions pass locally. Rename a public dependency-checksum constant to avoid a secret-scanner false positive without exclusions or weakening hash verification.

## 2026-10-16 Minecraft chat bridge components (#39)

Implement the owner-requested Minecraft-only input addon using the existing Discord Integration 3.2.1 bridge and its configured output channel; no separate Discord listener. Verify the official 26.2 source and actual public release hash/nested API packaging, compile against that exact API, and preserve normal chat. Add bounded asynchronous signed private requests with an explicit whole-response deadline and cancellation of late body subscriptions, server-thread identity/delivery, persistent hashed rate/replay state, deterministic saved statistics and disabled optional local knowledge using the shared CPU slot. Keep addon/introduction/knowledge inactive until owner qualification; persist an at-most-once introduction attempt rather than claiming acknowledged delivery.

Nine new Python runtime/actual HTTP tests pass locally, alongside Java HMAC, output, response-limit and durable introduction-claim checks. Add them to CI with the existing ten foundation tests. Prepare a read-only owner preflight for installed JAR/network/mount/stat coverage/model availability. No production configuration/database changed, model inference performed or message sent. Real-game/relay, private service packaging, restricted DB role, model quality/usage, custom Minecraft head, isolated owner staging and guarded installation remain pending. Update owner preferences and handoff with the Minecraft-only input scope and Discord-origin hook limitation.

## 2026-10-16 Runtime deployment confirmation (#36)

Record the owner's read-only confirmation that the qualified runtime release is already deployed. Running image, release status/commit/image, active Compose bytes and source tree hash match. App is running with no OOM; diagnostic left Compose unchanged. Update the project handoff and final PR merge ledger. No restart, model request, new cutover or fresh HTTP health check is performed by this documentation update.

## 2026-10-16 Runtime release and continuation review (#36, #37)

Prepare the guarded release of owner-qualified runtime revision 8611082 and identical merged tree 60adca9, image c33a1b8. Owner staging and enabled native privacy API checks passed without executing synthetic jobs or calling a cloud provider. The latest owner release attempt stopped before deployment because the old composer profile no longer matches. The initial read-only comparison narrowed the drift to the app image. A subsequent owner diagnostic confirmed that runtime release vector-runtime-privacy-release-20261016T165856Z-c0c023 was already deployed, with matching qualified commit/image, active Compose bytes and current source tree hash. The app is running without OOM. The repeated invocation correctly stopped at the old-profile guard; no further cutover is needed. Preserve the guard and rollback rather than rerunning a cutover blindly.

Review the four open PRs, record composer deployment evidence in #33 and the exact foundation scope/CI coverage in #34. Close empty #37: its description claimed changes absent from its zero-file initial-plan commit; carry those review tasks forward as unimplemented. Add a durable project handoff and owner preferences, required from AGENTS.md, so continuations retain instructions, pinned evidence, pending defects and FEGCraft integration boundaries. Repository merges do not activate the bot or establish current server deployment.

## 2026-10-16 Runtime follow-up fixes

Limit Minecraft player continuation to standalone short follow-ups, including reversible placeholders. Prevent the local text-only executor from generating unsupported live-state answers before inference. Clarify that an additional privacy approval blocks new tool evidence, not the already submitted prompt. Targeted local regressions and owner staging/native API qualification passed; production deployment of commit 60adca9 and image c33a1b8 is confirmed by the matching completed release record, current source and Compose. Fresh real-provider/UI behavior remains to be verified. This does not yet add local server data access or interactive mid-job consent.

2026-10-16 — Privacy composer follow-up (#32): reject contextual contact labels misclassified as people, preserve ambiguous names and credential types, and retain the real API preview assertion. All 36 targeted local Node tests pass. Native server retest remains pending.

This changelog documents repository changes by date, with commit and pull
request identifiers when available. Entries are listed newest first.
Production deployments are tracked separately.

## 2026-10-16 FEGCraft assistant foundation (#34)

Add a bounded read-only saved-statistics collector, deterministic rankings with ties and coverage checks, greeting-only admission, canonical-event deduplication, and three-per-user/twelve-global requests per minute. Ten synthetic Python tests pass locally and now run in Application CI. Prepare an emoji-free introduction. Chat/model integration, topic/output restrictions, durable delivery, owner-data qualification and production deployment remain pending. These modules do not yet read production files, invoke a model or send messages.

## 2026-10-16

### Compact privacy review beside the composer (#32)

- Show an immediate local checking indicator with elapsed seconds and a small accessible review card above the chat/project input. Remove the modal backdrop and eyebrow, simplify actions and preview labels, and keep fully local requests quiet. Test explicit consent, cancellation, stale scopes, duplicate sends and progress cleanup.
- Display only the current message in the default preview; separate context findings in a collapsed group while still protecting all included history, attachments and project retrieval. Batch uncached text segments in one native scan and reuse exact per-account successful results for at most five minutes with bounded in-memory storage. Changed context and other accounts rescan; cached work adds no fabricated encoder/API usage.
- Detect bare credential-shaped password values, explicit lowercase usernames and separate first-name references. Reject pronoun/code-heading false positives, trim Markdown edges on new person findings and respect person/username word boundaries. Preserve encrypted consent/vault handling and block failures before queue writes. Use synthetic regressions rather than the owner's private prompt values.
- Local verification passes 38 Node tests and 8 deployment evaluator tests. Expanded owner qualification covers current-only previews, natural reset credentials, masked queued context, cache accounting and fresh-input outage blocking. The initial branch commit passes production build and CI. Construct dummy PEM markers only at test runtime to avoid a source-scanner false positive without excluding any files or rules; keep redacted scan diagnostics visible. Final CI, owner API/UI qualification and deployment remain pending; native service code/model weights are unchanged.

### Privacy release preparation after enabled API qualification (#31)

- Owner source/image release ba30c82 completed with healthy app and backups; privacy activation stopped before changing production Compose. Owner read-only diagnostics prove all four app mount definitions match exactly when order is ignored. Normalize only app mount ordering while preserving every mount field and rejecting duplicate targets. Resume an incomplete preparation only after exact qualified Git-byte, root ownership, mode, file type, link count and directory-content checks; preserve the private token without overwrite. All 16 offline release/profile/rollback/resume tests pass. Native activation retry remains pending.
- Add the owner-run guarded app release and separate private NER activation/feature rollback using the inspected archived helpers. Pin the qualified app/model images and tested/merged trees, preserve existing local workers and all other container identities, retain encrypted token access through read-only bind mounts, validate the full canonical Compose delta, and inspect actual runtime isolation/authenticated sleeping health without inference. Guard rollback against changed source, Compose, images or service ownership. Eleven offline release/profile/rollback regressions pass; generated YAML additionally parses and preserves all unrelated fields locally. Owner production execution remains pending.
- Owner pipeline at a20b9a6 passed the rebuilt staging image, 75 tests and the full privacy-enabled real app/native service/disposable PostgreSQL qualification, including the previously failing project metadata assertion. All 13 normal/outage checks passed. Six synthetic jobs remained queued; none executed, no cloud model was called, temporary resources were removed and production stayed unchanged. Preserve bounded synthetic evaluation evidence. Feature PR #30 merged as ba30c82 after all observed gates and CI passed.
- Prepare a read-only production release inventory using the existing archived helper factory. Report only selected release/profile hashes and flags, plus active helper program definitions without resolved Compose/environment values. No helper main/rollback is executed, no restart or model request occurs, and production activation remains pending. The archived release implementation exists only on the owner's server, so its exact active behavior must be inspected before adapting source/image release and rollback around the already enabled local-worker profile.

### Project job metadata privacy boundary (#30)

- Owner API qualification at ff11044 reached the project-job assertion after earlier consent/local/history/upload/image checks, then correctly stopped because the durable privacy finding metadata still contained the original email. Reproduce the failure with the actual project route in a focused regression. Store placeholders for noncredential finding displays, full bullets for credentials (no prefixes/suffixes), and apply the confirmed privacy plan to retrieved filenames. Keep the pre-send local consent display and the full queued-payload expectations intact.
- Add field-path-only diagnostics to the synthetic API harness so future failures identify the metadata boundary without echoing private values. A new build/staging run is required for the runtime fix. Allow the API evaluator to receive a validated newly staged revision/image, retain the source-equality gate and bind native qualification to its independently observed b916048 report. The old app image is rejected when runtime source differs; native weights and all 32-case/API expectations remain unchanged. New staging and actual API retry remain pending; production remains inactive.

### Application-user API test dependency access (#30)

- Owner privacy-enabled API setup at ade4ff07 stopped before connecting to the app because the test client used UID 65534 while the image's application packages are owned by UID/GID 1001. The app itself started normally. Run this dependency-loading client as the same unprivileged application identity; retain the native service's separate UID 65534, read-only filesystems and existing resource/network limits. Do not modify image permissions or run the client as root.
- Preflight package.json, the actual pg Client export and the mounted API harness as UID/GID 1001 before the test begins. Record only bounded stage/error codes on failure and add client-identity/preflight regressions. Existing images, 32-case native qualification, source equality checks and API expectations remain unchanged. Real privacy-enabled API retry remains pending; no production activation occurred.

### Privacy-enabled application API qualification (#30)

- Owner retry at b916048 passed the private native HTTP service's 32 cases, consent/tool/runtime tests, idle unload/fresh wake, auth/limits and outage blocking. Owner app staging also passed its build, 74 tests and authenticated chat/file/project/server checks with privacy still disabled. Preserve bounded evidence separately; production source/configuration and running services stayed unchanged.
- Add a final owner-run qualification of the actual privacy-enabled built app, pinned native service and a fresh temporary PostgreSQL database. Exercise real login, review-before-chat/job-writes, account/request-bound confirmation, masked jobs, encrypted vault, response restoration with a synthetic assistant fixture, explicit unchanged send, quiet local requests, history, uploads, image limitations, project retrieval/access/local-only routing, encoder ledger metadata and outage blocking. Queue only synthetic jobs; start no worker or cloud provider. Reuse the observed app image only if Git proves all runtime/build sources still match the staged revision. No rebuild, production activation or production DB data writes are included. Docker/real-API execution of this new harness remains pending.

### Unprivileged privacy evaluation mount access (#30)

- Owner service qualification at 28bb9de stopped before running integration.mjs: the root runner's 0077 umask changed the requested 0755 input directory to 0700, preventing UID 65534 from traversing its read-only bind mount. Reproduce the restrictive-umask result, explicitly set only the synthetic/code mount root to 0755 and leave the release parent private. Add restrictive-umask and safe preflight-error regressions; actual unprivileged container access is checked by the owner-run preflight.
- Before starting the model service, verify all required scripts, fixtures and the synthetic token through the exact read-only client mounts as UID 65534. Report bounded error code/path metadata, retain container resource/auth/network limits and reuse the same qualified image and 32-case fixtures. Docker retry and app staging remain pending; the failed setup is not a model-quality failure or production activation.

### Private NER service and application adapter (#30)

- Owner server qualification at f7b5bb4 passed all 32 unchanged synthetic cases, including the previously missed surname; preserve compact evidence in docs/evaluations/privacy-ner-context-server-20261016.json. Short warm scans took 0.12–0.21 seconds, long fixtures up to 4.08 seconds, model load 9.596 seconds and peak RSS 2,816,296 KiB. No cloud requests, ledger writes or production activation occurred.
- Replace the application's unqualified generative privacy detector with the bounded, exact-span NER HTTP adapter. Keep existing consent, vault, authorization, provider/tool guards and quiet fully-local path. Record encoder text subwords as explicitly separate local metadata with zero API fees and no fabricated generative tokens. Preserve the earlier Qwen/Hermes comparison as an independent historical benchmark.
- Add an authenticated private service whose parent stays lightweight and whose model child loads on demand, exits after idle, and restarts cold. Reject excess input/concurrency and terminate a failed/timed-out child; no cloud fallback. Add client, HTTP/auth, failure, timeout and lifecycle tests plus an owner-run isolated 32-case service/runtime evaluation using the exact observed image, no downloads, no published ports and checked cleanup. Actual pinned-model local HTTP tests pass all 32 cases plus consent/tool/idle/wake checks; preserve bounded local evidence in docs/evaluations/privacy-ner-service-local-20261016.json. Real Docker service qualification and isolated application staging remain pending; no production installation or feature activation is included.

### Nested name spans and focused context verification (#30)

- Owner qualification at 2242f063 passed 27/28 cases; the long end-of-text case preserved only the first name and left its surname unprotected. Keep the original expected full name and the production gate. Reproduce the issue with the actual model locally: flat decoding suppresses an overlapping complete name and long surrounding text can weaken that name even with nested decoding. Retain nested exact-source spans at the unchanged 0.35 threshold and add at most 32 non-recursive original-sentence/neighborhood rechecks around detected people in multi-chunk inputs. Preserve all primary findings and word/subword bounds; count all recheck text in the explicitly labeled local tokenizer metrics. Reuse the model’s existing tokenizer rather than constructing it twice.
- All 32 actual-model local cases pass (the unchanged 28 plus four independent name-position/software controls); evidence is stored in docs/evaluations/privacy-ner-context-local-20261016.json. Add focused-window, nested-name retention, recheck-budget and token-accounting regressions. This is local evidence only; owner rerun, service/app integration and production activation remain pending.

### Bounded local privacy context qualification (#30)

- Owner retry at 7cedc0a confirmed the 0600-to-0444 public-weight fix and passed all 16 offline server cases. Warm short-case times were about 0.12–0.16 seconds, load 5.813 seconds and peak RSS 2,815,740 KiB; production stayed unchanged with no cloud calls or ledger writes. Preserve the observed pilot image for reuse.
- Add a separately qualified Python PERSON backend with complete splitter coverage, at most 64 words/192 raw-text subwords per chunk, 12-word overlap and strict exact-source spans. Reject omitted text, oversized words, oversized contexts and excessive chunk counts rather than truncating. Extend the unchanged 16 cases with eight synthetic credential checks and four long/Unicode/boundary controls, using the existing offline image without downloads. Record raw-text tokenizer counts with overlap explicitly; these are not provider billing totals. Extended actual-model qualification and app integration remain pending.
- Prevent a credential from appearing in another overlapping finding’s preview, including URL passwords recognized inside an email-shaped value. Recognize spaced API/access-token labels and quoted password phrases introduced by German/English verbs. Promote enclosing mappings and their saved aliases to the credential classification without altering ciphertext or reversibility; add regressions.

### Offline privacy pilot access recovery (#30)

- Owner server setup at 8126c50 completed, but unprivileged inference could not open converted model.safetensors. Locally reproduce safetensors 0.8.0 creating a 0600 file. Explicitly grant read-only access to this public weight asset, retain UID 65534, read-only inference and network isolation, and preflight weight readability before loading libraries. Add guarded reuse of the existing pilot image without downloads: verify the original model pin and converted-file checksum before changing permissions in a new derived image, preserve the original image, and rerun all 16 unchanged fixtures. Missing files, changed checksums and symlinks remain blocked. The subsequent owner retry passed all 16 cases with no production activation; the failed initial inference is not treated as a model-quality result.

## 2026-10-15

### Local privacy review and explicit external-send consent (#30)

- Owner model comparison at 75b5afa failed both candidates (6/9 each); Hermes was slower and missed different names. Keep staging and activation blocked. Prepare a separate CPU-only GLiNER PII PERSON pilot with digest/revision-pinned weights, restricted weights-only conversion to safetensors, package/version manifest, exact-source fixtures and existing placeholder roundtrip validation. Locally observed 16/16 short synthetic cases passing (the unchanged nine plus seven additional controls), roughly 0.2 seconds per warm case and about 2.7 GiB peak RSS. This evidence comes from the Codex workspace, not the owner server; long contexts and other PII model categories remain unqualified. The guarded server pilot downloads public dependencies into its own container, then tests with no network, 2 CPUs/4 GiB, read-only mounts and no persistent service or production changes. Add offline guard/fixture regressions and preserve failed candidate findings rather than claiming complete detection.

- Owner qualification at 1aa928e passed six of nine unchanged cases. Qwen omitted Anna and Mia, produced an inexact accented name, and returned no model findings for the injection fixture (deterministic rules covered that case). Keep privacy disabled and staging blocked. Add a comparison mode for the already installed, digest-pinned Qwen and Hermes using the same detector, prompt, nine fixtures and strict expectations; record the actual candidate in native usage and unload each model. No model switch or quality claim is made before observed comparison evidence.

- Owner qualification at 2302de8 passed three of six real local detector cases and failed German/full-name, standalone-first-name and accented-name cases. Production remained unchanged, staging did not run and no cloud call occurred. Clarify multilingual exact-span extraction with first-name/Unicode instructions, retain every original expected value and add three held-out cases. Report bounded synthetic-only detector diagnostics and missing expectations. This revised prompt remains unqualified until rerun on the actual server.

- Harden reviewed boundaries before qualification: promote all aliases of credential-shaped values and persist promotions without overwriting encrypted originals; preserve provider protocol identifiers; inspect decoded JSON and numeric tool leaves; require current approval for previously vaulted identities in unchanged-send jobs; respect the configured history window and avoid saving stopped local replies. Add focused regressions and an isolated PostgreSQL upsert/encryption check. Existing runtime-fixture bindings and once-only failure handling were corrected in preceding commits. Real detector quality and deployment remain pending server evidence.

- Add an opt-in `VECTOR_PRIVACY_REVIEW=1` path. A fixed private Qwen endpoint identifies exact sensitive spans locally, combined with deterministic credential/email rules. Preserve original wording around reversible, conversation-stable opaque placeholders and keep mappings in the existing encrypted vault. Include local detector tokens in the usage ledger at zero API rates, even when returned output is rejected.
- Review the prompt, authorized history and locally retrieved text context before message writes/enqueue. Require encrypted, expiring, account/content/context-bound confirmation before either masking or explicitly sending detected values unchanged. Display a compact accessible dialog with findings, masked credentials, preview, cancellation and both choices. Retain drafts on cancellation and discard stale chat-switch UI updates.
- Restore private values only for authorized local display and allowlisted local tools/renderers. Guard provider input centrally and examine subsequent tool evidence locally; new unapproved sensitive tool data blocks unchanged-send jobs. Never restore originals into web/sandbox tool arguments. Reject forged, expired or cross-account review tokens, incomplete detector responses and uninspectable-image masking; images require explicit unchanged-send permission.
- Add a separate native local text-chat path with no cloud routing, search, tools or failover, including local-only projects. It skips privacy warnings and uses a bounded 6 KB context. Local workers under a cloud parent remain external jobs and require the same review. Keep existing behavior while the feature flag is off.
- Add runtime, route/permission, reversal, fail-closed and local-only regressions, plus a synthetic-fixture server qualification script using the actual detector with synthetic names and credentials. The evaluator checks model pins, captures native usage, releases the shared inference lock and unloads weights without changing production or writing database data. Real model quality, browser interaction and production activation remain pending their observed checks; detecting every possible identity or retaining identical task quality cannot be guaranteed.


### Persistent local-worker deployment (#29)

- Owner activation ab2220c succeeded at 15:42 Europe/Zurich, confirming the persistent feature flag/private network, runtime/model pins, idle weights and healthy application. Harden saved rollback recovery for a positively confirmed missing app container; keep inspection errors and different images blocked. Require the inference runtime to use only its private network, and explicitly compare canonical mount lists. These maintenance-script improvements do not require a new app image or another activation.
- Owner source/image release 37130b5 succeeded with healthy app and unchanged supporting containers. Feature activation stopped before cutover because Compose included an extra `ipam` field on the external inference network; its private diagnostic confirmed this was the only differing path and the production Compose file was unchanged. Permit only an empty IPAM object at that exact external network in both preflight and post-cutover comparisons, with regressions retaining rejection of every nonempty IPAM configuration and unrelated change. Retrying activation remains pending owner evidence.
- The owner's final b7bf796 actual-worker evaluation passed all eight unchanged synthetic fixtures, accounting for 1,157 input and 117 output tokens with zero local API cost. Exact-source isolated application staging passed, with production unchanged. PR #28 is merged as 37130b5 and its pinned image was subsequently released and activated.
- Pin the tested application image and reuse the established backup, source-tree equivalence, idle-job, health and automatic rollback release flow. Guard the observed original Compose hash before release.
- Prepare persistent activation of the app's local-worker flag and attachment to the existing private inference network. Preserve raw YAML/environment substitutions, compare the entire resolved candidate against the strictly permitted change, and keep other container identities fixed. Verify runtime version/model digests and unloaded weights from the app without inference, cloud calls or database writes.
- Save a separate guarded feature rollback; execute it before an optional source/image rollback. Test configuration preservation, ambiguous layout rejection, the canonical permitted delta and refusal to overwrite later deployment changes.

### Bounded local workers and evaluation (#28)

- The owner's d283467 comparison completed with unchanged production, unloaded weights and all 24 native usage records. Qwen3 1.7B and Hermes each passed eight of eight synthetic cases; Qwen 0.6B passed six. Select the pinned 1.7B model for the proposed extraction role, retaining Hermes for structured summaries. These short fixtures do not certify general task accuracy.
- Run the same eight fixtures through the actual scoped worker/accounting core for final qualification, verify the observed 1.7B Ollama manifest digest, and retain the comparison's original expected values without duplicated fixtures.
- Add a read-only deployment shape probe for the subsequent persistent network/feature release. Report only allowlisted image/network/layout/flag metadata and the Compose hash; never print resolved credentials or full YAML. No production activation or configuration mutation.


- The 370150d owner staging passed and its evaluator confirmed unchanged production, but model quality still blocked activation: Qwen passed four of five extractions and invented a zero for an unmeasured value; Hermes invented service names/array structures. Keep both failed cases and their original expected facts in the evaluation.
- Apply the closed output-field schema to Hermes summaries as well as extraction; prose summaries use an explicit string field. Continue treating all results as unverified interpretation rather than equating schema validity with truth.
- Add an isolated eight-fixture comparison across existing Qwen 0.6B, official checksum/revision-pinned Qwen3 1.7B Q8_0 and Hermes. Import the additional 1.83 GB artifact without changing existing models, preserve token telemetry, production snapshots and cleanup, and never auto-select or activate a candidate. Reuse installed runtime/app images without an application rebuild.
- Add an offline comparison-harness regression proving the observed wrong-zero/array responses remain failures, all native token counts are retained and only a fully passing candidate is listed. Actual new-model quality and latency remain pending server evidence.


- The owner's first application staging passed, while the subsequent real-model evaluation correctly blocked activation: Qwen returned wrong arrays/field names and Hermes passed its fixture. Retain these failures rather than calling the initial worker evaluation successful.
- Require explicit nullable extraction field names/types, send a native JSON schema and validate every returned key/type locally before accepting interpretation. Shorten role prompts and expand real-model checks to zero, missing values and different English/German counts. Schemas constrain structure, not factual accuracy.
- Canonicalize Docker mount/alias ordering in evaluator fingerprints, save private before/after snapshots, and report exactly which fields changed. Preserve detection of actual image, container, restart, mount-permission and network changes. The earlier unsaved difference cannot be retrospectively attributed to ordering alone.


- Record the owner's successful isolated Hermes/Qwen CPU pilot and accounting release. Keep short-fixture timing distinct from general model quality or speed guarantees.
- Add feature-gated server-scoped extraction/summarization workers with fixed models, explicit current-job evidence, no tools or independent memory/retrieval, two attempts per job and global nonblocking PostgreSQL admission.
- Preserve the two-call worker budget across artifact provider failover, and explicitly set staged evaluator directory permissions so restrictive umasks do not block the evaluation container.
- Bound UTF-8 input, context, output, request duration and response size; reject incomplete/non-JSON extraction and unsolicited tool calls. Never retry or automatically switch a worker to a paid provider.
- Account for reported native Ollama tokens, including cache counts when present, through the existing per-response usage scope before result validation. Keep outputs visibly unverified and missing usage incomplete.
- Add offline authorization, isolation, budgeting, scheduler cleanup, HTTP-bound and ledger tests, plus an isolated real-model evaluator and application staging wrapper pinned to the current live image. No production activation, schema changes or dependencies.


### CPU inference pilot and tested accounting release preparation (#27)

- Prepare an isolated Ollama 0.40.4 install pinned to its Linux/amd64 digest, plus checksum-verified publisher Hermes 3 8B Q4_K_M and Qwen3 0.6B Q8_0 model imports.
- Bound CPU, RAM, concurrency, context, output and idle weight retention; publish no ports or host execution capabilities. Add synthetic cold/warm extraction measurements, local token telemetry, explicit unloading and a pilot-only rollback.
- Document measured CPU constraints, model licenses and the remaining integration/evaluation gates for user-scoped local worker roles. No installed-model speed, task reliability or Vector activation is claimed.
- Prepare the accounting release wrapper pinned to the user-observed passing 5e3f304 staging image and identical merged a7af796 source tree. No production deployment is performed by CI.
- Four offline pilot tests cover artifact integrity, isolation limits, extraction failure and proxy isolation. CI also parses both deployment scripts; no paid requests or model downloads in CI.


### Runtime and accounting: local rankings and per-response usage (#26)

- Persist provider-reported usage per response for background jobs before subsequent renderer/workflow failures; retain usage from planning, review, repair and prior provider attempts. Deduplicate stored events by provider configuration, account and response ID instead of adding a second job aggregate charge.
- Honor configured OpenAI pricing, preserve USD estimates, FX and rate snapshots in an additive usage metadata column, account for request/search fees per response, and visibly flag missing usage or rates. Do not equate local estimates with provider invoices or rewrite historical amounts without evidence.
- Preserve normalized reasoning and cache-write details, include Anthropic cache reads/writes in total input, retain the original execution's usage when repairing a workflow, and add one empty-response recovery after a reasoning-only tool-limit finalization.
- Distinguish provider responses from legacy aggregate entries on the dashboard and use the same thirty UTC calendar days for summary, model breakdown and daily series.
- Propagate dashboard query errors instead of reporting fabricated zero usage, and document the hardware-first local-inference rollout with a read-only capacity probe. No local model is installed or activated by this change.
- Offline regression coverage exercises the actual provider adapter, background executor success/failure, workflow repair, idempotency inputs, concurrent account isolation and missing-price cases. PostgreSQL-backed CI verifies metadata persistence and duplicate suppression. This adds schema metadata but no dependencies, live model requests or model installation.

- Add a read-only, bounded JSON ranking tool that verifies the entire source dataset locally and returns only top-N numeric values, units, coverage and read-time metadata. Names can be resolved from a complete local identity map.
- Keep missing/nonnumeric values explicit, reject incomplete sources and unsafe numeric values, and preserve existing Host Agent boundaries, privacy filtering and artifact completeness checks.
- Prefer local aggregation for ranking reports, serialize tool envelopes without decorative whitespace, and expose per-call token/cache/reasoning/stop metadata and tool output character counts for subsequent cost analysis.
- Route empty reasoning-only document responses through the existing single empty-response recovery instead of spending continuation calls on a nonexistent document fragment. Do not increase normal output caps or change providers.
- Offline fixtures verify five ten-row rankings over 43 synthetic files, source completeness, compact model inputs, accounting and document recovery. Live savings and production behavior require staging and a measured live task; no percentage saving is promised.

### Artifacts: render ranking bars and complete truncated documents (#25)

- Render explicit block-bar table cells as proportional vector graphics instead of unsupported question-mark glyphs; preserve supplied bar quantities.
- Continue provider-declared truncated PDF/DOCX content with tools disabled at most twice, using the original per-call token cap and accounting for all continuation usage.
- Reject unfinished or empty continuations before artifact persistence, and preserve completion metadata in compatible-chat and Anthropic adapters.
- Verify synthetic five-category, ten-row PDF rendering and proportional bars, all document-finalization paths, bounded continuation, usage accounting and provider completion metadata in CI; no user records, real model requests, new dependencies or schema changes.
- Production deployment and the original live request remain unverified by this change.

### Chat: finish documents after bounded tool investigation (#24)

- Render explicitly requested PDF/DOCX files after the final no-tools provider turn when the tool investigation reaches its configured limit.
- Preserve the existing renderer, completeness checks, format enforcement, usage accounting and bounded provider-call count.
- Propagate existing artifact state without duplicate rendering; reject empty document content and renderer failures instead of returning text-only success.
- Add regression coverage that reproduces the missing artifact before the fix and verifies PDF/DOCX generation, failures and reuse after the tool-round limit.
- No production deployment, provider calls or schema changes performed during development.

### Server: container resource control center (#23)

- Add separate top-five CPU and absolute-memory rankings plus a searchable, sortable container resource table.
- Fetch the existing host agent's one-shot Docker statistics only after the existing server permission check; keep host information available if resource sampling fails.
- Normalize the host agent's `ports` field for the existing server UI and preserve the original snapshot fields.
- Distinguish missing measurements from zero, retain CPU values above 100%, and explain cumulative I/O counters and host-sized memory limits.
- Refresh visible pages every 30 seconds, mark retained snapshots stale on failure, and explicitly report that exact reboot time and event logs are not supplied.
- Add offline tests for actual endpoint authorization, partial failures, measurement normalization and ranking behavior.
- No host actions, new host agent capabilities, database migrations, provider calls or production deployment.


### Chat: preserve explicitly requested document formats (#22)

- Exclude the XLSX-only server dataset exporter from PDF and DOCX requests.
- Reject wrong-format tool calls before host reads or file generation, and reject mismatched cached or rendered artifacts.
- Preserve deterministic PDF/DOCX rendering after source collection; keep spreadsheet exports available for spreadsheet tasks.
- Add offline regression coverage for the actual agent and tool execution paths. Production deployment and visual review remain separate.

### Projects: file workspace and original downloads (#21)

- Add a larger file browser with search, sorting, images, PDF and bounded text previews.
- Provide authenticated original downloads for every stored file format, enforcing existing project access rules.
- Keep partial text previews read-only and prevent stale preview requests from replacing a newer selection.
- Present text editing and file creation only to users with write access; preserve backend authorization.
- Keep the file workspace mounted across project tabs so unsaved edits survive tab changes.
- Refresh file counts and storage totals after uploads and saves; make overview uploads work before opening Files.
- Scope the visual changes to Projects and retain the main dashboard.
- Add file behavior and download-handler tests plus PostgreSQL-backed access checks in CI.
- No production deployment, explicit database migration, provider requests or telemetry activation.

## 2026-10-14

### UI: chat conversation history and file downloads

- Group the user's existing chat history into readable local-date sections without changing data access.
- Give history rows a clearer visual hierarchy, accessible selection state and useful empty results.
- Unify uploaded and generated chat files under readable download cards with filenames, types and sizes.
- Extend the scoped chat design without creating another dashboard or changing the homepage.
- Add unit regression checks for date grouping and download actions.
- No database migration, provider calls, or production deployment.

### Operations: safeguard persistent production application source (#20)

- Add a one-time guarded maintenance utility to synchronize the host app build source with the already tested 5.9.5 release.
- Pin the existing application Docker image in the base Compose file without changing other services.
- Preserve full original source and Compose backups, validate the rendered configuration, and attempt restoration if the host changes fail.
- Reject overlapping app, worker and runner mounts/build contexts; verify the Compose backup matches the candidate source and preserve live file permissions on rollback.
- Document the recovery paths and verify the Python maintenance script in CI.
- No database migration, external model calls, automatic production deployment, or telemetry activation.

### UI: workspace navigation and model intelligence refinement (#18)

- Keep the home dashboard as the only global usage dashboard and move per-provider intelligence beneath API connections.
- Present unavailable pages as optional locked navigation items with friendly messages; permissions remain enforced on the server.
- Improve the Models & APIs and Audit log labels and provide a themed missing-page experience.
- Redesign the user-management form for accessible account, budget and feature controls.
- Prevent user-editor request races and make project sharing updates transactional; validate grant selections and add an isolated PostgreSQL regression test.
- Display account expiry as local wall-clock time so editing and saving an unchanged expiry preserves its instant.
- Replace soft login/logout navigation with full document transitions to discard previous-account UI state; add regression coverage.
- Test logout response ordering and failure cases with a mocked server request, preventing navigation when session revocation fails.
- No telemetry migration, provider calls or automatic production deployment.

### Security: isolate dashboard data and enforce feature access (#17)

- Scope home usage, charts, models and recent projects to each member; preserve the global view for the platform owner.
- Hide all project summaries from accounts without project access, including shared membership leftovers.
- Require feature permission for chat, attachments, activity, Models & APIs and their relevant HTTP APIs; restrict global usage controls to the owner.
- Add authenticated HTTP regression coverage for tenant isolation, project visibility and denied features.
- No database migration, telemetry activation or production deployment in this pull request.

### docs: standardize changelog and release documentation (#16)

- Restore dated and commit-attributed entries for PR #13, #14 and #15.
- Document the separately committed screenshot assets.
- Add changelog requirements to development instructions and PR reviews.
- Update telemetry documentation and record the production preflight.
- No production deployment, database migration or service change.

### `b714f5a` — feat: add owner-only Model Intelligence dashboard (#15)

- Add Model Intelligence to the existing Models & APIs interface.
- Display 7-day and 30-day provider statistics, including request counts,
  success rates, response latency and reported token usage.
- Introduce a read-only API with server-side owner authorization and
  provider-credential isolation.
- Add authenticated PostgreSQL integration tests for access controls,
  tenant isolation, date filtering and missing telemetry data.
- Correct token-completeness reporting to distinguish input and output
  samples instead of treating them as paired observations.
- Pass application build, security scanning and documentation checks.
- Keep provider telemetry opt-in; no migration or production deployment
  is performed by merging this pull request.

### `74a9436` — docs: add product screenshots to README (#14)

- Embed the existing Vector login and dashboard screenshots into
  the README with captions and descriptive alternative text.
- Update screenshot documentation to match the actual filenames.
- Preserve privacy guidance for published screenshots.

### `c5bc109` — chore: add Vector screenshot assets

- Add the login and workspace dashboard image files to the repository.
- These assets were added separately before pull request #14.

### `ba81d16` — docs: complete changelog history (#13)

- Expand the changelog to cover previously undocumented repository commits.
- Add commit-specific summaries for the initial application snapshot,
  documentation, security, CI, model broker and telemetry development.
- Preserve chronological traceability without claiming a production release.

### `8dad487` — Document available commits and add MIT attribution license (#12)

- Added the MIT license and project copyright attribution.
- Expanded the changelog to describe the previously documented history.

### `6e10ca9` — fix(cost): attribute usage events to users and verify budget isolation (#11)

- Persist the owning user ID with provider usage events, including background jobs.
- Centralize usage-event persistence and per-user total/monthly cost aggregation.
- Add a user-and-date usage index for efficient per-user budget checks.
- Add isolated-PostgreSQL tests for attribution and per-user budget separation, and run them in application CI.

## 2026-10-13

### `5945c33` — security: enforce project membership and server resource access (#10)

- Require project membership and owner privileges for protected project operations.
- Apply access checks to file, task, tool, conversation and related server-resource routes.
- Add authenticated project API integration coverage against isolated PostgreSQL and run it in CI when its fixture is available.
- Cover response preservation, file-write protection and editor deletion behavior.

### `7876e4c` — fix: harden model broker and provider telemetry (#9)

- Give explicit HTTP status precedence in retry classification and preserve provider HTTP status on failures.
- Restrict shadow comparison to opted-in background jobs; handle missing benchmark profiles and unsupported alternatives safely.
- Recognize Perplexity as a provider family.
- Normalize OpenAI and Anthropic usage while preserving the distinction between unknown and explicitly zero token counts.
- Isolate optional telemetry persistence to a dedicated, bounded PostgreSQL connection and document its operational limits.
- Add reliability tests for retry decisions, routing comparisons, usage normalization and telemetry isolation.

### `5409784` — feat: add opt-in provider request telemetry (#8)

- Add disabled-by-default measurement of provider, model, duration, response status and reported token usage.
- Keep prompts, responses, credentials and raw exception messages out of telemetry.
- Store telemetry separately from billable usage, using best-effort asynchronous persistence.
- Add an explicit migration, operational guidance and tests; include the telemetry tests in CI.

### `ce76032` — feat: introduce background model broker shadow routing (#7)

- Add a read-only model-candidate comparison at the provider resolver boundary, gated by an opt-in setting.
- Keep normal provider selection unchanged and avoid extra provider calls or prompt storage.
- Document the comparison's scope and the limits of catalog estimates.
- Add shadow-routing tests and run the model-broker test suite in CI.

### `292aefa` — fix: harden model broker cost and retry validation (#6)

- Reject negative estimated or observed costs.
- Limit transient HTTP retry classifications to an explicit status allowlist.
- Require explicit idempotency and prohibit retries after streamed output or started side effects.
- Add policy tests for the cost and retry constraints.

### `7b193f3` — feat: intelligent model broker foundation (#5)

- Add offline helpers to rank model candidates, summarize observations and assess retry safety.
- Apply privacy, permission, capability, health and budget constraints before ranking.
- Require explicit idempotency approval for retry eligibility; the policy does not itself execute retries.
- Document that the foundation is not connected to production routing and add unit tests and CI coverage.

### `e3b1fcf` — fix: secure CI checkout and simplify README (#4)

- Disable persisted checkout credentials in CI workflows.
- Simplify the README and replace the architecture graphic with a compact logo.
- Clarify screenshot guidance and validation workflow settings.

### `b50fb6e` — ci: add application build and security checks (#3)

- Add application CI for the Next.js production build and Gitleaks source scanning.
- Document current engineering checks, their boundaries and planned improvements.

### `035250c` — ci: establish Vector engineering checks

- Ignore Python bytecode and pytest cache artifacts.

### `cdc44b5` — docs: refine Vector README and architecture (#2)

- Refine product, architecture and development documentation.
- Add deployment guidance and a documentation validator with regression tests.
- Replace the banner with an architecture asset.

### `fafd0a9` — docs: redesign Vector GitHub documentation (#1)

- Rework the README, vision, architecture, roadmap and security documentation.
- Add design-system, development and third-party attribution guidance.
- Add a pull request template, documentation validation workflow and documentation assets.

### `e8fcca1` — chore: initialize Vector platform and documentation

- Add the sanitized application snapshot, Docker build, initial README, vision and contribution guidance.
- Establish the initial application, API routes, libraries, database migrations and asset structure.





## 2026-10-16 Composer release closure (#33)

The owner observed successful app/source release f38e44f with image 9a2b01e, persistent Compose pinning, health checks and rollback at vector-privacy-composer-release-20261016T123251Z-4139a9. Preserve the guarded historical release script. Syntax and archived-helper preparation were verified. The later runtime-release preflight found a changed app image; this does not invalidate the observed composer deployment and does not establish what is currently deployed. Reconcile current release records before another cutover. No production action is performed by merging this PR.
