# Vector project handoff

## Current owner step: installed base recipe qualification (PR #51, 2026-10-17)

Owner v3 inventory at 4441337edea29e49ba4e741f3c35435d37d272aa PASSED. Evidence: /root/vector-workspace/releases/vector-fegcraft-recipes-20261017T121016Z-221cbd/result.json. Traversal/candidate complete, no missing targets, 357 root archives, 9,987 recipe documents, 392 unique root/nested scans, 153 identical aliases, 180,452 entries, 110,850,163 member bytes and 459,489,223 hashed archive bytes. Production unchanged, no model/cloud calls/messages, no activation. Preserve this success; do not repeat broad archive inventory.

Important source distinction: the inventory includes old 1.21.4 remapped/cache game JARs as well as versions/26.2/server-26.2.jar. The latter has observed SHA-256 183c0499c5f855570ee487dd38e141a53f0121f83a0b07a3bac2d8b6698823e8 and embedded version 26.2. Root world/datapacks has zero entries; active mod/pack order and runtime recipe alterations remain unverified. Do not promote candidate variants or cached copies as effective server recipes.

PR #51 deliberately supports installed vanilla-base crafting facts, not claims about effective modded server recipes. services/fegcraft-assistant/recipes.py builds only from that exact game JAR/version and parses supported shaped/shapeless recipes, counts/default count, plain items/tags/flat alternatives. Unknown custom predicates/conditions and unsupported types are counted, not guessed. Replies explicitly say Grundrezept für Minecraft 26.2 and Mod-Anpassungen sind nicht geprüft. They include quantities and rows, bounded for channel output. Missing/ambiguous/too-long recipes are explicit.

Runtime integration is opt-in by injected RecipeBook, with backwards-compatible existing constructor calls. Crucially the actual server entrypoint ALWAYS injects a book, empty if not configured. With VECTOR_FEGCRAFT_RECIPES=1 it loads only /inputs/recipes.json; missing/invalid mounted catalogs fail startup, while an empty handler refuses recipes rather than falling back to Qwen. Stats routing and PRIVATE checks precede recipes. Freeform model knowledge remains disabled/unqualified. No app web code changes are involved.

Next owner entrypoint: scripts/deploy/evaluate-fegcraft-recipes.py at the final reviewed PR #51 pin, prepared as current/vector-fegcraft-base-recipes-evaluation.py and run with VECTOR_FEGCRAFT_REV. Do not reuse failed preflight names. It hashes/builds the exact installed base catalog privately, verifies the qualified Python image already exists, then mounts public code/catalog read-only into a disposable UID 65534 container with network none, no credentials, one CPU, 256 MiB memory, no capabilities and temporary SQLite state. It calls the real Service/Assistant HMAC HTTP path on loopback with synthetic identities/statistics and actual base recipe data.

The gate checks the three actual base recipes, no model calls even with missing catalog, private seed rejection, ordinary-chat silence, invalid signature, replay/user limits and fresh stats. It measures individual recipe request latency, keeps recipes.json and result.json under a private releases/vector-fegcraft-base-recipes-* directory, verifies cleanup and eight production container identities/profile hashes, and sends no real Minecraft/Discord messages. The catalog public-file/code modes allow UID 65534 to read their bind mounts; the parent evidence directory remains 0700. It requires no Docker build, cloud call, model loading or app release.

Local source validation: nine parser/catalog/routing tests, two actual HTTP harness tests (including wrong-quantity rejection), eleven existing runtime tests and four legacy model-harness tests passed. The three 26.2 target documents supplied by the owner also formatted correctly locally. Owner installed full-catalog qualification is still PENDING. Do not claim activation, effective mod-recipe verification, full knowledge quality or real channel delivery.

After success, reuse the exact private catalog and already captured unchanged addon evidence; prepare guarded standalone service/addon packaging and installation, actual Minecraft callback and existing Discord relay delivery checks. A deterministic-only service does not need model DB credentials; if freeform model knowledge is enabled later, restricted role/driver/usage and factual gates remain required. The owner-authorized one-time introduction remains pending final integration; do not send it repeatedly on tests/restart/uncertain delivery. Logo/head support remains unimplemented. Qualified web app baseline remains fe12d19 / image 8d4645d / fresh-statistics release with HOSTNAME=0.0.0.0.


## Current owner step: deduplicated recipe inventory (PR #50, 2026-10-17)

This supersedes the v1/v2 retry instructions below. Owner v2 execution at cd0fb872c8acd2e62402489fe4ed9c78d13d86ba reached 11,430 recipe documents and 200,093 archive entries, then failed ENTRY_COUNT_LIMIT. It had read 92,321,866 member bytes and hashed 236,924,969 archive bytes; the reported location was a Fabric API nested dependency. Evidence: /root/vector-workspace/releases/vector-fegcraft-recipes-20261017T105029Z-9b109c/result.json. Production remained unchanged; candidate/effective coverage and activation were false. The report did not preserve actual target documents. Do not infer ingredients or a verified source version from these counters.

PR #50 fixes archive accounting rather than just ignoring the failure. Installed top-level archives are hashed before metadata traversal, and identical root/nested JAR content is scanned once, with separate SHA-256 aliases recording every skipped copy's source. Nonidentical archives and conflicting recipes still get inspected. Alias provenance does not prove that a cached or bundled copy is active on the live server. The global entry budget is now 1,000,000 for unique traversals, each archive is independently capped at 200,000 entries, and recipes at 50,000. The 8-level/256 MiB live-payload and total read/hash/time/file/member guards remain. Total Python memory includes buffers and metadata beyond the logical live-payload budget.

A failure now writes already captured target documents, schemas, version/source hashes and aliases into the private result.json, alongside the error and diagnostic_progress. archive_traversal_complete and candidate_inventory_complete stay false on any failure even when missing_targets is empty. effective_recipes_qualified remains false on successful inventories too. This lets a later bounded failure provide useful recipe evidence without claiming complete or active coverage.

Next owner entrypoint: current/vector-fegcraft-recipe-preflight-v3.py from the final reviewed PR #50 pin, using VECTOR_FEGCRAFT_REV and the existing runner after origin/main ancestry and exact content/syntax checks. Preserve both old failed scripts/reports. The diagnostic performs no model call, restart, configuration edit, install or message; it writes only private evidence. Fifteen offline tests pass; actual v3 server execution remains pending.

After the installed asset report, implement deterministic supported recipe answers with verified effective source precedence, then finish service/addon packaging and real Minecraft callback/linked Discord delivery qualification. The owner-authorized one-time introduction remains pending. Do not repeat app staging/release or ungrounded model recipe tests. Live app fe12d19 / image 8d4645d / fresh-statistics release and HOSTNAME=0.0.0.0 remain the qualified baseline recorded below.


## Current owner step: recipe inventory retry (PR #49, 2026-10-17)

The owner executed the PR #48 recipe preflight at dd7b5fddd141714977725e17ca27ec31fc89c738. It failed with NESTING_LIMIT, not a model or production fault. Evidence: /root/vector-workspace/releases/vector-fegcraft-recipes-20261017T102149Z-600e76/result.json; production_unchanged true, candidate_inventory_complete false, effective_recipes_qualified false, production_activated false. No installed recipe documents were reported by that failed run. Preserve it and the failed current/vector-fegcraft-recipe-preflight.py.

PR #49 changes only the diagnostic/tests/docs. The original depth cap of two could reject normal deeper Fabric dependency bundles. The retry allows eight nesting levels and additionally caps simultaneously retained inflated nested archive payloads at 256 MiB. Existing total read/hash, count, time, symlink, duplicate and member guards remain. The live-payload budget is not a promise that total Python process RAM stays below 256 MiB; buffers and archive indexes add overhead. A remaining limit failure still aborts coverage, with diagnostic_progress identifying the last public archive/member/depth and work counters.

Next owner step is a new current/vector-fegcraft-recipe-preflight-v2.py from the final reviewed PR #49 pin, same VECTOR_FEGCRAFT_REV environment and workspace runner. Validate origin/main ancestry and script syntax/content; do not overwrite the old failed script. It remains read-only for game/app configuration, with private evidence output only, no model calls, game restart, installation or announcement. The web app stays at the already qualified fe12d19 / image 8d4645d release recorded below. The once-only introduction remains pending final integration qualification.

Eleven synthetic archive tests pass locally. The installed server retry has not yet run; deeper traversal support does not establish effective recipe precedence. Continue deterministic recipe lookup after actual assets are available, then service/addon packaging and actual game/Discord relay qualification. Do not repeat app staging/release or ungrounded Qwen recipe diagnostics.


## Current continuation: observed release and recipe evidence (PR #48, 2026-10-17)

This section supersedes older "current production" and "next owner release" instructions below. Do not repeat the app staging, native API qualification or release already completed.

Owner-confirmed production:
- scripts/deploy/qualify-and-release-fresh-statistics.py at ops pin 75f2a89a9d5a41b8b4aeae1633f151af62cbc23e succeeded.
- Native privacy normal/outage report: /root/vector-workspace/releases/vector-privacy-api-evaluation-20261017T002322Z-39dc71/result.json. All native checks passed, cleanup verified, no executed jobs/cloud calls/API fee. Single-run cold/followup/cache timings: 8922/211/11 ms.
- Live source commit fe12d19bbc079074c51de8654e8c830b187923aa; image sha256:8d4645d72630974981ceb9985332473d41f03563b9a8f52a2b808f63387ec9cd; tag vector-app:staging-b9d34da-20261017T001416Z-b7e4cf.
- Release /root/vector-workspace/releases/vector-fresh-statistics-release-20261017T002400Z-75c2c0. Current persistent Compose baseline is its compose.candidate.yml. Preserve HOSTNAME=0.0.0.0. All app interfaces and real host Nginx HTTPS health passed; seven other service identities retained.
- Guarded rollback: /root/vector-workspace/releases/vector-fresh-statistics-release-20261017T002400Z-75c2c0/rollback.sh. Do not use older composer/runtime/chat-controls releases against this baseline.

Actual local recipe diagnosis:
- /root/vector-workspace/releases/vector-fegcraft-recipe-diagnostic-20261017T002415Z-b0a64a/result.json completed with failed quality, no adapter error, done/stop for each answer.
- The three synthetic crafting questions produced invented ingredients/items/mechanics, not just synonym or output-format mismatches. Do not weaken the quality gate or repeat the same ungrounded Qwen test.
- Three local calls, 508 input / 209 output tokens, zero cloud/API CHF, no messages or production ledger writes, cleanup/unload and unchanged production verified. Knowledge remains disabled; no addon installed or welcome sent.

Next owner step:
- Run scripts/diagnostics/fegcraft-recipe-preflight.py at the final reviewed PR #48 commit using VECTOR_FEGCRAFT_REV. Prepare a new current/vector-fegcraft-recipe-preflight.py file, validate syntax/content and ancestry of origin/main, then use the existing workspace runner.
- This bounded read-only diagnostic scans root-level server JARs and versions, libraries/net/minecraft, .fabric and mods archive trees. It handles nested bundled game/mod JARs and old/new resource directory names, records exact three target recipe documents, archive/member digests, version IDs and recipe schema/types. It reads no log/player files or level.dat and does not parse or export configuration. The two Compose files are hashed only to verify unchanged state; world/datapacks is counted only, not opened.
- It writes only a private result.json under a new releases/vector-fegcraft-recipes-* directory, compares Compose/container state and makes no model/cloud requests, game restart or chat send. On limits/missing recipes it fails instead of asserting coverage. Retain the diagnostic evidence locally; do not commit installed assets or private owner output.
- candidate_inventory_complete only means the three target assets were found. active_pack_order_verified and effective_recipes_qualified stay false even on a successful candidate inventory. Installed mod assets, enabled datapacks and dynamic recipe alterations still need correct precedence/validation before answering as effective server recipes.
- After that evidence, implement deterministic supported-recipe lookup/formatting using actual installed schemas and verified source precedence; do not let Qwen invent missing recipes. Keep unknown/unsupported recipes explicit. Then qualify the real service, finish restricted model-role/driver/usage accounting if freeform model knowledge is enabled, package/install the unchanged qualified addon and test actual game callback plus linked Discord delivery.
- Existing captured addon qualification is reusable for its unchanged source; it did not prove real channel delivery. Owner authorization includes the once-only introduction after final qualification. Preserve the durable attempted-delivery marker and never resend on restart/uncertain delivery. Minecraft logo/head still has no supported implementation; do not claim otherwise.
- Repository ops-only progress must not force another web app rebuild or overwrite the current qualified /opt/vector/app source/image pin.


Updated 2026-10-17 after owner-confirmed chat-controls deployment and successful persistent listener/Nginx repair. Read OWNER_PREFERENCES.md, AGENTS.md and current repository status first. This document preserves decisions and evidence, not secret values or a substitute for a live-state check.

## First steps in a new chat

1. Identify KibouAkari/vector and read this file plus OWNER_PREFERENCES.md. Check main and open PRs through GitHub; repository snapshots in scratch may be stale or partial.
2. Do not assume a merged commit is deployed. Ask the owner to run the smallest read-only diagnostic needed when server state is missing. Do not repeat a deployment to discover its state.
3. Preserve the installed NER/Ollama services, private networks, encrypted privacy mappings and existing authorization. Never dump .env, full Compose output, Discord integration configuration or token files.
4. Update this handoff and CHANGELOG with new observed results and remaining tasks. Keep user instructions stable in OWNER_PREFERENCES.md.

## Deployment environment and last known evidence

The owner runs root commands on Debian. Repository /root/vector-workspace/github/vector; production app source /opt/vector/app; Compose /opt/vector/docker-compose.yml; runner /root/vector-workspace/bin/run; prepared scripts /root/vector-workspace/current; evidence/backups /root/vector-workspace/releases. We have no direct access to this machine.

| Item | Observed state |
| --- | --- |
| Composer app release | Owner observed success for commit f38e44f3c8edad95cc8812d9d51e53fc1079e5b7 and image sha256:9a2b01e5afd37b51983fdf336ff986db13e3679b5381a802037c2795f1908fe4 |
| Composer release record | /root/vector-workspace/releases/vector-privacy-composer-release-20261016T123251Z-4139a9/release.json; saved status/commit/image still match that release |
| Repeated runtime attempt | Script from f6e327a209b49127f331755bdc188e787eae374c stopped at the old-profile guard because the qualified runtime release was already deployed |
| Latest read-only diagnostic | Qualified image running, no OOM; completed runtime release record matches commit, image, active Compose bytes and current source tree hash; Compose unchanged by diagnostic |
| Current app deployment | CONFIRMED by owner successful guarded release: vector-chat-controls-release-20261016T233346Z-341cd8, commit 2f5b8e866f613b336ed24b5242dc93e535c985bc, image 5a2ee0f. Source synchronized, persistent Compose image pin and app health passed. Do not repeat the release |
| Native privacy service | Previously activated private authenticated GLiNER service; local workers retained; model unloads after 300 idle seconds |
| Local inference | Private vector-local-inference, Qwen 1.7B extraction/text and Hermes 8B summaries; no public inference ports |

Historical runtime qualification pins (superseded by the chat-controls deployment below):
- Tested source 86110826e2c1b4205ad5e39f5dca7213bcdfc664; identical merged source 60adca9398dff938e97df4f00bf8a2c476dde907.
- Image sha256:c33a1b853a16602e9413f4784de85337135288f55cf2437e6516b46ccfd463c0; tag vector-app:staging-8611082-20261016T162644Z-22f9a2.
- Staging report /root/vector-workspace/releases/vector-privacy-staging-20261016T162644Z-22f9a2/staging-result.json.
- Native enabled API report /root/vector-workspace/releases/vector-privacy-api-evaluation-20261016T162809Z-d3792a/result.json. Normal/outage checks passed; production unchanged; no cloud calls; synthetic jobs queued but none executed. This does not prove actual provider end-to-end execution.
- Current runtime release directory /root/vector-workspace/releases/vector-runtime-privacy-release-20261016T165856Z-c0c023. Its generated rollback path is rollback.sh in that directory; confirm its existence and guard conditions before any use. The older composer rollback is historical and must not be run blindly. The latest read-only diagnostic did not run rollback or a fresh HTTP/provider check.

Native service facts:
- Model urchade/gliner_multi_pii-v1 at 1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d.
- Service/container privacy-ner / vector-privacy-ner; previously qualified image sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7.
- App reads /run/secrets/vector_privacy_ner_token; never print/copy its value.
- Private service has unprivileged UID, read-only filesystem, resource caps and no published ports. Retain local-worker and privacy flags, networks and token mount.
- NER and Ollama serialize CPU work using PostgreSQL advisory lock 6194261933202610.
- Owner diagnostic: all three app/NER/Ollama containers running, no OOM/restarts, slot available, health 200 sleeping, synthetic scan 200. Cold request 8.903 s, model load 8.492 s, scan 0.197 s. This did not establish the cause of an earlier intermittent failure.

## Pull request review ledger

- #33: merged as f27720a13337eb4b04076932ab4745afeef08e41 after green checks. Historical composer release tooling and observed deployment evidence preserved; changelog conflict resolved without dropping runtime fixes.
- #34: merged as 26ad034160acc0d291b2c3bb286846680714a78f after green checks. FEGCraft statistics/admission foundation only; all ten synthetic Python tests pass and run in Application CI. No bot or local tool access activated.
- #35: runtime fixes merged as 60adca9 and now confirmed deployed by matching owner release/source/image/Compose evidence above. Earlier local regressions, owner staging and native API qualification passed. Real user-facing provider execution remains a separate pending check.
- #36: merged as 793e1afcf3e189dd6b670ec830dce83fa2dee960 after green checks. Guarded runtime release tooling and continuation documentation. Original guards correctly stopped the repeated old-profile release attempt; no bypass or second cutover required.
- #37: closed because head 772b2a57cfd1a1a42dccc083f3afd8e8255e540f is an empty initial-plan commit with zero changed files. Its description claimed fixes absent from source. None were implemented or deployed by that PR. The owner-requested four-PR cleanup is complete; no open PRs remained after that cleanup. Recheck GitHub for newer work.

## Privacy behavior and remaining work

Implemented source:
- Compact review above composer; immediate elapsed checking status; current-prompt preview distinct from collapsed historical/context findings. All actually outgoing history/retrieval still needs protection.
- Explicit original/replacement consent; encrypted vault/policy; local response restoration; deterministic credential detection and native PERSON detection; exact-span/boundary replacements.
- Exact per-account successful scan cache, bounded size and five-minute TTL; uncached segments batched; local encoder usage kept separate from billable cloud tokens.
- Runtime route fix: a new standalone email-writing task no longer inherits Minecraft tooling merely because it contains a word equivalent to “for”. Short player continuations still request real server data.
- Local text executor now blocks unsupported live/tool lookups before inference instead of inventing server stats. That older deployed version had no server data access; the newly deployed chat controls add the narrow deterministic statistics reader described below.
- New tool secrets under original-send consent are blocked before that tool evidence is exported. Error wording now distinguishes this from the prompt already sent.

Still required:
1. Interactive consent/resume for newly discovered tool evidence. Do not broaden consent or disable protection to remove the error.
2. Diagnose intermittent native-review failures with bounded reason codes for busy/timeout/invalid response/size, preserving fail-closed external sending. Earlier synthetic health success is not a root-cause fix.
3. Verify real user-facing provider execution for fresh mail requests after runtime deployment, plus current-only compact UI behavior. No real credentials in tests.
4. Implement and independently test the unimplemented #37 review items: credential alias type promotion/persistence; structured and numeric provider values without altering protocol fields; vaulted identities in original-send checks; configured history bounds; duplicate failure/cancelled-local-job completion handling. The old PR description is not evidence of a fixed vulnerability.
5. Continue actual provider-cost reconciliation: original owner samples showed repeated large cumulative input usage across tool rounds (293741 and 793264 input tokens), despite short visible history. Do not invent corrected historical bills. Verify ledger completeness, failed/retried calls, cached/reasoning tokens, pricing/version, currency conversion, time/project scope and provider billing differences from actual records.

## FEGCraft foundation and integration plan

Owner update 2026-10-16: input integration is Minecraft only; reuse existing Discord forwarding/output. No separate Discord listener. Verified that Discord-origin system messages do not invoke the Minecraft player hook, so they do not automatically trigger the assistant.

New source phase: a disabled-by-default Discord Integration addon compiles against the actual Fabric 26.2 / 3.2.1 nested API; private HMAC Python transport and deterministic statistics, persistent limits/replays and optional local-only knowledge adapter are implemented. Nine new Python tests plus Java interoperability/output/body/intro checks pass locally. Existing ten foundation tests remain. No addon installed, service activated, model called or introduction sent. Owner read-only preflight at cbc7cc8b5a9502de58085db8e3651f14caa980ea passed: exact public integration hash/API, 50/50 readable named stat files, 63 mod metadata IDs, Qwen available; mc-net and vector-local-inference are separate; no host javac or installed Vector addon. Compose and production identities unchanged. The owner has now passed the pinned captured container qualification; do not repeat it. Real-game/relay, isolated service packaging, restricted CPU-slot role, model quality/usage and guarded install/rollback remain unqualified.

Actual installed environment reported by owner: Minecraft 26.2, Fabric loader 0.19.5, Discord Integration 3.2.1. Do not reuse old 1.21.x APIs without verifying exact version.

Existing script /opt/fegcraft-updated/fegcraft-stats.py uses json/pathlib and sum_category, ticks_to_hours, cm_to_km, print_top10. Its source stays off Git. Collector data paths are operator-configured:
- /opt/fegcraft-updated/data/world/players/stats
- /opt/fegcraft-updated/data/usercache.json
- Installed mod inventory is under data/mods; never expose raw server configuration/seed/ops.

Foundation modules in services/fegcraft-assistant:
- stats.py: bounded regular-file reads, no final symlink following, saved timestamps and coverage, five categories (playtime/distance/mob kills/player kills/deaths), exact player lookup, ties, refuse definitive records when files/names are incomplete.
- Playtime ticks / 72000; distance sums walk, sprint, swim, elytra, boat, horse, minecart counters / 100000 km. This scope follows the existing owner report.
- policy.py: anchored greeting admission, safe display names, bounded canonical-event dedup, authenticated-principal rate limits. Limiter/dedup are process-local, not durable or a deployed security boundary.
- docs/FEGCRAFT_ASSISTANT.md states limitations. These original foundation modules themselves do not invoke models or send messages; the new addon/transport phase above is separate and not activated.

Next integration work:
1. Owner preflight and captured addon/API qualification are complete. Preserve the evidence below. Actual game callback/relay remains a separate gate; do not repeat the captured qualification just to continue.
2. Provide narrow read-only statistics/mod/recipe sources to local execution. Prefer deterministic retrieval/calculation for records; give the local model only bounded approved facts. No arbitrary filesystem/shell tools.
3. Apply topic/output policy before public sending, neutral handling of administrative allegations, no seed/credentials/commands/private memory. Add version/mod-aware Minecraft knowledge with provenance; never fabricate recipes.
4. Implement local-only inference, bounded work queues, limits and durable dedup/introduction state. No cloud fallback. Format concise channel-specific replies with author greeting.
5. Qualify on synthetic fixtures and isolated owner environment, then guarded deployment/rollback. Only then send the authorized once-per-channel introduction and verify delivery outcomes. Logo/avatar/head support remains unimplemented.

## Release handling cautions

Archived release helpers live only on the owner machine. Local copies can test syntax/factory preparation but not prove server state. Existing machinery protects source, images, Compose, other containers, backups and rollback. New repository documentation/ops commits do not mean /opt/vector/app should be switched to new main without a qualified application release. Preserve exact tested-image/source equality and never rebuild solely to archive docs.

A repeated release may stop because its previous successful run changed the image. Establish a matching completed release record and actual app/source/Compose health. If changed state is unknown, stop before mutation and reconcile it. Do not reinterpret image-only drift as a successful deployment.

## Captured staging preparation

The owner preflight has no pending retry. New evaluator source prepares only a private temporary service/network and compiler containers, without changing Minecraft/app/NER/Ollama services. It uses an exact pinned official JDK image and the existing qualified native Python image; no production credentials, data or public network ports enter the evaluation. Local captured first/restart phases and nine evaluator regressions pass. PR #40 reproduces and fixes silent loss of an immediate next question during worker completion, using single-request admission and a bounded completion handoff before visible delivery. Interrupted/incomplete qualification cannot pass; partial timeout/completed logs are bounded and daemon/permission inspection errors propagate to cleanup failure. Owner Docker qualification passed at vector-fegcraft-bridge-evaluation-20261016T224316Z-280627: revision 5f5eb4185480ea9ea095d37ff1cdb273498f2031, both first/restart phases and cleanup true, no model/cloud calls or external messages, production unchanged. Qualified addon artifact SHA256 0be86352e50597fc5e8e82742d87bba3ef924b8d1a8c2230c03bc89d261bc671. PR #40 merged as b4e2a58248c1782321d2f40d07df476ed5e03c55 with identical tested tree. Actual knowledge inference, dedicated CPU-slot DB role, native token telemetry, recipes/mod correctness, game callback/Discord delivery, logo and guarded installation remain pending. No announcement has been sent to real channels.


## Current priority: web-chat controls and data reliability

Owner update 2026-10-17 takes priority before final Minecraft installation. Replace visible Low/Normal/High/Search/Lokal tabs with a small active-mode menu plus Auto. Add a separate names/credentials privacy switch. This is explicitly authorized for the owner's outgoing request, not permission to disable login/project/server access checks or command restrictions.

PR #41, branch feat/chat-controls-local-data-20261017, implements default Auto and default-on request privacy. The off choice restores this conversation's old placeholders locally and is sealed into a user-bound job policy; a loose payload flag cannot disable worker protection. Owner actual native read and application staging have now passed as recorded below. The owner has now successfully deployed this exact app as recorded below.

Auto/native local statistics use only /opt/fegcraft-updated/data/usercache.json and world/players/stats via the existing read-only Host Agent, at most 120 complete files. Five categories match the existing collector convention. No raw files enter a model. Exact player/rank/tie/positive-record output includes saved-file provenance; incomplete/invalid/unnamed/unknown-player requests fail. A conservative native grammar rejects mixed tasks and conceptual explanations; follow-ups stop at the latest standalone request. The executor selects from restored requestText/safeOriginalMessage, not appended retrieved evidence. Menu options render in a viewport-positioned body portal. Missing player stats and explicit null counters fail. Auto does not steal PDF/file/credential tasks; other requests retain the existing tool-capable cloud path. Explicit Lokal still refuses unsupported tools and never falls back to a cloud provider. It is not arbitrary local model filesystem access.

The owner completed native read, staging, native API qualification and guarded release; exact evidence follows. Local regressions passed; browser UI and real provider execution remain pending. No Minecraft installation or announcement has been performed.


## Observed PR #41 / #42 production release

PR #41 merged as 2f5b8e866f613b336ed24b5242dc93e535c985bc with the exact tree of tested e8b6b6e690aa893e3fc0a0641e07261c0414ffc6. The owner has completed the pending native read and staging phases above; do not repeat those phases or rebuild this image.

- Actual Host Agent check: /root/vector-workspace/releases/vector-chat-server-read-20261016T231729Z-306171/result.json. Passed, snapshot available, statistics complete, 50 files, production unchanged, no model/cloud calls, no exported player records.
- Application staging: /root/vector-workspace/releases/vector-chat-controls-staging-20261016T231731Z-6a08fa/staging-result.json. Passed existing auth/history/files/project checks plus Auto/Local/Normal, boolean preference, account-bound sealed policy and queued-unexecuted privacy-off checks. Temporary services removed; production and main checkout unchanged.
- Exact qualified image: sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d, tag vector-app:staging-e8b6b6e-20261016T231731Z-6a08fa.
- Current live app is now commit 2f5b8e866f613b336ed24b5242dc93e535c985bc / image 5a2ee0f, confirmed by the owner successful release below. The older runtime baseline c33a1b8 is historical.


Owner execution on 2026-10-17 Europe/Zurich completed the pipeline at immutable ops revision c973ac2535582038c52ba5881ef67c4e5e7fb267, merged through PR #42 as fc65e41ef932fe66112c82a062f059c719872b24. All PR #42 CI checks passed before merge. No further staging build or repeat release is needed.

Native API evidence:
- /root/vector-workspace/releases/vector-privacy-api-evaluation-20261016T233310Z-e54379/result.json.
- passed true; exact app runtime revision e8b6b6e and image 5a2ee0f; qualified native image eca0b83. Normal and outage phases passed with isolated database, production unchanged and cleanup verified.
- Normal tests covered explicit off without scans, authorization, bound consent, encrypted masked jobs, restored responses/history, original-send choice, quiet local mode, owned history and attachments, local-only project routing, natural reset credentials and separate local encoder metrics.
- Outage tests confirmed default-on blocks before writes; explicit off remains available; fully local remains quiet.
- Observed timing for this synthetic run: initial cold review 8732 ms, follow-up 205 ms, exact cached review 11 ms. These are single-run observations, not a latency guarantee; cold loading remains noticeable.
- 11 queued synthetic jobs in total after the outage phase, none executed. Cloud calls zero, API cost CHF 0. Native qualification does not prove real provider execution.

Production release evidence:
- /root/vector-workspace/releases/vector-chat-controls-release-20261016T233346Z-341cd8.
- Commit 2f5b8e866f613b336ed24b5242dc93e535c985bc; tag vector-app:staging-e8b6b6e-20261016T231731Z-6a08fa; image sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d.
- Tested/merged trees matched. Fresh backups, app source synchronization, persistent image pin and app health passed; runner reported SUCCESS.
- Existing guards retain worker, runner, PostgreSQL, Redis, Ollama, NER and Minecraft identities. The release did not install the Minecraft addon, send its introduction, migrate/restore the database or submit model requests.
- Current guarded rollback is /root/vector-workspace/releases/vector-chat-controls-release-20261016T233346Z-341cd8/rollback.sh. Preserve it; do not run older release/rollback scripts blindly. A future deployment must use this new baseline, not the superseded runtime/composer pins.

Next steps:
1. Owner refreshes the web page and checks active-mode dropdown, Auto and independent privacy switch. Test a deterministic own-server/player statistics request in Auto or Lokal and confirm the actual completed response/provenance. The 50-file read already passed; successful production job execution and real browser rendering still need owner observation.
2. Test a new short email request with synthetic names/credentials using replacement and explicit off. Real provider execution and whole-server cloud-tool reads remain distinct from queued-job/native qualification; do not claim all tools are fixed without results.
3. If a new failure occurs, collect bounded metadata/reason codes and the relevant job state rather than rerunning the release or dumping secrets.
4. Continue pending interactive consent for new tool evidence, provider billing reconciliation and final Minecraft integration only after the web flow is confirmed. The Minecraft addon is not installed and its once-only introduction has not been sent.


## Resolved: post-release listener/Nginx 502

Owner update 2026-10-17 after the successful release: host Nginx serves 502. Read-only owner evidence shows vector-app running, zero restarts and no OOM, on vector-internal 172.23.0.5, vector-local-inference 172.25.0.3 and vector-privacy-ner 172.26.0.3. Only 172.25.0.3 returns health 200; 127.0.0.1 and the other app addresses are unreachable. Host Nginx is active. This confirms a partial-interface bind; the actual Nginx upstream address has not been captured. Do not call the public flow healthy merely from the earlier release result.

The older release helper health check stops at the first working interface. It did not test the public proxy route, so the successful release was insufficient to establish availability. scripts/deploy/fix-app-listener.py prepares a guarded persistent app HOSTNAME=0.0.0.0 correction, reusing image 5a2ee0f and the unchanged 2f5b8e8 live source. It validates the exact old release/source/Compose, stores original/candidate files, preserves seven other container identities, recreates only the app, probes every IPv4/loopback health endpoint, tests and reloads host Nginx, then probes https://vector.kibouakari.com/api/health via local Nginx/TLS. No model request or image build is involved. The owner has now observed successful repair as recorded below. Compose bytes changed: future guards must use the listener repair candidate as the current profile, and the older app release rollback must not be run blindly against it.

The local Nginx HTTPS route and all app interfaces now passed. Browser-level rendering, completed statistics jobs and actual provider execution still require owner observation. Preserve the exact repair evidence below. Future application release health gates must require the actual ingress route and intended listen interfaces; the historical archived helper remains unchanged by this targeted repair.


Owner-confirmed repair on 2026-10-17 Europe/Zurich:
- Script revision bc52a8f38098eea0e2123f74cc0c8c8392358bed, PR #44 merged as a59a36ff0c00b751fa028bfd8df2e6d6a93201bd after green Application CI, documentation, secret scan and both Java compiler checks.
- Evidence directory /root/vector-workspace/releases/vector-listener-fix-20261016T235002Z-913eee. Runner reported LISTENER FIX SUCCEEDED and SUCCESS; script archived at /root/vector-workspace/archive/phases/vector-app-listener-fix.py. Do not rerun this exact-baseline repair.
- All IPv4 app interfaces including loopback passed health with database/Redis ok; tested/reloaded host Nginx HTTPS ingress returned health 200. This is stronger evidence than the older any-interface release probe. It does not independently prove remote DNS/browser rendering.
- Persistent app environment now requires HOSTNAME=0.0.0.0. Same app source commit 2f5b8e866f613b336ed24b5242dc93e535c985bc and image sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d; seven other production container identities were retained; no model requests.
- Current Compose baseline is the repaired compose.candidate.yml in that evidence directory, with result.json recording deployed status and original Compose retained as compose.original.yml. Future release/rollback work must inspect this record and preserve the listener setting rather than require the older chat-controls release Compose bytes.
- The older chat-controls release rollback remains historical and will reject this changed Compose; do not bypass that guard. No new standalone manual rollback command is claimed by this repair. Reconcile the repair's saved original/candidate and actual source/image/state before any rollback.

Next owner phase: refresh the web page, confirm dropdown and privacy switch, then run the same player statistics question in Auto and a synthetic email test. Do not repeat deployments or rebuild merely to discover state. Minecraft installation and its announcement remain pending.


## Current priority: PR #46 fresh records and final Minecraft integration

Owner update 2026-10-17 02:01 Europe/Zurich: the repaired web app now completes a five-category native player statistics request (vector-local-statistics, CHF 0), so basic production native execution is observed. However a followup asking for all record holders went to a cloud text answer using the earlier player response, then a further server request used cloud tools and returned an incomplete list. Do not record those cloud claims as definitive source evidence or commit player values.

Two source causes are addressed in the new change: conservative native intent omitted Rekordhalter/short statistics-refresh followups, and findRecentDuplicate reused completed native jobs for 20 seconds. Native intent now follows only an uninterrupted chain of qualified user statistics requests, ignores assistant text and stops at unrelated tasks. All-holder requests reset a previous player selection. Completed native results are never reused; in-flight retries remain deduplicated, and ordinary completion replay is retained. Each response freshly reads saved files and records readAt. Minecraft persists game counters periodically: a fresh filesystem read cannot include unsaved in-memory actions. Never issue a world save/console command from chat to hide this limitation.

The Minecraft deterministic service now supports all five record-holder categories, rereads saved files per distinct event and fixes a computation-slot/HTTP delivery race found by the prior intermittent runtime test. The new regression holds the previous response handler open while making the immediate next request; it must be admitted after completed computation. The addon source/intro marker are unchanged. The owner has reiterated authorization for final Minecraft integration with the once-only introduction; no further generic permission question is needed.

Next owner steps prepared in this source change:
1. scripts/deploy/stage-fresh-statistics.sh with VECTOR_STAGING_REV at the final reviewed branch pin fix/fresh-statistics-20261017. It requires current qualified app image 5a2ee0f and exact repaired Compose from vector-listener-fix-20261016T235002Z-913eee, preserves eight production identities, builds the new runtime once and runs isolated app/queued-job regressions. It does NOT deploy the app.
2. scripts/deploy/evaluate-fegcraft-knowledge.py with VECTOR_FEGCRAFT_REV at the reviewed pin, after it is an ancestor of origin/main. It reuses the pinned qualified Python image and existing Qwen model, never installs packages or changes production configuration. A real read-only production PostgreSQL session holds advisory slot 6194261933202610 while the disposable unprivileged client runs the real LocalKnowledge adapter/Assistant policy on six factual/crafting questions and five zero-model private/off-topic/mod cases. Native tokens/calls, latency, cleanup/unload and unchanged production fingerprints are reported; no cloud/API fee or production ledger write is claimed. Failing factual/output/routing checks keep knowledge disabled.
3. After owner results, prepare the exact qualified app release against the repaired listener baseline and require all-interface plus Nginx ingress health. Reuse its image; do not run the historical runtime/composer/controls release script against the changed profile.
4. Continue Minecraft packaging, actual-game/relay qualification, restricted slot-role/driver and local usage accounting, then guarded installation/activation. The model benchmark intentionally does not qualify production DB privileges: the outer real CPU lock is held by the coordinator without exposing DB credentials to the temporary client. That gate is explicitly false in its report. No actual game callback or Discord delivery is claimed by it.

Welcome behavior remains authorized once after final qualification/activation, never repeated on restart or uncertain delivery. Current addon claims an fsynced introduction marker before sending its brief introduction with the first answered addressed question; no real announcement has been sent. If activation timing is changed, qualify it and preserve once-only state. Logo/head presentation remains unimplemented; do not claim otherwise.

All new changes are source-only until the corresponding owner release/activation succeeds. Current production source remains 2f5b8e8 / image 5a2ee0f with persistent HOSTNAME=0.0.0.0 and the repaired Compose baseline.


## Owner results for PR #46 and PR #47 release preparation

Owner output 2026-10-17 02:16 Europe/Zurich confirms:
- Fresh statistics staging PASSED at b9d34da3f07b91f27de1800aba214d507922b760, same tree as merged fe12d19bbc079074c51de8654e8c830b187923aa. Report /root/vector-workspace/releases/vector-fresh-statistics-staging-20261017T001416Z-b7e4cf/staging-result.json.
- Exact image tag vector-app:staging-b9d34da-20261017T001416Z-b7e4cf, ID sha256:8d4645d72630974981ceb9985332473d41f03563b9a8f52a2b808f63387ec9cd. Existing auth/project/privacy controls and completed-versus-in-flight native job/followup tests passed. Temporary services removed, main checkout and production unchanged. Do NOT rebuild or repeat staging.
- Local model report /root/vector-workspace/releases/vector-fegcraft-knowledge-20261017T001539Z-4256c9/result.json: passed false. Piston/comparator/repeater and five no-model private/off-topic/mod cases passed; crafting-table/furnace/hopper failed QUALITY_OR_ROUTING_MISMATCH. Each made one model call, but the report did not retain responses. Do not assume every failure is a factual hallucination: aliases, parsing, response termination or output filters need diagnosis.
- Six local calls, 1017 input / 425 output tokens, zero cloud/API CHF. Production unchanged, cleanup verified, weights unloaded. Dedicated DB role remains unqualified. No Minecraft addon/knowledge activation or introduction occurred.

Prepared next owner entry point scripts/deploy/qualify-and-release-fresh-statistics.py with immutable VECTOR_CHAT_RELEASE_REV from the reviewed ops followup. It reuses the exact 8d4645d staged image; the generic native privacy evaluator verifies that runtime/build inputs are unchanged apart from docs/tests/scripts/workflows. It qualifies normal/outage privacy on the new image and then invokes scripts/deploy/release-fresh-statistics.sh only after cleanup. The app source installed is the matching merged fe12d19, not the later ops-only commit. Current pre-release source remains 2f5b8e8 / image 5a2ee0f and repaired HOSTNAME=0.0.0.0 Compose from vector-listener-fix-20261016T235002Z-913eee. The release validates the original app release and listener-repair source/image/profile evidence, preserves seven other production services and fresh backups/rollback, and requires all app IPv4/loopback endpoints plus the actual Nginx HTTPS health body. It can test/reload the existing host Nginx config if ingress is stale after app recreation; no Nginx config is rewritten.

Recipe diagnosis is independent of the app release. Run scripts/deploy/evaluate-fegcraft-knowledge.py at the ops pin using VECTOR_FEGCRAFT_EVALUATION_SCOPE=recipe-diagnostic and VECTOR_FEGCRAFT_REV. Use a new current filename so the earlier failed evaluation remains intact. This repeats only the three failed synthetic recipe cases, records bounded actual model text/adapter answer/errors/done reason and native metrics, and keeps the full_knowledge_qualified flag false even when the subset passes. It accepts only the two observed app images 5a2ee0f or 8d4645d and retains the real shared CPU lock/cleanup/unload safeguards. It reads no owner prompts or private server configuration; actual model observations are synthetic and saved privately, never committed to Git. A failed diagnostic after successful app release must not roll back the independent app release.

Next: record actual new app release/API paths and status; inspect the synthetic recipe answers before selecting a fix. Prefer verified version-aware recipe evidence over guessing or merely weakening the gate. Continue restricted DB role/driver/usage and actual-game/relay qualification, then guarded Minecraft activation and the authorized once-only welcome. Do not describe Minecraft as installed or the welcome as sent before owner evidence.
