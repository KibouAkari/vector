# Vector project handoff

Updated 2026-10-17, PR #51. Read this file, AGENTS.md and docs/OWNER_PREFERENCES.md first, then verify current GitHub/server state. These are project instructions, not public-assistant memory. This file replaces accumulated historical "current" sections; [the complete earlier handoff](https://github.com/KibouAkari/vector/blob/4f29682b9698ca314a64036a557bd518f760d17b/docs/PROJECT_HANDOFF.md) remains immutable in Git.

## Working agreement

The owner Simi executes server commands; this workspace has no SSH/server access. Concise natural German, Swiss spelling, no emojis. Supply full copyable immutable-pin commands, not only downloads. Scripts belong under /root/vector-workspace/current and run through /root/vector-workspace/bin/run. Fetch/validate revision ancestry or exact branch head, syntax and existing content. Reject symlinks/differing files; preserve failed scripts and rollback. Repeated release attempts can mean deployment already succeeded: inspect evidence before mutation. Continue already authorized work, review affected PRs, run meaningful tests, update CHANGELOG and this handoff. Keep secrets, owner prompts, player records, raw logs/config/screenshots and installed game assets out of Git; synthetic fixtures only.

Owner authorization includes final Minecraft integration and one brief introduction after qualification. It does not authorize duplicate announcements on tests/restart/uncertain delivery. Never claim deployment or real-channel delivery from source/isolated tests alone.

## Current production baseline

- Repository: KibouAkari/vector, server checkout /root/vector-workspace/github/vector. Check current main/open PRs; PR #51 is the current source work, not a production deployment.
- App source /opt/vector/app, Compose /opt/vector/docker-compose.yml, Minecraft /opt/fegcraft-updated, evidence /root/vector-workspace/releases.
- Owner-confirmed live app commit fe12d19bbc079074c51de8654e8c830b187923aa; image sha256:8d4645d72630974981ceb9985332473d41f03563b9a8f52a2b808f63387ec9cd; tag vector-app:staging-b9d34da-20261017T001416Z-b7e4cf.
- Release /root/vector-workspace/releases/vector-fresh-statistics-release-20261017T002400Z-75c2c0. Its compose.candidate.yml is the current persistent profile; guarded rollback is its rollback.sh. Preserve HOSTNAME=0.0.0.0. Do not use older composer/runtime/chat-controls releases or rollbacks against this profile.
- Owner native API normal/outage qualification passed at /root/vector-workspace/releases/vector-privacy-api-evaluation-20261017T002322Z-39dc71/result.json. Guarded release passed all app IPv4/loopback and actual host Nginx HTTPS health, preserving seven other service identities. No repeat app build/staging/release is needed for standalone Minecraft service changes.
- The earlier 502 was a partial-interface bind, repaired persistently. All future app releases must verify actual Nginx ingress plus intended interfaces, not merely any working interface.
- Private vector-privacy-ner and vector-local-inference remain installed. GLiNER unloads after 300 idle seconds; cold loading was about 8.5 seconds in one observed check. Do not promise warm timing for cold requests.
- Qualified native Python image: sha256:eca0b83a886fcc9952ef13755853ef63134e5c76733d40564460398776c92dd7. Existing Qwen model: vector-qwen3:1.7b-q8, digest 97f1ed78571eac64f6b5b7413d9bc5f50fc95ab13ad4403cd813aebb9ba3a5b0. No public model ports.

## Web features and remaining issues

Deployed active-mode menu offers Auto, Low, Normal, High, Search, Lokal and a separate default-on per-request privacy switch. Explicit off sends that authorized request unchanged but does not disable authorization/project/local-only/command boundaries. Compact review sits above composer, immediate elapsed status is visible, current-prompt preview is distinct from outgoing history/context. Replacement/original consent is exact-request/account bound; encrypted mappings restore responses locally. Fully local requests stay quiet. Protect all outgoing retrieval/tool evidence.

Native Auto/Lokal statistics read only approved saved usercache and world/players/stats files, at most 120 complete named files. Five metrics: ticks/72000 hours; walk+sprint+swim+elytra+boat+horse+minecart cm/100000 km; mob kills, player kills, deaths. Exact players/ties/positive records, all-holder and uninterrupted qualified user followups. Completed native jobs are not replayed from the old 20-second duplicate cache; in-flight retries still deduplicate. Every result rereads saved files with readAt. Unsaved Minecraft counters remain unavailable until the game saves; never issue save/console commands from chat.

Still pending, separate from Minecraft integration:
1. Interactive consent/resume for newly discovered tool secrets. Original-send consent is not blanket permission for new tool evidence; affected external sends must stop.
2. Diagnose intermittent native review with bounded busy/timeout/invalid-response/size reason codes, preserve fail-closed external sending; verify real provider execution and browser behavior with synthetic data.
3. Closed PR #37 contained no implementation despite its description. Its review items remain: credential alias promotion/persistence, structured/numeric provider values without protocol corruption, vaulted identities in original checks, history bounds, failed/duplicate/cancelled local-job handling.
4. Actual provider billing reconciliation remains unproven. Original samples had cumulative 293741 and 793264 input tokens across tool rounds. Verify ledger completeness, failed/retried calls, cached/reasoning tokens, pricing, FX, date/project scope; never invent historical corrected totals.

## Minecraft foundation and policy

Observed Minecraft 26.2, Fabric 0.19.5, Discord Integration 3.2.1. Do not use old 1.21.x APIs. Minecraft network mc-net; Ollama network vector-local-inference. Source modules are under services/fegcraft-assistant, addon under integrations/fegcraft-addon. No Vector service/addon is installed/activated and no real introduction has been sent.

Owner scope: Minecraft input only, existing linked Discord output. Discord-origin system messages do not invoke the Minecraft player hook; no separate Discord listener/bot. Answer only anchored hi/hey/yoo/hallo Vector greetings. Use authenticated sender name and matching short greeting, concise no-emoji output. Allowed saved stats, Minecraft items/recipes/facts/features/redstone, installed mods and troubleshooting. No seed, credentials, private memory, raw configuration, commands or command execution. Administrative/cheating allegations get a neutral scoped answer, never unsupported blanket denial.

Private transport uses timestamped HMAC at /v1/minecraft; no public port. SQLite stores hashed event/principal limits, no raw prompts: 3/user/minute, 12 globally, durable replay protection. Topic/private/output filtering applies before public send. The addon preserves ordinary forwarding, schedules trusted identity/delivery on the server thread, and fsyncs a CREATE_NEW introduction-v1.attempted marker before first announced answer. Uncertain delivery must not auto-resend. Actual delivery acknowledgments and Minecraft logo/head remain unimplemented.

Read-only data: /opt/fegcraft-updated/data/usercache.json and world/players/stats; data/mods metadata only. Existing fegcraft-stats.py remains private. Owner preflight found 50/50 named stat files and 63 readable mod IDs. Captured addon qualification passed:
- /root/vector-workspace/releases/vector-fegcraft-bridge-evaluation-20261016T224316Z-280627/result.json, tested 5f5eb4185480ea9ea095d37ff1cdb273498f2031.
- Addon SHA-256 0be86352e50597fc5e8e82742d87bba3ef924b8d1a8c2230c03bc89d261bc671.
- Installed integration JAR SHA-256 75e039ac6c8edad3c9423c91638ffd15d7c9b95dadb60bf69349da838afbf337; nested API 4b0dee9f505d30129b003eae08866be543cddc7b5bc11b7b42bae6b1fb77d0a9.
- Captured first/restart phases, signatures, limits, intro replay and cleanup passed. Actual Minecraft callback/Discord delivery were NOT tested. Reuse unchanged addon evidence rather than repeat capture builds just to continue.

Freeform Qwen knowledge stays disabled/unqualified. Actual three-recipe diagnosis at /root/vector-workspace/releases/vector-fegcraft-recipe-diagnostic-20261017T002415Z-b0a64a/result.json proved factual hallucinations, not formatting mismatch. Do not repeat ungrounded recipe tests or weaken the gate. Enabling freeform models later requires factual quality, restricted PostgreSQL role/driver for shared CPU slot 6194261933202610, local usage accounting and no cloud fallback. Deterministic recipes/stats require no model/DB credentials.

## Current step: installed base recipes, PR #51

Owner v3 inventory at 4441337edea29e49ba4e741f3c35435d37d272aa PASSED:
- /root/vector-workspace/releases/vector-fegcraft-recipes-20261017T121016Z-221cbd/result.json.
- 357 root archives, 9,987 recipes, 392 unique root/nested scans, 153 aliases, 180,452 entries; complete candidates, no missing targets, production unchanged, zero model/cloud calls/messages. Do not repeat broad inventory.
- Old 1.21.4 cache/remapped game JARs coexist with versions/26.2/server-26.2.jar. The latter embedded version is 26.2, observed SHA-256 183c0499c5f855570ee487dd38e141a53f0121f83a0b07a3bac2d8b6698823e8.
- Root world/datapacks entries zero; active pack/mod precedence and runtime recipe alterations remain unverified. Never call these effective modded server recipes.

New recipes.py builds supported shaped/shapeless crafting facts only from the exact pinned 26.2 game JAR, with bounded hash/version/member/schema checks. It derives quantities/default count, alternatives and rows; unknown custom predicates/conditions/types are not guessed. Answers explicitly label Minecraft 26.2 base recipes and unverified mod adjustments. Unsupported/ambiguous/long recipes are explicit.

Assistant has a backwards-compatible optional injected RecipeBook, before optional model routing. The actual server entrypoint ALWAYS supplies a book: empty if disabled, or /inputs/recipes.json with VECTOR_FEGCRAFT_RECIPES=1. Missing/invalid enabled catalog fails startup. Empty/unknown recipes cannot go to Qwen through that service. PRIVATE/stats checks still precede recipe handling. General Minecraft questions must not be mistaken for crafting just because Minecraft contains "craft".

Next owner entrypoint: scripts/deploy/evaluate-fegcraft-recipes.py at the final reviewed PR #51 pin, prepared as current/vector-fegcraft-base-recipes-evaluation.py with VECTOR_FEGCRAFT_REV. It builds the actual full catalog privately and uses the existing pinned Python image in an unprivileged UID 65534, network-none, read-only, one-CPU/256-MiB container with temporary SQLite state and no production/cloud credentials.

Its real Service/Assistant HMAC HTTP checks cover three actual base recipes, private seed rejection, ordinary-chat silence, invalid signature, replay/user limits, missing catalog without model calls and fresh synthetic stats. Recipe timings are measured. Private recipes.json/result.json are retained in releases/vector-fegcraft-base-recipes-*, cleanup and eight production identities/profile hashes verified. Parent evidence stays 0700; mounted public code/catalog have readable modes. No app build/release, model loading, game restart/install or announcement.

Local validation passed nine parser/catalog/routing tests, two actual HTTP harness tests including bad-quantity rejection, eleven existing runtime tests and four legacy model-harness tests. The three owner-supplied public 26.2 documents also formatted correctly locally. Actual installed full-catalog/HTTP qualification remains PENDING.

After success: reuse that exact catalog and unchanged captured addon evidence; prepare guarded standalone service/addon packaging, rollback and installation, then real Minecraft callback and existing Discord relay delivery checks. Finish allowed knowledge coverage explicitly; deterministic-only operation must not be described as complete freeform Minecraft knowledge. Send the authorized welcome once only after final qualification, preserving attempted-delivery state. Do not redeploy the qualified web app merely because the external repository advanced.
