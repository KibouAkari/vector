# Changelog

The complete dated history is retained below. Historical scripts and paths describe their original change, not current installation instructions. Private server labels, operating paths and release identifiers are generalized in this copy; exact evidence remains in the private archive and immutable Git history. New entries extend the history rather than replacing it.

## 2026-10-20 — Reduce the fixed context before the first conversational token

- Keep the experimental local mode gated. Shorten its fixed instruction text from 831 to 475 characters using concise internal English instructions while still requiring German replies; use compact JSON envelopes. Backend policy, tool permissions, identity checks, output validation and deadlines remain unchanged.
- Stop attaching own-player counters and the configured game joke to unrelated initial questions. Authenticated self identity remains explicit, named-player evidence remains available, and fresh counters/operator jokes are still fetched through the existing public statistics lookup. Bound both documentation-index and knowledge-pack snippets to two rows.
- Thirteen dialogue tests pass locally, including a synthetic clock prompt below 900 characters, preserved verified identity, fresh changed counters and retained operator-joke lookup. Seventeen preload/stream/evaluator guard tests also pass. These checks prove smaller source payloads and retained boundaries, not native speed or universal answer quality; no service activation or game restart.

## 2026-10-20 — Separate diagnostic model loading from response latency

- Add explicit `--preload --profile-only` qualification diagnostics. Send one empty local chat preload under the existing restricted CPU slot, bounded to 45 seconds with no prompt, schema or user context; retain the pinned model, 4096 context, two threads and five-minute keep-alive. Reject unexpected generated text/tokens and record loading metadata separately.
- Release preload admission before the one synthetic streaming question receives its original 20-second transport and 24-second computation budgets. Skip that question when loading fails. Existing process watchdog, baseline/secret/role guards and non-activation policy remain; ordinary evaluation does not preload.
- Seventeen local preload, streaming and evaluator tests pass, including lock release and skipped generation after preload failure. Startup latency is a hypothesis, not a verified diagnosis; native evidence remains required. No service, model configuration, game restart or real channel delivery is performed by this source change.

## 2026-10-20 — Profile one native dialogue request without activating it

- Add an explicit `--profile-only` evaluator mode for one synthetic clock question. It retains the existing model, schema, context, two CPU threads and 20-second deadline while reading streamed chunks, so headers, first content/thinking arrival, output size and final native counters can be distinguished from an undifferentiated timeout.
- Keep the destination fixed and allow at most one request. Bound line/total/text sizes, reject partial or truncated output, close the transport and retain the existing shared-slot, watchdog, release-baseline and native-child termination guards. Metadata contains no prompts, generated prose or exception messages.
- Record measurement completion separately from qualification: the profile never passes the full dialogue quality gate and cannot authorize activation. Five mocked stream-profile tests and seven evaluator boundary tests pass locally. Native results remain pending; no runtime code, production profile, game service or model configuration is changed by this source update.

## 2026-10-20 — Reduce conversational request overhead and expose bounded timing evidence

- Keep the experimental local dialogue mode opt-in. Replace the three-field planning envelope with one validated answer-or-tool field, shorten the common instruction prefix, remove the per-request random nonce, and keep unrelated global leaders out of every initial prompt. Fresh statistics remain available through the existing allowlisted lookup. Documentation snippets are bounded and explicitly marked when shortened.
- Reduce candidate prediction ceilings from 112/96 to 80 tokens without increasing the 20-second native timeout, 24-second computation deadline, CPU threads or model/context size. These are source-level reductions, not proof that native latency or answer quality passes.
- Add opt-in prompt-size, prediction, token-count and native timing metadata without prompt text, generated prose, exception messages or secrets. Stop the evaluation after the first timeout and report incomplete coverage as failed. Unknown token totals remain unknown rather than displaying measured zero.
- Twenty-eight targeted local dialogue, evaluator, metrics and factory tests pass. Existing production modes and deployment profiles are not activated or changed by this source update; native qualification remains required.

## 2026-10-20 — Preserve the installed slot identity during dialogue evaluation

- Keep the existing service's restricted database role and read-only secret mount when evaluating a generic conversational candidate. The evaluator previously used the generic secret filename and could fail before the first model question on an existing private installation.
- Require one matching read-only mount, one factory default and one exact role comparison. File ownership, mode, destination, CPU-slot and model checks remain enforced; no credentials are printed or copied into the repository.
- Six evaluator boundary tests pass locally, including own-child cancellation and rejection of missing, writable or ambiguous mounts. Native dialogue quality remains unqualified; this change does not activate a service or restart the game.

## 2026-10-20 — Prepare an opt-in local conversational assistant

- Add an experimental mode 6 with self-written local answers instead of social-expression matching or canned fact selection. Existing modes and the default-off constructor retain their behavior; no deployment enables the candidate automatically.
- Supply fresh public observations, configured-zone time and reviewed documentation. Permit one bounded lookup for statistics, portraits, recipes, documentation or installed mods; retain the same local model destination, CPU admission, usage callback and request deadline. There is no command, arbitrary-file or web tool.
- Keep short per-author/source conversational context in bounded RAM, encourage wording variation and retain independent input/output restrictions. Schema and numeric checks are explicitly not a factuality guarantee.
- Add structural, identity, tool and policy tests plus an operator-pinned four-question native evaluation. The evaluation preserves installed catalog pins and private aliases, uses synthetic player files and temporary state, and performs no activation, game restart, channel delivery or production usage-ledger write.
- Native semantic accuracy and latency remain unqualified until the actual host report is reviewed. Preserve the README and complete historical changelog; document the candidate separately.

## 2026-10-19 — Sharpen playful banter and explain paused ranking pages

- Give the peaceful-server player-kill-leader joke a shorter, sharper voice without a defensive closing disclaimer. Keep it confined to gameplay and derive its target from fresh counters.
- Recognize named good-or-bad player questions, including the exact alternate phrasing reported from live chat.
- Keep the existing question and replay limits. A rate-limited continuation of an owned, unexpired ranking gets one brief pause notice per minute, capped at three notices globally. Do not compute, consume or advance the rejected page; unrelated and repeated rejected messages remain silent.
- Normalize Unicode consistently in continuation guards and refresh a paused page's expiry through the advertised wait without consuming it. Avoid repetition-related character decoration when requesting the next ranking page. Extend authenticated regressions for the live wording and the real three-answer pause/resume sequence.

## 2026-10-19 — Route player opinions and multi-category rankings by intent

- Keep the best-player joke limited to direct global best-player questions. Normalize named good/bad evaluations and alternate portrait phrasing without changing player identity.
- Count fresh positive first places across the five tracked categories, retaining ties and distinguishing records from subjective skill. Add a clearly playful peaceful-server roast based on the current player-kill leader rather than fabricated events.
- Page Top-N requests across all five categories with bounded, expiring per-author continuation; read counters afresh on each page. Recognize the narrow ranking typo `spielerkilld`.
- Answer bounded numeric smalltalk and sword-enchantment recommendations directly instead of returning unrelated anvil guidance. General enchantment effects follow the official Minecraft Help enchantments reference; modified server rules are not claimed.
- Extend authenticated synthetic regressions for the reported question forms, identity isolation, fresh data, pagination and forbidden-request boundaries. Runtime-only installation retains game state, private character and other services; no game restart or model call is required.

## 2026-10-19 — Block leader totals and ordinal block types (PR #102)

- Answer which player has the highest saved mined-block total or registry-filtered block-item use, including ties and combined server-wide requests. Placement output retains its approximation scope.
- Respect numeric and common written ordinals for personal block types instead of silently returning the most frequent type. Equal counters share a level; a second level means the next lower distinct positive value. Unsupported or absent levels are explicit.
- Preserve personal identity, complete-data checks, missing-registry refusal, reply bounds and the independent assistant-only rollout boundary. These deterministic questions introduce no model requests.

## 2026-10-19 — Personal block statistics and weapon-style impressions (PR #101)

- Answer personal saved block totals and most-used/mined block types, including ties and authenticated self identity. Filter placement approximations through the current block-item registry; do not count food or tools as placed blocks.
- Describe preferred weapon families from fresh item-use counters, with explicit ties and missing evidence. Keep weapon preference distinct from accuracy, kill attribution or proven combat ability.
- Tolerate a common portrait-question misspelling and a unique adjacent-letter transposition in player names. Retain ambiguity clarification and existing policy/rate/replay boundaries.
- Make guarded updater failures actionable with a safe phase label and private stderr evidence, without printing resolved configuration or secrets. Network-disabled qualification still precedes any assistant recreation.

## 2026-10-19 — Give fresh player portraits a more natural voice (PR #100)

- Combine multiple observed strengths into short, varied player impressions instead of a statistics list followed by a fixed label. Keep descriptions grounded in fresh counters and advancements; never invent victims, weapon kills or personal character traits.
- Recognize attached target names and shortened portrait questions. Retain unique-name clarification, authenticated self identity, per-author context expiry and incomplete-data refusal.
- Vary concise single-statistic wording while retaining exact values, ranks and identities. Include the earlier comparison/Top-N corrections in the independent assistant update.
- Allow an explicitly pinned portrait module alongside the runtime in the guarded updater. Qualify both in network-disabled fixtures and preserve every other installed module, state, image and service. No game restart, welcome or model call is introduced.

## 2026-10-19 — Apply an already qualified web image (PR #99)

- Reuse the exact successful stage image/source without rebuilding or repeating detector qualification. Require unchanged app/worker generations and source/configuration; snapshot other services afresh and preserve them during release.
- Pin the existing Compose project and change only the app image and listener. Preserve source/configuration backups and provide guarded, generation-aware rollback with durable private progress.
- Check idle jobs read-only before replacement and verify app interfaces plus local/public HTTPS health. These checks do not claim an atomic worker drain or provider execution.
- Keep Minecraft assistant updates separate. Synthetic release/recovery tests and CI verify source boundaries; production application remains an operator-run step.

## 2026-10-19 — Pin existing Compose projects for assistant updates (PR #98)

- Require the operator-pinned existing project name and pass it explicitly to every assistant Compose render, configuration hash, recreate and rollback operation. Retain the existing service, working-directory, image, code and configuration guards.
- Separate explicit ranking subjects from category aliases, including usernames resembling a statistic. Reject comparisons containing unknown names after conjunctions.
- Isolate the admission client from terminal process-group signals so Ctrl-C cannot release the shared CPU slot before detector shutdown. Cover the actual process-group signal path without a model call.
- Record successful operator qualification of the web candidate: native normal/outage boundaries and cleanup passed, with no production activation. Reuse the resulting image for a separate guarded release rather than rebuilding it.

## 2026-10-19 — Harden recovery cleanup and preserve ranking subjects (PR #97)

- Retain full private before/after fingerprints, including paused and failed runtime states. Require the existing owned release lock and remove legacy build intermediates on failures.
- Unwind controlled termination through cleanup. Verify native shutdown while holding CPU admission, with an independent monotonic PID1 deadline before lease expiry; failed cleanup cannot be reported as success.
- Keep actual player names separate from category typo aliases and reject unknown named subjects before comparing players.
- Verify the saved original resolved Compose profile and image before rollback writes. Track owned rollback progress and container generations so interrupted recovery can resume without accepting unrelated drift.
- Synthetic failure tests cover these boundaries; real Docker/native qualification and production updates remain operator-run, separate from CI.

## 2026-10-19 — Fresh comparisons and bounded Minecraft leaderboards (PR #96)

- Compare one saved statistic for exactly two known players with the actual counts, direction, difference and ties. Read fresh data for each request.
- Answer Top 1–10 queries with competition ranks and cutoff ties. Recognize the narrow ranking typo `monkills`; ambiguous or incomplete inputs do not become server totals.
- Recognize the best Minecraft player phrasing while retaining all-category ranks and independent policy, identity, replay and rate limits.
- Provide a separately guarded assistant-runtime-only updater. Preserve installed companion/server code, private configured character, image, environment, state and secret bindings. A synthetic network-disabled check must pass before activation; no Minecraft restart, welcome, model or cloud call.
- Focused ranking and updater tests pass locally. Actual operator Docker qualification and game/Discord responses remain separate evidence.

## 2026-10-19 — Qualify a fresh web recovery image before release (PR #95)

- Add a stage-only build and native API qualification against an operator-owned readiness baseline. Pin existing local base/runtime images, bound resources and retain candidate/evidence without changing production source or Compose.
- Use synthetic users and disposable PostgreSQL, an offline detector and an internal temporary network. Preserve all production container/configuration fingerprints and clean owned test objects and synthetic secrets.
- Check original-send with separately signed tool masking through the built HTTP API, including exact reviewed text and rejection of altered preferences. No worker job or cloud call is executed by this matrix.
- Require a later separately guarded live release; successful source tests are not a production fix. Minecraft, its assistant, local inference, backups and welcome state are not deployed by this stage.

## 2026-10-19 — Restore documentation depth and complete history (PR #94)

- Restore all 62 earlier dated sections and their technical paragraphs with narrowly generalized private references.
- Restore the full README structure, reference screenshots and acknowledgements; extend it with current privacy modes, integration boundaries and architecture status.
- Preserve the original screenshot blob identities and all historical dates/PR associations. Live deployment evidence remains private.
- Documentation and source-publication validation cover this restoration. No deployment or game action is implied.

## 2026-10-19

### Exact original snapshots and credential promotion — PR #93

- Preserve the exact reviewed message/context on subsequent provider rounds even when new tool values overlap names or ordinary numbers.
- Bind the actual project message wrapper to the encrypted consent snapshot; tool evidence and arguments never inherit that exemption.
- Promote reused mappings to credential types before saving and displaying later review metadata.

### Web reliability — PR #91

- Preserve original-send consent for the reviewed prompt/context while separately protecting newly read tool evidence with placeholders.
- Bind the evidence preference to the signed review, preserve legacy fail-closed behavior and mask structured credential fields.
- Restore advancement arguments only inside authorized local tools.
- Keep short local requests usable in long chats by dropping oldest complete turns.
- Keep own-server corrections within the latest uninterrupted statistics task.

### Repository portability — PR #92

- Separate private deployment scripts, inventories and operating notes from reusable source.
- Document Minecraft as an optional independent integration, with operator-supplied data locations and aliases.
- Build container dependencies with `npm ci` and the committed lockfile.
- Refresh README and engineering guidance. Preserve authorization role identifiers and existing private Git history.
- Reject dangling/directory symlinks in source checks and detect configuration disappearance during a read-only inventory.
- Add a source publication check and read-only web deployment inventory; no game deployment or restart is performed by this change.


## 2026-10-19 — Web privacy and local context recovery

- Preserve explicitly approved original prompt/context while separately masking newly read tool evidence; bind this choice to the signed review and job policy.
- Inspect sensitive structured fields and restore advancement lookup arguments only inside authorized local tools.
- Keep short local requests usable in long conversations by dropping old complete turns instead of rejecting the whole chat.
- Resolve own-server corrections only within an uninterrupted statistics task. Minecraft deployment is unchanged.
- Validation: targeted privacy, routing, controller and real local-executor regression tests. Live deployment remains separate.


## 2026-10-19 — Record observed player-portrait deployment (PR #90)

- Operator confirms PR89 deployed at [private release reference], only assistant recreated, Minecraft/current addon unchanged and saved advancements available. No new restart/welcome required.
- Actual isolated qualification passed:1 local social call,177 input/33 output tokens,14.260s; seven synthetic deterministic cases0.045–0.070s. Unknown usage/cloud/API fees/messages0. These measurements do not claim live latency or a real-channel portrait test.
- Update authoritative handoff with minecraft-portraits.json, exact release/verifier/rollback and remaining manual chat verification. Documentation only; no runtime changes, server action, model test or message.

## 2026-10-19 — Fresh player portraits and natural smalltalk routing (PR #89)

- Operator confirms PR88 same-container restart/load verified at [private release reference]. Eyy/Discord input and the best-player joke were observed; feelings smalltalk still fell into clarification. Record actual state before adding another assistant-only update.
- Recognize feelings, mood and more conversational phrases; add harmless dry humour to the existing short native social prompt. Preserve local-only model/CPU lease/role, independent restrictions and output bounds.
- Add fresh public-statistics portraits for known players, authenticated Minecraft self, unique nickname/typo matching and bounded own UUID followups. Show evidence-based playful game impressions, never inferred real personality, invented victims, all death causes, weapon kills or guaranteed PvP skill. No permanent labels, value cache or ordinary-chat ingestion.
- Optionally mount only a verified saved-advancement directory readonly. Bounded per-player parsing includes completed advancement counts/known labels; missing/invalid files do not become invented events. Keep weapon uses distinct from kills and bound placed totals by the live block registry.
- Guarded updater verifies observed PR87 backend and PR88 game start, stages exactly1 accepted native feelings reply plus synthetic deterministic portraits over signed HTTP, then recreates only assistant. Preserve pack/addon/game/backup/markers/state and owned rollback. Seven new focused tests plus affected local regressions pass; actual native stage and production rollout remain pending.

## 2026-10-19 — Load the staged addon with an owned regular restart (PR #88)

- Operator confirms PR #87 deployed mode5 at [private release reference] with192 facts/63 mods and3 accepted native calls (981 input/25 output tokens); cached repeat0.051s, zero cloud/messages. Minecraft has not restarted; greeting addon is still pending.
- Add a guarded same-container restart command using exact confirmed backend release and staged addon proof. Acquire existing backup/release locks, retain data/world directory identities, all configuration and welcome markers. No Compose recreation, download, backup or model request. Normal stop/start recovery targets the original ID/image only.
- Verify healthy game, new startup registration/boot evidence, staged bytes and unchanged other services/profiles. Read Docker stdout/stderr privately; never publish logs/config/credentials. Record attempt before stop, make completed repeat read-only, and block uncertain repeats. Do not replay introduction. Source tests do not claim a live restart or real greeting test.
- Four focused synthetic tests cover delayed current-load readiness, same-ID stop/start, failed/unclean-stop recovery and exact allowed snapshot difference. Update operational handoff and operator preferences, including that old StartedAt-protected rollback requires current-aware review after this restart.

## 2026-10-19 — Grounded mod context and a concise Vector character (PR #87)

- Operator confirms PR #86 backend deployed at [private release reference]; staged greeting addon remains for the next regular restart. No further game restart or welcome is requested.
- Add opt-in mode5 with192 reviewed public facts covering63 observed mod IDs and Minecraft basics. Retrieve at most6 same-topic facts and let the same local4B model select1–2 allowed IDs. Compose only reviewed text/wording variants, with bounded own followups and short static-selection caching. Original84 passage catalog, recipes, model/image/role/lease and fresh statistic computation retained. This is not universal mod correctness or unrestricted factual generation. Source/license/scope review is recorded separately.
- Add warm, concise voice, light casual/Swiss cues and gentle own repetition humour with180-second/256-author bounds. Never tease on reported trouble or uncertainty. Generic best-player questions get the operator-requested configured best-player joke, marked as an opinion; real metrics and private-command boundaries take priority. No emojis, ordinary-chat capture or cross-author memory.
- Add a guarded assistant-only updater with readonly pack mount and mode4->5. Require exactly3 accepted native selections with complete token usage in isolated signed HTTP before deployment; zero cloud/game messages. Preserve game/addon/pack/state/backup/markers and offer owned rollback. Repeated completed update verifies rather than rerunning tests.
- Eight focused synthetic tests cover factory pin/permissions, readonly candidate, complete-usage gate, real local signed HTTP, ID-only selection, own-cache/TTL and opinion/statistic/policy separation. Actual server-native stage and deployment remain unobserved until the operator runs the pinned wrapper.

## 2026-10-19 — Repair statistic intents, group greetings and pending addon salutations (PR #86)

- Operator confirms PR #85 cutover worked: native welcome visible, logo attached and Discord-origin questions answered. Full terminal report was not retained; exact live release/result is read and verified locally by the next guarded update rather than fabricated. No new game restart is requested.
- Route historical player-count questions to a fresh, complete saved-statistics count instead of generic claim-documentation matches. State that players without retained saved statistics are not proven by this count; no claim of online population or complete lifetime join history. Ignore generic player/server/action words as independent documentation subjects.
- Add named ore-mining rankings from bounded saved minecraft:mined counters, combining ordinary/deepslate variants, ties, authenticated Minecraft self, fresh reads and unknown/incomplete-data rejection. Explicitly label ore-block counts rather than diamond item drops. No live inventory/private files or fabricated records. Combined unrelated ore types ask a clarification.
- Direct group morning/afternoon/evening wishes address everyone, detailed introductions explain local scope and limits, backpack-upgrade answers ask for the desired tier. Reuse reviewed catalog/model/role/image; no additional freeform prompt or blanket knowledge claim. Seed/commands/cheating/gamemode/credentials and existing rate/replay boundaries remain.
- Extend anchored case-insensitive Python/Java greetings with bounded ey/eyy, longer yo, moin, servus, German time-of-day and Swiss variants. Normalize multiword greeting whitespace. Existing yo/yooo/hello already worked. Backend changes can deploy immediately; the running Java filter only changes on the next regular Minecraft restart.
- New assistant-only updater verifies immutable PR #84 backend and completed PR #85 identity evidence. Stage uses synthetic readonly stats/cache and isolated state, signed HTTP, zero model/cloud calls/messages. Reuse the exact existing public mod-recipe export and readonly mounts. Compile against checksum-pinned installed API using cached JDK, unprivileged/network-disabled container; only one offline unit run. Stage the owned addon JAR on disk after healthy backend rollout; preserve old bytes/UID/GID/mode, all game identities and welcome markers. No Minecraft start/stop/recreate or announcement. New JAR activates on the next independently scheduled restart. Owned rollback restores backend and pending JAR before that restart; changed game generations require review.
- Eight focused synthetic tests cover real signed HTTP, ore ties/freshness/incompleteness, player-count/claim separation, direct replies, greeting boundaries, exact profile relocation and owned pending-JAR metadata/generation guards. Existing policy, reviewed service, conversation and dialogue regressions pass locally. Required CI includes Java17/25 and normal build/security gates. Server deployment and new greeting activation remain unobserved here. PROJECT_HANDOFF records new pointer/rollback and avoids replaying the completed identity installation.

## 2026-10-18 — Preserve unspecified Docker user and install chat identity against deployed mod context (PR #85)

- Operator diagnostic confirms the failed identity release rolled back before recreation: same original game healthy, old addon restored, Discord input/avatar/head still disabled. The only committed-image config mismatch is container User empty string versus omitted/null image User; parent layers, OS and architecture match. Operator then successfully deployed PR #84 at [private release reference] with84 reviewed passages/63 mods, installed Backpack11.3.2 recipes and zero native/cloud calls or messages. Minecraft remained unchanged.
- Normalize ONLY None/empty User as an unspecified user during private stopped-container preservation and verify the never-started reference container resolves to that same setting. Explicit root, numeric IDs and groups remain distinct; Env/order, launch fields, labels, layers, bounded private tar content/metadata and mounted-world exclusion checks remain strict. OCI ImageConfig.User is an optional omitempty string; see https://github.com/opencontainers/image-spec/blob/main/specs-go/v1/config.go and Docker user defaults https://docs.docker.com/engine/containers/run/#user.
- Identity installer now uses the immutable PR #84 verifier and exact observed release, checking runtime source equality, pointer/profile/manifest/catalog/recipe digest and accepted zero-call stage before any stop. Retain qualified addon/assets, role/image/current backend, all world/backup/HTTPS/rollback guards and native once-only welcome at least15s after confirmed readiness. No backend recreation, new model tests or game cutover performed here.
- Extend scoped installer tests for both unspecified User representations, every explicit user pair, strict unrelated fields and backend provenance rejection. Existing Docker CI proof checks real commit, never-started reference User and private content preservation with mounted data excluded. New operator retry uses current/vector-minecraft-chat-identity-install-v4.py; do not rerun v3 or the backend updater. Real Discord input/avatar/head/welcome delivery still needs operator observation after successful cutover.

## 2026-10-18 — Expand public mod guidance and installed backpack recipes; hold game recreation (PR #84)

- Operator confirmed PR #83 mode4 deployed at [private release reference]: only assistant recreated,52 complete saved-player files/63 mods/975 vanilla base recipes,2 local social calls278 input/47 output tokens, first6.957s/followup5.927s, cloud0/messages0. Later game identity attempt [private release reference] passed HTTPS publication but failed ROOT_PRESERVATION_IMAGE_CONFIG_CHANGED before recreation. Recovery invoked the same original game's start; health and the precise differing fields still require the read-only diagnostic. No game recreation/addon/logo/v2 welcome success is claimed. Do not repeat the old installer or relax preservation checks.
- Expand the checksum-pinned catalog14→84 concise entries with public purpose context for all63 captured mod IDs and targeted claim-access/backpack controls. Source/provenance and scope are recorded; library/background mods are distinguished from gameplay and live settings remain unknown. Reject the old template-example link for Droppable Villager Trades, use its author project page; WWOO ambiguity stays explicit. Original short factual paraphrases only, no raw documentation download to model prompts, commands or private config. More context is retrieved selectively, not dumped wholesale.
- Add bounded export of public recipe JSON from the exact installed Travelers Backpack11.3.2 JAR. Preserve digest/version, reject archive/schema ambiguity, mount the export read-only with an exact checksum. Support the custom shaped backpack recipe type, tags and common English/German/standard spelling aliases before vanilla recipe fallback. Describe it as an installed mod BASE recipe, not a proven effective runtime/datapack recipe. Never read world metadata or guess ingredients.
- Friendlier mode4 statistics retain fresh aggregation/identity/completeness/ties internally but omit repeated provenance and avoid repeating the sender name. Single personal kills become a short sentence with value and rank; other-player names remain explicit. Bound the word hack to avoid treating Spitzhacke/Hacke as prohibited requests while retaining command/seed/gamemode/cheating protections. Greeting policy was already case-insensitive; new backend/signed-stage case tests verify vector/VECTOR/VeCtOr rather than inventing a proven casing fix.
- New guarded assistant-only updater accepts ONLY the observed PR #83 mode4 pointer/release/profile/code, preserves role/image/networks/state and adds one readonly public recipe input. Requires recovered game health first. Stage uses synthetic signed HTTP and isolated state, tests casing/claim building rights/three recipe phrasings/other-mod guidance/friendly UUID self/private policy with ZERO native/cloud calls. Same existing image, no model download/import/old quality matrices. Own rollback and pointer retained. Game cutover remains HELD for root-config diagnosis and a subsequent current-aware installer.
- Seven focused public recipe/guidance/format/rollout/diagnostic tests pass locally, along with current reviewed-service/conversation tests. Historical selector catalog copied byte-for-byte into a pinned test fixture so its old31-case synthetic matrix remains meaningful; new expanded coverage is separately tested. No server deployment/model request or game message here. Update PROJECT_HANDOFF after operator output.

## 2026-10-18 — Author-aware statistics, direct reviewed help and local smalltalk (PR #83)

- Resolve first-person Minecraft statistics using the authenticated sender UUID and current usercache/stat files, never a Discord display-name match. Discord supports explicit player queries; unlinked first-person requests ask for the Minecraft name. Preserve explicit unknown-player rejection. Answer all five ranks separately from first-place records, combined player/mob kills in one fresh read, and clarify the subjective best-player question rather than inventing an overall winner.
- Opt-in mode4 reuses the existing restricted role, qualified local Qwen4B image/model and reviewed catalog. Unique reviewed answers and unambiguous claim instructions bypass the model; reviewed candidates remain usable during selector failure. Add short local social generation with own-author/source RAM-only context, independent forbidden-input/output checks, no cloud fallback and exact native usage. Thanks/farewells/identity need no model. No claim of universal mod accuracy, arbitrary unrestricted chat or verified live rights.
- Guarded assistant-only updater verifies the actual deployed PR #78 mode3 baseline, preserves limits/replay/state/role/image/networks and changes only code/catalog bind sources plus mode3→4. Reuse all unchanged image/role/addon/public assets and backup evidence. Exactly two short native social calls via isolated signed HTTP qualify the new runtime before deployment; no Minecraft restart/game message. Native failure blocks deployment. Separate guarded identity installer accepts ONLY this verified mode4 pointer/source/stage evidence, retaining all existing root/world/pack/HTTPS/welcome protections. The exact owned empty directory from the failed PR #81 attempt is retired while its old baseline still holds.
- Six focused conversation tests plus existing dialogue, policy, reviewed service, publication and pure installer checks pass locally. CI retains normal regression checks; Docker and real native qualification remain respectively CI/server stages. No server deployment or real Discord input/logo/welcome delivery observed here. Operator should use the NEW bundled two-script wrapper, not earlier installer pins. One game recreation happens only after assistant staging succeeds and identity preflights pass; v2 welcome remains native, once, at least15s after readiness.

## 2026-10-18 — Retry logo publication safely and preserve actionable failure evidence (PR #82)

- Operator PR #81 attempt at [private release reference] rolled back BEFORE recreation/root preservation. Operator read-only diagnosis confirms original game healthy/same ID, current assistant healthy, app running, all five managed files at before hashes, both compose preflights approved, current Nginx syntax and origin/public health200. Only an empty public-asset directory remains. No new addon/avatar/head/welcome activation is observed. Original failing command/status was hidden; its exact cause remains unproven.
- Replace immediate one-shot HTTPS checks in this installer with a bounded30s readiness poll after Nginx reload. Require200, exact asset hashes on origin AND public routes, and healthy app before Minecraft can stop. Retry only bounded transient transport/status conditions and wrong200 bodies during publication; TLS errors, redirects and permanent HTTP failures fail closed. No insecure TLS, HTTP fallback or reduced digest checks. Record redacted curl/status/digest observations and preserve initial publication evidence.
- Record named phases and separate primary/recovery private tracebacks with safe public error codes. A recovery failure no longer hides all evidence of the original failure. No credentials/configuration/body content enters stdout. Remove the prior empty directory only after proving the exact rolled-back release/script/game/protected-state/file hashes and root-owned directory metadata within that attempt's time window; never recursive removal. New pre-recreation recovery removes only its own empty public directory.
- Seven new tests pass locally, including actual loopback TLS/curl with an initial404 then correct assets, rejection of an untrusted certificate, persistent wrong200 digest failure, redirects, bounded retry, specific/private error reporting and failed-release directory ownership/drift checks. Existing seven pure installer/root tests also pass (Docker proof skipped locally; existing CI runs it). Root preservation, world bind, mode3 backend, captured addon, local-model policies and one-time delayed welcome are unchanged. Actual retry/production delivery remain unobserved.

## 2026-10-18 — Preserve root state and install qualified Discord input and Vector identity (PR #81)

- Operator PR #80 preparation PASSED at [private release reference]. Current mode3 is intact; existing nightly snapshot is11.97h old with recorded consistent staging and world-header restore probe. Current addon still has Discord input/avatar/head off. Fresh installed-API capture [private release reference] passed Discord/policy/replay/limits and delayed-native-welcome tests, JARSHA440d4231e5e5711e14250b39528f9b9702b4b8e29f8ecedf4bbfbe671b02da1f. No production activation or messages in that preparation.
- Add an operator cutover that reuses this exact capture/assets and verifies the actual PR #78 mode3 baseline, current persistence and recent owned backup without rebuilding or re-running models. Before recreation, cleanly stop the original game, preserve its root layer/config in a never-pushed local image, and compare bounded private tar contents/archived metadata for the one known changed path against a fresh never-started isolated image container. Preserve the parent layer chain/config, refuse deletions/new paths/oversized input, and recover the same original game if preservation fails. Mounted world data is deliberately excluded from this image and retains the exact existing host bind; this is not a second full-world backup or a full restore claim.
- Publish only exact logo PNG/pack over checked HTTPS/Nginx before downtime. Only game image, approved pack variables and observed Fabric loader0.19.5/launcher1.1.2 are pinned; current cached launcher required and startup download/reinstall overrides rejected. Install the captured addon and enable linked-human Discord input, per-message avatar, native head and mandatory logo pack. Assistant/profile/code/catalog/role/state and all other containers remain untouched. Legacy assistant manifest is retained; this separate release owns the new game/addon files and must precede any older assistant rollback.
- Add guarded rollback retaining the preserved root image and both version pins, restore only owned files/pack keys and retain all world/player/mod data and welcome markers. Signal/pre-recreation failure recovery starts the original game even if config restoration is refused. Completed reruns verify ownership instead of recreating/resending. Arm the single operator-authorized native v2 welcome only after ready game, addon registration, pack and protected-state checks; addon waits>=15s, durable attempts/uncertain delivery never retry.
- Seven local unit tests pass; the additional real Docker preservation proof runs in CI (synthetic scratch image, no fixture started, changed root file compared, mounted world excluded). Five preparation and seven dialogue regressions also pass locally. Actual operator cutover, real Discord input/logo rendering/welcome delivery remain unobserved; no production success or zero-risk guarantee claimed. Root image/private archives may contain existing configuration and must stay local/private.

## 2026-10-18 — Prepare Discord input and Vector identity against the deployed mode3 service (PR #80)

- Operator confirms actual Minecraft party explanation and own claim-rights followup work and reach Discord. Discord-origin rank request remains unanswered; avatar/head absent. The new addon hook and logo pack were qualified earlier but never installed. An apparent record reply to a party question remains unexplained; do not claim a reproduced routing bug.
- Add a current-mode3-aware preparation entrypoint. Verify PR #78 deployed manifest/profile/code/image, existing role-only mount/security, installed captured addon, full production snapshots and delivered introduction markers. Reuse the existing isolated addon/API evaluator with delayed-welcome/Discord/policy tests; prepare exact brand assets privately. No app/assistant replacement, Minecraft restart, model request, cloud request or actual message. Runtime code remains unchanged.
- Collect current persistence/private writable-layer review and existing nightly backup evidence in the same run. Exact writable paths remain in root-private operator evidence. Read only owned Restic config/snapshot metadata with no cache/lock; no backup, restore tree, prune, old-archive removal or secret output. A recent successful consistent snapshot plus world-header restore probe does not prove a full restore or include the container root layer. Missing evidence remains a separate explicit gate, not an activation authorization.
- Add regressions for a party question following records and Discord-origin mobkill rank freshness. Five preparation evidence tests and seven dialogue tests pass locally. Actual server preparation, Discord input/logo client rendering and guarded cutover remain unobserved; keep recreation/backup holds and v1/v2 welcome semantics. CI includes the new tests.

## 2026-10-18 — Record successful reviewed-help deployment and pending real-chat verification (PR #79)

- Operator PR #78 release PASSED at14:59, source45f3400d472603e0e55d16c31fce32bb1a8283fb, evidence [private release reference]. Only assistant recreated; actual mode3 health/readonly inputs passed with50 player files/63 mod IDs/975 base recipes. Minecraft/other services and production state retained.
- Actual staged signed HTTP/policy/native routes/restricted role/own followup passed. Two local calls used303 input/18 output tokens, unknown0, first11.034s/followup5.526s; no cloud/API fee/game message/welcome. Keep these measured scope/time distinctions and real_chat_verified=false.
- Update active image/source/code/network/role/rollback baseline and next three addressed Minecraft tests. Preserve14-passage limitation and separate Discord-input/logo/welcome/recreation/backup holds. Historical mode0-only bootstrap guards must not be rerun or loosened against deployed mode3. Documentation only; no production action or repeated model/role/image qualification.

## 2026-10-18 — Qualify and roll out reviewed local Minecraft help through the actual service (PR #78)

- Operator PR #77 v2 role preparation PASSED at [private release reference]/result.json. Actual private destination verified, owned role created, three DB privilege audits/no app-object or permanent-create rights, inherited PUBLIC TEMP retained, actual same-database contention both directions/release passed. Cleanup and production fingerprints unchanged; no model/cloud/messages/activation. Reuse the driver image, role and private secret.
- Add explicit opt-in server mode3 using the qualified4B passage selector, fixed14-passage catalog checksum, restricted0400 role file and actual local-usage accounting. Default0 and legacy explicit modes retain their contracts; no freeform or cloud fallback. Native stats/recipes/security policy are unchanged.
- Add an operator release that verifies original native/role/image/addon evidence, re-audits the existing owned role READ ONLY without creating/resetting it, stages the actual service construction on private networks and isolated SQLite state, then sends signed synthetic HTTP tests. Only two native selector calls check explanation/own followup, exact usage and deadlines; policy/ordinary chat/recipe/fresh-stat routes/missing evidence require no model. No game/Discord sends, downloads, imports or repeated31-case model gate.
- Preserve every existing input/security/state binding; change only owned assistant image/code/mode and readonly catalog/role mounts plus two existing private networks. Save guarded atomic profiles/manifests and rollback before replacing that service alone. Test failure recovery from a partial transition even when the assistant is down, newer-edit/foreign-operator refusal and retained SQLite state. Preserve Minecraft and all other service fingerprints, addon, backup and welcome holds.
- Fifteen new factory/signed-HTTP/profile/rollback guards passed locally alongside23 reviewed-knowledge and16 role guards. Extend PG17.11 CI with read-only existing-role verification and absence refusal. Actual staged model/service rollout and real chat remain operator-observed gates. Update current handoff and next immutable-pin operator action.

## 2026-10-18 — Verify inspected private PostgreSQL aliases for slot-role preparation (PR #77)

- Operator PR #76 preparation stopped at ROLE_PRIVATE_DATABASE_REQUIRED before any database connection/role mutation, release [private release reference]. A subsequent redacted read-only operator diagnostic confirmed the DSN host is the Compose service and inspected alias, uses the standard port/no URL options, and resolves only to the current private PostgreSQL container. The former container-name-only assumption was too narrow.
- Inspect only the fixed running app/PostgreSQL containers on vector-internal. Pass bounded alias/IP/container-identity metadata privately to the existing app-side actor; before any SQL, require an inspected hostname and every DNS result to equal an inspected private address. Bound lookup to5s. Reject missing/foreign/public/mixed/changed destinations, unsupported ports and query overrides in both production and disposable-fixture routes. Do not output addresses or DSNs.
- Sixteen local guards pass, including Compose alias acceptance, DNS mismatch/error, wrong network/container, private-IP scope, no SQL before proof, query overrides and fixed-container provenance. Preserve all real PG17 privilege/slot CI gates. No runtime/model change, rebuild, production activation, service/game restart or message. Retain the failed script/report and existing private intent; provide a separately named v2 retry and update handoff.

## 2026-10-18 — Prepare and qualify an owned production CPU-slot role without service rollout (PR #76)

- Operator PR #75 actual driver/PG17.11 fixture passed, including denied app/permanent-create access, inherited PUBLIC TEMP, both slot directions, release and cleanup. Record exact prepared db331 image, wheel fingerprint and report; reuse them without downloads, rebuilds, readiness or native31-case reruns.
- Add a guarded operator step that audits every connectable database (including template1) before creating one owned restricted login and private credential. Check PUBLIC/direct object/column/routine/SECURITY DEFINER/foreign/default data/create privileges and role attributes/memberships/ownership. Preserve all global PUBLIC ACLs and report inherited TEMP honestly. No application rows or admin credential in probes/model/service.
- Verify actual runtime.local_slot in both directions against the existing-app same-database CPU lock using labelled, nonroot readonly driver probes. Keep current mode0/profile/source and all nine production identities/configurations unchanged. Role writes and private secret creation are explicit; no service rollout, inference/cloud/game message, backup or Minecraft restart.
- Add foreign-role-safe resumability and mounted/active/dependency-aware transactional rollback without DROP OWNED/CASCADE or credential overwrite. Eleven local guards pass; add actual PostgreSQL17.11 create/resume/privilege/cross-database/rollback and Python slot integration to existing CI driver environment. Update project handoff/current next operator command; production role and service activation remain unobserved until operator evidence.

## 2026-10-18 — Prepare binary driver and qualify admission only in a disposable database (PR #75)

- Operator readiness v2 passed: current mode0/profile/input scope retained, installed captured addon27s vs candidate24s, PG170011 PUBLIC CONNECT/TEMP+schema USAGE only in reported scope, role absent, base-image psycopg absent. Cleanup verified/production unchanged; no writes/model/cloud/messages/activation. Record actual evidence and stop repeating readiness/model gates.
- Pin three maintainer PyPI wheels by exact URL/size/SHA with existing psycopg/binary3.2.13 and typing_extensions4.15.0. Actual scratch downloads/hash checks and offline installation/binary import passed; preserve package/bundled licenses. Prepare a separate offline-built local driver image without host installs or changing any running image.
- Add actual runtime.local_slot integration harness restricted to a disposable database name, synthetic credentials/data and temporary role. Check app-read/permanent-create denial after removing read-only default, inherited PUBLIC TEMP honestly, attributes/membership, contention both ways and normal/exception release. Operator uses installed PG17.11 image in an internal-only labelled temporary network with tmpfs DB; preserve production fingerprints and clean owned fixtures.
- Nine local scope/artifact/evidence/cleanup tests passed. Add the same actual driver harness to disposable PostgreSQL17.11 CI. Production role creation, effective privilege review, service-only rollout/health/rollback and real chat are still pending. No runtime/model change, production role, game restart, backup, welcome or activation. Update handoff and current next command.

## 2026-10-18 — Compare complete mount records without enumeration-order false alarms (PR #74)

- Operator PR #73 audit stopped with READINESS_PRODUCTION_CHANGED at09:14. Its original failure report omitted the field differences and completed metadata. Three subsequent locked read-only operator samples at09:19 found only Mounts order changes for app/assistant in samples1/3; full mount records equal ignoring order, no configuration-file differences. Original failure's exact diff was not retained; don't retroactively certify that earlier snapshot.
- Canonicalize ONLY Docker inspect Mounts enumeration by full-record JSON; preserve every field and duplicate, all other arrays/configuration/identity/start/network/file hashes stay strict. Add redacted container/field and changed-file-count diagnostics. Keep the first failed comparison and completed audit sections on failure; never resnapshot to replace a real failure or emit Config/secret values.
- Sixteen local tests passed, including order-only equality, changed source/destination/RW/type/propagation/new fields, duplicates/removal, non-mount changes, file hashes and failure-report preservation/redaction. The PostgreSQL catalog query/driver probe/model/runtime are unchanged. New operator v2 target preserves failed v1. No model rerun, production change, role/ACL change, restart or activation. Update current handoff.

## 2026-10-18 — Record successful native help gate and audit admission prerequisites (PR #73)

- Operator PR #72 v3 PASSED31/31: cold10.642s, warm median4.592s,17 calls/2821 input/168 output, unknown0; no cloud/API fees/messages/activation, production unchanged, cleanup/unload verified. Preserve limited14-passage scope; no universal mod/version/rights claim or repeated unchanged model test.
- Add a non-activating operator audit of successful evidence/current source, owned mode0 backend/read-only data scope, exact installed vs captured addon deadline, offline base-image psycopg availability and aggregate READ ONLY PostgreSQL privilege catalogs. No credentials/names/application rows are output; no role/ACL changes, packages, model requests or restarts. Temporary driver probe uses network none, no mounts, nonroot/read-only and labelled cleanup. Nine production containers/configuration fingerprints must remain unchanged.
- Twelve local guard/evidence/baseline/cleanup tests passed, and real operator report parsing passed. Add a disposable PostgreSQL CI integration test for schema/table/column/sequence/routine/default PUBLIC ACL semantics and unchanged repeated audit; no production role security claim from test fixtures. Driver/role, assistant-only rollout and real chat remain pending. Update project handoff/current next action and retain backup/game recreation/welcome holds.

## 2026-10-18 — Complete container-protection evidence and broaden native qualification (PR #72)

- Operator v2 ran correctly: party followup passed, but chest protection chose none. Keep25/26 as failed quality; warm median4.234s/cold10.179s passed timing, exact2193 input/136 output across14 calls, no unknown/cloud/messages/activation, unchanged production and verified unload/cleanup.
- Add a separate source-reviewed free-chunk/container protection procedure and aliases, preserving the existing permissions guide. No prompt/model/routing changes or forced answer fallback. Catalog14 passages; installed version/settings and all-mod coverage remain unqualified.
- First six actual scratch controls caught a furnace wording gap (5/6); after completing the generic container guidance, six new controls selected the intended chest/area/furnace/purpose/followup entries. Fresh loads on different hardware are not operator timings or broad relevance proof.
- Expand actual operator qualification to31 cases/17 calls. Keep all26 existing cases and strengthen chest protection to require the claiming step; add3 action paraphrases, unavailable live limit and missing backpack procedure. Original safety/usage/deadline/cleanup gates remain. Thirty selector/index/composed tests and unchanged native foundation suites passed locally. No production change, download/import, restart, backup or chat send; update handoff and new v3 target.

## 2026-10-18 — Procedural followups cannot repeat purpose explanations (PR #71)

- Record the operator actual25/26 selector result: only party-followup chose an overview instead of a useful step. Cold10.639s/warm median4.567s and all latency gates passed; exact2298 input/138 output across14 calls, no cloud/messages/activation, unchanged production and verified cleanup/unload. Quality remains failed.
- Add required reviewed answer kinds and generic requested-answer-form filtering before selection. Procedures cannot fall back to overview prose; reviewed limitations remain valid. Keep same-author dependent context when a followup names its subject, and preserve the current action intent when inheriting topic.
- Update the same sourced Claim UI fact and catalog pin/schema. Retain the full26-case native quality/safety/usage/deadline gate,14 calls, disabled production mode and dedicated-role/deployment requirements.
- Three actual scratch selector controls chose the correct purpose/own action/new-topic entries; fresh loads on different hardware are not operator timing proof. Seven new behavior regressions bring selector/index/composed tests to28. No download/import, restart, deployment, backup run or chat send. Update current handoff and next v2 script target.

## 2026-10-18 — Offline reviewed passage selection after failed grounded prose (PR #70)

- Record operator complete63-ID/64-JAR public source inventory; explicitly reject the Fabric example-template link, retain WWOO version ambiguity and8 missing sources. Add per-ID review status without claiming full documentation coverage.
- A new actual scratch4B prose probe still invented glass mechanics despite correct evidence. Replace this candidate's freeform output with local enum-only passage selection; render only an exact reviewed German fact or knowledge-gap reply. Five independent actual reference selections chose the relevant entry/none; different hardware and fresh loads are not operator warm-latency or broad-quality evidence.
- Add a bounded checksum-pinned offline index,13 short original factual paraphrases with primary-source provenance and version limits, own-author dependent topic context, independent input/output policy and no public runtime fetches. Existing production/default adapter remains unchanged.
- Compact the project handoff around current evidence, operator rules, production pins and remaining gates; preserve full earlier history through an immutable Git link.
- Add26-case isolated operator qualification reusing the existing candidate, shared read-only CPU coordinator, unchanged factual/safety/latency/usage gates, verified unload/cleanup and production fingerprints. No download/import, restart, backup run, chat message or activation. Restricted role/driver and guarded assistant-only deployment remain outstanding.

## 2026-10-17 — Public mod source inventory after failed independent model probes (PR #69)

- Owner4B import/integrity/preservation passed but full quality failed: two timeouts and fabricated cows/sheep/glass. Eleven calls, exact totals NULL after2 unknowns; known1522 input/284 output, warm median7.906s, no cloud/activation/messages, verified unload/cleanup and unchanged production. Preserve inactive candidate; no repeat model download or guard relaxation.
- Run the same verified public GGUF with checksum-pinned official CPU llama.cpp light b11706 binaries in scratch. Two ungrounded questions also produced false mechanics; one supplied-source reading probe answered correctly. Different hardware/sampler means no operator latency claim or complete native-root-cause conclusion. Three actual scratch invocations, no production calls/data or deployment; one successful case does not qualify general QA.
- Add operator-run read-only public Fabric source inventory: bounded fixed metadata entry, reviewed ID allowlist, safe version/license fields, canonical public publisher roots only, explicit duplicate/missing/unknown coverage and production fingerprints. No source fetch, model/DB call, config/player/world read, nested archive traversal, service action or backup change. Public source candidates require author/license/version review before generic offline retrieval; no hardcoded test-answer promotion.
- Eight synthetic tests cover URL privacy/normalization, bounded root metadata, duplicate coverage, symlinks/non-regular files and operation scope. Add CI coverage and update project handoff with exact evidence and pending grounded-QA/least-privilege rollout work. General mode remains OFF; native welcome/recreation and nightly backup gates unchanged.

## 2026-10-17 — Test a pinned non-thinking 4B candidate after native/raw failures (PR #68)

- Operator PR #67 minimal controls gave identical wrong text/token counts for every chat/raw pair in English/German. Eight calls, exact260 input/520 output, no unknowns/cloud/messages, cold4.712s/warm median5.700s; production unchanged, verified unload/cleanup. Do not present a template swap or speed-only success as a fix.
- Add checksum-pinned Unsloth Qwen3-4B-Instruct-2507 Q4_K_M as a separate inactive namespace, with reviewed source/license, exact revision/size/SHA, resource/private-runtime preflight, bounded no-clobber download, actual imported-blob verification and marker-bound reuse. Keep original models, failed partials, production settings and game online. Import and inference both use actual shared admission; no runtime/image/package update or automatic activation.
- Add an explicit candidate constructor name while preserving old default; omit thinking option only for the non-thinking candidate. Existing answer/context/security/deadline guards unchanged. Full composed gate adds held-out glass and returns evidence on request without shrinking scope or weakening normal CLI failure. Normally11 native calls across20 fixtures; raw synthetic answers still need manual factual review, not keyword trust.
- Eleven new synthetic import/transport/preservation tests and existing affected regression suites passed locally. Extend CI and update project handoff/local-help docs with measured failures, candidate pins, resource/storage costs, pending quality/least-privilege/deployment gates and independent-backend next step if basic facts still fail. No game/assistant/app activation, restart, backup job or welcome.

## 2026-10-17 — Minimal local prompt and rendering controls after verified artifacts (PR #67)

- Operator PR #66 audit verified both actual registered weight sizes/SHA256, registry identities and known templates, with empty system fields and native0.40.4. Zero inference/cloud/DB/messages and unchanged production. Integrity success does not qualify factual knowledge; no corrupt weight file observed.
- Review versioned native routes: Jinja Qwen syntax alone is not a bad template; native chat and Go/rendered paths coexist. No template/environment/runtime changes or model repair/download.
- Add eight fixed private Qwen controls: two Minecraft questions, English/German, normal chat/manual raw ChatML. Remove rich-prompt/schema/history/fact/version confounds while keeping sampling, seed, stops and output bound equal. Audit metadata drift fails before inference. Retain real shared admission, exact/unknown usage, unprivileged isolation, bounded client and verified cleanup/unload through the unchanged evaluator.
- Keep raw synthetic answers for human factual review, with no keyword verdict, automatic winner or activation. Add transport/usage/drift/cleanup tests and CI syntax/test coverage; update handoff. No game/app/assistant/backup change, restart, announcement or relaxation of the full quality and private-data gates.

## 2026-10-17 — Audit actual local model artifacts before further inference (PR #66)

- Actual PR #65 comparison completed with0/16 combined passing cases across both existing models and both formats. Qwen/Hermes fabricated basic Minecraft mechanics; Hermes also timed out/was slow. Known usage2189 input/557 output plus3 unknown attempts means exact totals NULL. No cloud fee, activation/messages or production change; cleanup/unload verified.
- Record that positive keyword matches are not factual verification: the wrong Hermes glass text matched terms but failed overall. No model is selected or qualified; keep broad mode OFF and preserve existing quality gates.
- Add a zero-inference read-only artifact audit: native version, fixed registration/source identities, bounded previously observed public templates with empty system fields, selected architecture/tokenizer metadata and actual registered GGUF SHA-256/size. Only two fixed blob paths are read, with symlink/size checks, internal90s reader timeout/110s outer cap and visible progress. No recursive scan, raw system text/config/credential dump, download/import/repair, DB call or model load/unload.
- Synthetic tests cover digest/size/source mismatch, timeouts, template/system withholding, bounded metadata, fixed command scope and production drift. Add CI test/syntax coverage and update handoff with observed comparison and next immutable audit.
- No app/game/assistant image/config changes, restart/recreation, backup action or native welcome. File-integrity success is not model-quality qualification; actual audit/template review remains pending.


## 2026-10-17 — Separate local model knowledge from output-format failures (PR #65)

- Operator PR #64 run passed routing and latency (warm median4.79s) and all private/native cases, but still hallucinated cow/sheep breeding and gave a vague party followup. Exact native usage1872 input/334 output across10 calls, no unknowns/cloud fees; production unchanged, cleanup/unload verified, broad mode OFF.
- Add a diagnostic-only comparison of already installed digest-pinned Qwen1.7B/Hermes3 8B, each with the current schema or plain output. Same questions, prompt, sampling, public hints and independent display guards; include held-out glass knowledge. Collect template marker/hash summaries without exposing model system text. Optional missing model skips explicitly, digest drift aborts, no download/import or implicit model change.
- Reuse the current isolated evaluator and actual read-only shared CPU coordinator per phase, preserving private-network read-only clients, exact/unknown metrics, cleanup/unload checks and unchanged-production evidence. Return diagnostic result/report path from the support evaluator without changing its full quality gate.
- Test all four model/format combinations, hallucination/unsafe/truncation distinctions, timeout usage, missing/different manifests, CPU-coordinator syntax and cleanup failure. Add CI coverage. Changelog/handoff distinguish diagnosis from deployment or universal mod knowledge.
- No production adapter, timeout, model, backup, Minecraft/container recreation, chat/welcome, privileged role or cloud change. Even a completed diagnostic cannot activate gameplay; actual comparison and later full adapter/role/driver qualification remain pending.


## 2026-10-17 — Current-subject local help and exact late usage (PR #64)

- Operator's actual PR #63 full-model run removed timeouts/truncation but still failed vague party followup, dinner/game and cow/other routing, plus warm median 8.202s against an unchanged 8s target. Exact native usage 3079 input/258 output for 15 attempts; cloud fee zero, no activation, production unchanged, cleanup/unload verified.
- Route recognized current Minecraft/mod subjects directly to one bounded local answer call. Unknown topics retain a German few-shot classifier; explicit real-world categories reject locally. Independent questions clear old context; only short dependent own-author followups may carry a prior turn/hint. Do not inherit OPaC notes on a new cow question.
- Ask for a supported action or specific menu clarification on how-to questions; strengthen followup evaluation and add unfamiliar game/other routing fixtures. Preserve all factual/security checks and latency thresholds; expected stage counts reflect the removed classifier work, with all actual calls accounted.
- Address PR #63 late review: distinguish correct denials from affirmative false claims in the synthetic factual gate, with adjacent-clause tests. Parse bounded complete native JSON before rejecting a late response, retaining exact token counts while rejecting delivery.
- Changelog/handoff record actual operator evidence and next pinned full check. No backup change, Minecraft restart/recreation, chat message, model download, cloud fallback or production activation. Actual candidate performance and restricted-role/driver qualification remain pending.


## 2026-10-17 — Compact grounded local Minecraft candidate (PR #63)

- Actual focused diagnostic identified a 22s timeout, inaccurate comparator guidance, truncated/repetitive party hallucinations and wrong off-topic routing; raw synthetic evidence remains on the operator server. Broad model mode stays OFF. Known usage 2133/370 plus one unknown call is not an exact total.
- Replace greedy decoding with Qwen3 author-recommended non-thinking sampling; separate a small game/other classifier from <=200-character grammar-constrained answers. Locally filter the complete public mod ID inventory to relevant IDs/hints. Keep one shared CPU lease, checked total budget, finite response sizes, per-stage accounting and independent forbidden-input/output checks; no retry or cloud fallback.
- Add factual public piston/comparator hints and repetition rejection. Let a qualified broad adapter handle initial general gameplay questions rather than guide-only fallback clarifications. Native stats/recipes/Carry On, addressed-only routing and bounded own-author context remain.
- Strengthen the full real-model gate with factual negative checks, cow/backpack questions, novel off-topic routing, expected stage counts and cold/warm/median latency thresholds. Focused diagnostic mode cannot activate anything. Local synthetic regression tests do not qualify real model performance.
- Update handoff with actual diagnostic and next full-model check. No production activation, model download, Minecraft restart/message or backup modification. Dedicated DB role/driver and assistant-only rollback qualification remain later requirements.


## 2026-10-17 — Diagnose rejected local Minecraft answers (PR #62)

- Operator confirms incremental backup installation at `[private release reference]`: one old cron paused, new 03:00 server-local schedule, engine SHA-256 `5ad872cef09c7a7599b06c8c3ae9baf5ed540f215aa8a32873fb551ebfc9466f`, no backup/game change/legacy deletion. First complete backup is still unverified; do not repeat installation or the old offline tar job.
- Actual Qwen general-help qualification with all 63 installed mod IDs failed at `[private release reference]`. Piston returned unavailable after about 22 seconds (timeout suspected; exact adapter reason was not captured); comparator/party/off-topic produced the generic unavailable reply; party followup was classified outside Minecraft. Claims and deterministic protection/Carry On routes passed. No cloud calls, production changes or activation; cleanup and unload verified. Exact token totals are unknown, not zero.
- Add isolated-harness native response observations and safe adapter rejection codes without changing runtime/model/prompt/limits/permissions. Capture bounded synthetic model content, completion/length reason, load/prefill/generation durations, prompt/schema sizes and actual usage. A read timeout keeps totals NULL while retaining separately labelled known usage and unknown-call count.
- Add explicit diagnostic-only mode for the four failed independent questions. Collecting evidence is distinct from model quality: even successful diagnostic fixtures cannot qualify activation. Maintain the same shared CPU lease, private fixed endpoint, synthetic-only inputs, unchanged-container/profile proof and verified unload. No backup, game message, service recreation, new model or cloud call.
- Seven diagnostic/parser/gate tests and nine existing adapter/context/policy tests pass locally, covering timeout, rejected truncation, unsafe raw output versus player reply, native timings, partial usage and activation-ineligible diagnostics. Update handoff with observed operator results. Actual detailed host evidence remains required before selecting a targeted prompt/model/runtime fix.

## 2026-10-17 — Broad local Minecraft/mod help candidate (PR #61)

- Add a separate opt-in Qwen 1.7B general-help adapter for addressed gameplay questions, rather than requiring a fixed topic keyword. Supply the complete bounded installed-mod ID inventory plus reviewed public Carry On/OPaC facts. Explain general Minecraft/mod topics and ask specific questions when details are uncertain; never imply universal mod accuracy or knowledge of actual claim owners/rights/limits.
- Keep only the same authenticated author's own last two model turns in bounded RAM for 180 seconds, isolated by source and author. Ordinary chat is ignored; native statistics/recipes/mod inventory clear model context. No channel transcript, private memory, cloud fallback, tools or command API. Preserve fresh deterministic statistics, reviewed Carry On answers and the recipe fast path ahead of the model.
- Enforce normalized command/console-output/seed/gamemode/cheating input and output boundaries independently of the model, including arbitrary slash commands, Unicode formatting and common German variants. Reject incomplete/unsafe/oversized/schema-invalid model answers; record real native usage even when rejected, retain unknown token counts as NULL, and never count local work as API fees. This private assistant ledger is not yet a web-dashboard integration.
- Add a separate composed real-model qualification under the actual shared PostgreSQL CPU lock: claims, parties, own followup, redstone and unrelated-topic routing; forbidden topics and missing recipes cannot call the model. Use only synthetic fixtures, no game messages/restarts/production activation or credentials in the isolated client. Unload weights and verify unchanged production afterwards. This does not retroactively qualify the old freeform recipe adapter or the future restricted DB role/driver.
- Address review: reject double-slash command forms; validate answer semantics separately from the structurally safe authenticated display name; preserve existing general-help context for troubleshooting followups instead of consuming them in a generic Carry On clarification. Whole-word query detection preserves general party/claim creation and joining questions.
- Address backup review: identify exact owned cron command/interpreter positions, preserving unrelated paths, redirections, environment settings and shell comments. Distinguish a copied staging tree from a verified Restic seed, validate the referenced snapshot, and retain initial-snapshot space budgeting plus a second space check after precopy before any game stop.
- Guard ongoing copy/Restic work against exhausting disk space, stopping at a 10 GiB reserve and recovering the same game if in the final phase. Test a real subprocess interruption with synthetic low-space evidence.
- Add a real-root temporary-file regression for setup dependency failure: the old backup entrypoint is held, originals/disable are preserved, and no game command or new cron is run.
- Nine local adapter/context/usage tests, three evaluation-gate tests and existing runtime/mod-help/dialogue/recipe tests pass. Broad model mode remains OFF on the operator host; actual model quality and dedicated-role/driver qualification are required before a service-only activation. PR #59 remains the observed active backend. Operator-run PR #60 backup installation and the first complete backup are still pending.

## 2026-10-17 — Bounded incremental 03:00 backup (PR #60)

- Record operator-confirmed PR #59 service-only deployment at `[private release reference]`; Minecraft and other services unchanged. Freeform knowledge remains disabled. Operator now requests broad local Minecraft/mod understanding, including claims and parties, while preserving independent command/seed/gamemode/cheating boundaries.
- Replace the known long-offline cron entrypoint with online rsync staging, a clean stopped final delta limited to 45 seconds, recovery of the same immutable container and encrypted deduplicated Restic format-2 snapshots after restart. Stop/start/health time is additional; no claim of a 45-second total outage. Preserve all world/player/mod data and hidden configuration, excluding only prior root backups/log and data logs/crash-reports/cache.
- Own a new private repository by its exact ID; keep 7 daily/4 weekly/2 monthly snapshots and at least the latest, prune only that repository weekly after a successful world-header restore probe. Never delete legacy archives or the interrupted tar. Full initial staging can be large and slow, but runs online. No writable-container-layer backup or zero-loss claim.
- Guard the installer with both release/backup locks, preserve original files/cron privately, hold the old offline entrypoint before dependency setup, comment only matching old cron lines and install one server-local 03:00 job. Signed distribution Restic/rsync tools run as CLI dependencies (BSD-2-Clause/GPL-3.0 respectively), without copying their code or upgrading existing packages. Installation does not run a backup or operate Minecraft. Guarded disable retains all data and does not reactivate the old offline job.
- Test actual rsync contents/exclusions, same-ID timeout recovery, changed repository/mount rejection, cron isolation, permissions and disable. CI additionally installs Restic and tests two real snapshots/deduplication/full synthetic restore of world/player/mod/config data. Actual host installation and first completed backup remain pending.

## 2026-10-17 — Grounded Carry On help and service-only update (PR #59)

- Operator confirms the repaired offline backup was cancelled after roughly 36 minutes; the same Minecraft container restarted and is healthy. Retain the partial snapshot.tar as unverified; never treat it as a completed backup. Do not rerun the long offline workflow or recreate Minecraft. The unknown writable-layer path, loader pin and native welcome/identity cutover remain held.
- Add reviewed Carry On pickup/placement guidance from the mod author’s instructions, gated on its installed mod ID. Recognize German spelling variants, separated verbs and common Swiss phrasing without requiring a mod name. Explain both empty hands/default sneak and right-click, ask useful troubleshooting questions and respect claim restrictions without commands. This is grounded fast-path help, not activation of the unqualified freeform model.
- Retain only a bounded, expiring topic enum per authenticated author and source in RAM for short hands/placement/failure followups. Clear it on unrelated/private requests and success; do not read ordinary chat or other users, persist prompts, relax greeting/privacy/output/rate/replay boundaries or reuse old statistics. Replace the repeated capabilities fallback with a targeted clarification.
- Add isolated signed-loopback HTTP qualification with synthetic fixtures and a guarded updater for only the existing standalone Vector service. Reuse its qualified image, data mounts, token and SQLite state. Validate original code/profile/runtime/ownership, preserve private rollback and update the installation manifest coherently. Check the unchanged Minecraft/other container starts and Compose hashes before/after; never stop/recreate the game, run a backup, call models/cloud or send a welcome.
- Address review: explicitly apply public source file/directory modes under the private umask, retain private evidence permissions, and keep installed-mod inventory questions ahead of Carry On interpretation.
- Twelve HTTP tests plus nine synthetic update/rollback/changed-state tests pass locally, along with existing runtime/dialogue/recipe checks. Add CI and update preferences/handoff. Actual isolated image qualification, operator deployment and public-channel observation remain pending.

## 2026-10-17 — Repair truncated Minecraft backup and retain recreation gate (PR #58)

- Operator reports the existing backup script is syntactically truncated; no completed backup was verified. The read-only cutover audit confirms the live data/world bind but blocks on one unreviewed writable-layer path; Fabric loader is not pinned. Keep the old integration deployment held.
- Add an operator-run, revision-pinned repair that preserves the broken original privately, parses all replacements before installation, refuses valid unrelated scripts/symlinks/unexpected permissions, supports guarded rollback and does not operate containers. Classify the private audit path without publishing arbitrary filenames or weakening the gate.
- Replace the backup entrypoint with a full-module Python implementation. Check live bind identity and free space before stopping; snapshot and compare the persistent server folder while stopped, restart the same original container in recovery, compress/test/check required members and publish an exclusive SHA-256 archive. Keep hidden configuration, old backups and unknown backup directories; exclude only backups and the changing root backup log. No retention deletion, container recreation, public messages or claim to include writable container-layer data.
- Address review findings: target stop/start/stat by immutable container ID, refuse extra mounts, settle ambiguous stop completion with bounded Docker wait before recovery, and retain a complete installed pair if post-publication fsync fails.
- Synthetic tests use real GNU tar/gzip for archive contents, comparison, checksums and retained files; simulate stop timeout, deferred signal cancellation, archive/source failure, replacement, stopped-game and health failure. Cover repair/idempotence/rollback/later edits/private diagnostics. Update CI and handoff. A real host backup, root-layer review, loader pin and native welcome qualification remain pending operator execution.

## 2026-10-17 — Pre-recreation persistence audit and operator-authorized native welcome (PR #57)

- Hold the supplied PR #56 deployment: operator has not run it and requests current persistence verification plus one additional native Vector welcome, 15 seconds after readiness. Record this narrow authorization separately; retain the old welcome marker and mandatory logo-pack choice. No backup or production change is claimed.
- Add a read-only host-bind/world/Compose/version/type/user/image/startup-options and writable-container-layer audit. Compare live container and host directory device/inodes, reject extra prospective tmpfs/secret/config/volume mounts and pending environment changes, and recheck final readiness. Refuse ambiguous/unpersisted data; keep unknown filenames private. Recheck stable host directory identities and report loader pin status without claiming zero risk or a verified backup.
- Add default-off session-bound operator welcome control. The operator-only arming helper checks healthy current ownership/readiness and atomically exposes a readable signal. The addon waits at least 15 monotonic seconds, schedules native Vector/head/avatar delivery, and durably claims its independent v2 event before sending. Existing/stale signals, repeat polls and unload/reload cannot cause automatic resend; capture the original worker, bridge and timer so callbacks cannot act on a replacement load. Recheck both final container snapshots before arming. No console command, fake user or inference.
- Add audit-before/after isolated qualification of the changed addon, with required native welcome test proof. Synthetic tests cover mount/version/destructive-option/root-layer boundaries, durable arming, delayed scheduled delivery, session/marker/unload/symlink handling and changed/failed qualification gates. Existing signed first/restart chat captures pass locally. Update CI and project handoff; actual host audit, new qualification/deployment and native greeting delivery remain pending.

## 2026-10-17 — Guarded combined Minecraft dialogue and identity update (PR #56)

- Operator's combined source qualification passed: both restart captures, extended statistics and linked-channel Discord boundaries, exact prepared logo assets, no production changes/model requests/messages. Reuse this evidence and captured JAR without another build.
- Add an operator-run updater for the existing pilot: scope-checked persistent game pack environment and immutable image pin, exact public PNG/ZIP HTTPS routes, matching backend/addon/config, coherent original ownership manifest and preserved token/SQLite/welcome marker. Operator explicitly chose mandatory logo-pack acceptance; game recreation is required.
- Check Nginx syntax and both origin/public-DNS HTTPS assets and app health before game downtime; retain seven other containers and app Compose. Validate fresh saved-data reads, private service/game health, new addon registration and applied pack settings after cutover. No app redeploy, separate Discord bot, inference, cloud request, console command or announcement.
- Add durable private before/after backups and guarded automatic/manual feature rollback, including failed recreation recovery. Record/recheck assistant container ID, image, user, installation/Compose labels and read-only code mount before either container is stopped; refuse an unrelated replacement without downtime. Reject unknown changes and unsupported configuration layouts; completed repeats verify without restarting. Restore the feature before optional original pilot removal.
- Test successful/repeated update and rollback, stopped/restarting/unhealthy repeat rejection, replaced-assistant rollback refusal, early/late failures, evidence/source drift, scope/backup guards, quoted Nginx structure, canonical Compose restrictions and resource-key restoration. Update CI, handoff and operator pack preference. Actual deployment, Discord gateway input and client logo/avatar remain pending operator execution/observation.

## 2026-10-17 — Natural statistics and existing-channel Discord questions (PR #55)

- Operator confirms real addressed Minecraft statistics/recipe replies and Discord relay delivery. The new logo qualification passed without activation; retain its assets/evidence and delivered welcome marker.
- Recognize natural death/rank questions and plural record-holder requests; include shared competition ranks and preserve exact/unknown-player checks. Read saved counters freshly. Translate Amboss and Eisenblock.
- Add bounded block usage/mining queries; only live registered BlockItem IDs classify usage counters, excluding tools. Label usages honestly rather than claiming a complete placement ledger. Missing registry/incomplete data fail explicitly.
- Add opt-in human Discord input through the existing linked-channel integration hook, without another bot. Reject other channels, DMs, bots, webhooks, ordinary chat and repeated events; preserve normal relay, authenticated author names and durable account/event limits. No model/cloud fallback.
- Expand isolated capture and semantic tests for Discord boundaries, restart replay, registry transport, natural questions, rank ties and fresh block counts. Keep prompt/reply limits while allowing bounded signed public registry metadata.
- Fix the later PR #54 review's manifest-snapshot race; exercise the qualifier orchestration against changed production and failed/incomplete captures. These changes are source/qualification only; matching service/addon/identity deployment and actual Discord-input/client-head verification remain pending.

## 2026-10-17 — Vector player-style name and local logo assets (PR #54)

- Operator confirms the pilot installed successfully and the single welcome appeared in both chats. Preserve its durable marker. Diagnostics confirm active Discord webhook, no avatar and no existing server resource pack.
- Render <Vector> directly through the addon, with an optional native player-head object using a fixed local pack texture. Retain plain-name output until pack availability. Keep per-message webhook name/avatar scoped to Vector, without fake login, commands, profile lookup or global server/bot renaming.
- Render the existing SVG offline into a PNG avatar and deterministic 26.2 logo-only resource pack. Six image/UV/archive/version/path checks pass. Addon compiles against the installed nested API; its native object survives serialization. Local signed HTTP first/restart/limits/introduction checks pass.
- Add isolated operator qualification: verify completed installation, marker, exact game/resource format, webhook and site hints; compile/capture with pinned isolated runtime and prepare private assets. Verify production unchanged, with no restart, models/cloud calls or real messages.
- Production identity installation, public HTTPS assets, pack delivery and actual client/avatar rendering remain pending operator qualification and a separate guarded update. Update handoff and operator preferences with observed state and next steps.

## 2026-10-17 — Operator-requested welcome before manual chat testing (PR #53)

- Operator reports Minecraft restarted but no introduction appeared. The pilot intentionally left introductions disabled; installation success/real routing is not independently confirmed without its manifest/output.
- Apply the operator explicit new timing preference: prepare one fixed short Minecraft welcome before manual tests, without another restart. Verify completed installation ownership/profile/file hashes and healthy service/game first; stop if installation failed.
- Submit only the closed welcome text through the existing game console helper and preserve the addon's durable introduction-v1.attempted marker before submission. No shell, model path, configurable user command or automatic retry. The marker remains on failure/uncertain delivery and prevents a later addon introduction too.
- Read relay configuration locally and report only boolean hints, without exporting tokens/config; report console acceptance separately from actual delivery. The existing relay may forward the announcement depending on configuration; no Discord delivery is claimed.
- Four offline fixed-command/marker/failure/path tests pass. Actual welcome submission is pending operator execution. Update operator preferences and project handoff; no service/app rebuild or restart.


## 2026-10-17 — Qualified installed recipe catalog and guarded Minecraft pilot installer (PR #52)

- Operator installed-base HTTP qualification passed: 975 supported recipes, 610 unsupported entries explicitly excluded, actual three-recipe requests around 47–50 ms in this one run, zero model/cloud calls or messages, cleanup and unchanged production verified. Effective modded recipes remain unqualified.
- Prepare a guarded standalone private assistant service using the existing pinned Python image, exact qualified catalog/source and captured unchanged addon artifact. No app build/release or edits to either existing Compose file. Read-only mounts include only approved saved stats/usercache, public mod IDs, base catalog, service code and its HMAC token; only new SQLite state is writable.
- The operator-run installer checks existing evidence/source hashes, fresh real-data access as the game UID, private health, explicit game version pin, unchanged game JAR, existing mount/network and integration hash before restarting only Minecraft gracefully. It requires addon registration plus game readiness, retains other service identities/profile hashes and leaves introduction/freeform models disabled.
- Persist exclusive file ownership hashes and a guarded rollback, refuse unexpected files/services/drift, preserve state/evidence. Failures before cutover do not restart Minecraft; after cutover the rollback restarts only Minecraft. Real game/Discord delivery and eventual once-only introduction remain pending operator testing.
- Seven offline profile/file/rollback/private-health regressions pass, including a real signed ignored HTTP probe without rate events. Actual installation has not been executed; this source PR does not claim production activation.


## 2026-10-17 — Installed vanilla recipe answers and isolated HTTP qualification (PR #51)

- Operator v3 inventory passed: 357 installed archives examined, 9,987 recipe documents, 153 identical archives skipped, 180,452 entries inspected, production unchanged, zero model/cloud calls/messages. It also found historical 1.21.4 cache assets; inventory success does not establish active recipe precedence.
- Build a bounded supported crafting catalog only from the observed 26.2 game JAR, checking its full SHA-256 and embedded version. Reject duplicate resources, unsafe/oversized inputs and unknown conditions; retain unsupported counts. No game assets or operator report are committed.
- Add deterministic shaped/shapeless quantities, alternatives and row formatting with an explicit Minecraft 26.2 base-recipe label and unverified mod-adjustment notice. Recipes are routed before the optional model in the configured assistant; the service entrypoint always supplies a recipe handler so missing catalogs cannot send recipes to Qwen. The existing Assistant constructor remains backwards compatible for old callers.
- Add operator-run isolated catalog/private-HMAC-HTTP qualification, retaining a private candidate catalog. The pinned unprivileged container has no external network or credentials; it checks three recipes, signature/private-topic boundaries, ignored ordinary chat, missing catalog, replay/rate limits and fresh synthetic statistics with no model calls or real chat messages.
- Replace the growing historical handoff with a compact current-state runbook, preserving an immutable Git history link, operator instructions, live baseline, open issues and qualification boundaries.
- Local checks: nine parser/catalog/routing tests, two real HTTP harness tests, eleven existing runtime tests and four legacy model-evaluation tests pass. The three observed public base documents also format correctly locally. Actual server catalog/HTTP qualification and final Minecraft installation/relay delivery remain pending. No app rebuild/release or announcement is performed by this change.


## 2026-10-17 — Deduplicate recipe archives and retain partial evidence (PR #50)

- Operator v2 preflight reached 11,430 recipe documents and 200,093 archive entries, then stopped at the global metadata cap while production remained unchanged. Candidate/effective recipe coverage was not established.
- Hash installed archives before traversal and scan identical root/nested archive content only once, retaining SHA-256 provenance aliases for cached/copied dependencies. Conflicting content is still inspected separately; identical content does not establish active pack order.
- Separate the unchanged 200,000-entry per-archive cap from a 1,000,000-entry global unique-traversal budget and a 50,000-recipe budget. Retain depth, live-payload, total-read/hash, time, file/path and duplicate-member guards.
- Save already captured target variants, source hashes, schemas, versions and work counters after a later failure. Missing targets and incomplete traversal remain explicit and cannot pass candidate/effective qualification, even if all three target recipes were found.
- Fifteen synthetic regressions pass, including content-cache aliases, independent metadata/recipe limits and a real private failure report that retains targets without promoting incomplete coverage. Installed v3 inventory, effective recipe precedence and actual channel integration remain pending; no app release, model call, restart or announcement.


## 2026-10-17 — Bounded deeper recipe archives and useful failure evidence (PR #49)

- Operator recipe preflight stopped at NESTING_LIMIT, with production unchanged and no activation. The original two-level archive traversal was insufficient; installed recipe coverage is still unknown.
- Support up to eight nested JAR levels with an additional 256 MiB budget for simultaneously retained inflated archive payloads. Retain existing total-read, entry, archive, time and path guards. Over-budget inputs still fail instead of silently skipping resources.
- Save bounded progress counters and the current public archive/member/depth on failed and successful runs, so a limit failure identifies the resource without exporting configuration or player data.
- Eleven offline regressions pass, including a four-level dependency bundle, pre-decompression live-budget rejection, cleanup after an invalid child archive and the retained depth/deadline guards. Actual installed-archive traversal remains pending; no app rebuild/release, inference or Minecraft activation is involved.


## 2026-10-17 — Observed fresh-statistics deployment and installed recipe preflight (PR #48)

- Record operator-confirmed native privacy qualification and successful fe12d19 / image 8d4645d production release, including all-interface and actual Nginx HTTPS health. Preserve the new release/rollback/profile baseline and HOSTNAME=0.0.0.0; no repeated build/release is requested.
- Actual synthetic recipe diagnostics confirm factual hallucinations from Qwen 1.7B in all three failed crafting cases. Keep knowledge disabled; do not relax the gate. Three local calls, zero cloud/API fees, cleanup/unload verified; no Minecraft activation or announcement.
- Add a bounded operator-run inventory of installed public game/mod recipe assets, including nested JARs, version evidence, exact target documents, hashes, variants and schemas. Ignore player/log files and configuration content (Compose files are hashed only), reject unsafe or oversized members, and never treat candidate assets as verified effective recipes. No inference, game restart, messages or production configuration changes.
- Eight offline archive/precedence-boundary tests pass with synthetic assets; actual installed-resource inventory and final recipe/runtime/channel qualification remain pending.


## 2026-10-17 — Qualified fresh-statistics release and recipe diagnostics (PR #47)

- Operator app staging passed at b9d34da3f07b91f27de1800aba214d507922b760, including new completed-versus-in-flight statistics dedup and native record-holder/refresh followups. Exact qualified image: sha256:8d4645d72630974981ceb9985332473d41f03563b9a8f52a2b808f63387ec9cd. Production remained unchanged; no new app build is requested for release.
- The real local Qwen knowledge test failed the three crafting fixtures while piston/comparator/repeater and all five deterministic policy/mod cases passed. Six local calls used 1017 input and 425 output tokens; API fees/cloud calls were zero, cleanup/unload passed and production remained unchanged. The old report did not capture the answers, so factual errors versus wording/parser/output-filter rejection remain unresolved. Knowledge remains disabled.
- Prepare a guarded reuse-image native privacy qualification and app-only release against the repaired HOSTNAME/Compose baseline, with fresh backups and rollback. Strengthen health for every app IPv4/loopback interface and the actual host Nginx HTTPS response, validating/reloading Nginx only if ingress requires it. Retain the seven other production container identities and preserve the repaired listener setting.
- Add a bounded three-recipe diagnostic mode with actual synthetic model/adapter responses, termination and rejection metadata. Passing this subset cannot qualify full Minecraft knowledge or production DB privileges. No game install, introduction or cloud call is performed by that diagnostic.
- Local verification: nine release/fingerprint/ingress/pipeline regressions and four evaluation-harness regressions pass, plus syntax checks. Operator native privacy requalification, app release and recipe diagnostic remain pending.

## 2026-10-17 — Fresh complete statistics and Minecraft qualification (PR #46)

- Recognize uninterrupted native statistics followups including all record holders and explicit refresh. Resolve intent from user requests rather than assistant facts; topic switches and mixed/export/admin tasks retain their normal routes. Every completed native statistics request now rereads the fixed sources; completed native jobs are excluded from the short completion replay while queued/running retries still share their job. Ordinary completion dedup remains intact.
- Return all five record categories through the deterministic reader with exact ties and a fresh read timestamp. Explain that newly performed game actions appear only after Minecraft saves its statistics files. Include read provenance in local job metadata.
- Add the equivalent complete record-holder response to the private Minecraft service. Release the service computation slot before publishing its HTTP response so an immediately following request is not spuriously busy.
- Add an operator staging wrapper pinned to the repaired listener/Compose baseline, testing completed-versus-in-flight job reuse and native followup routing in a disposable app/database. Prepare real local Qwen knowledge qualification using the actual bounded adapter and policy, synthetic Minecraft fixtures, shared production read-only advisory-lock admission, separate temporary client and reported native usage. No cloud calls, game installation or introduction are performed by qualification; the dedicated production DB role remains a separate unmet gate.
- Local verification: 31 focused Node tests, 11 Minecraft runtime/HTTP tests and three knowledge-evaluation tests pass, plus syntax checks and a new actual-PostgreSQL duplicate policy regression prepared for CI. Real operator staging/model qualification and production release remain pending.

## 2026-10-17 — Operator-confirmed listener and Nginx repair (PR #45)

- The operator completed PR #44 repair at bc52a8f38098eea0e2123f74cc0c8c8392358bed. Runner reported LISTENER FIX SUCCEEDED and SUCCESS: every app IPv4/loopback interface and the host Nginx HTTPS health route passed. The persistent app HOSTNAME is now 0.0.0.0.
- Evidence: [private operating path], containing result.json and original/candidate Compose files. App source/image are unchanged; other production containers were retained; no model request was made. Future release guards must use this repaired Compose baseline and preserve its listener setting. Do not rerun the older exact-baseline repair or bypass historical rollback guards.
- Update the handoff from unresolved 502 to confirmed local ingress recovery, while keeping remote browser rendering, completed statistics jobs and provider execution as pending checks. Documentation only; no new server mutation or model call.

## 2026-10-17 — Repair app binding across private networks (PR #44)

- Operator post-release evidence shows the app running without OOM/restarts but listening only on 172.25.0.3:3000, with health unreachable on loopback and the other two app network addresses; host Nginx returns 502. The prior health gate accepted any single interface, so successful internal release health did not prove proxy reachability.
- Add an operator-run guarded repair that changes only app.environment.HOSTNAME to 0.0.0.0, using the same qualified image/source. Require the confirmed deployed source/image/Compose baseline, idle jobs, unchanged other services and exact canonical candidate equality; save the original Compose before app recreation. Validate all IPv4 app interfaces and the real host Nginx HTTPS health route after a tested Nginx reload.
- Three offline mutation/ambiguity and guarded repair/rollback tests plus Python syntax pass. No server repair has yet been executed or observed; the public outage remains unresolved pending operator output. The Minecraft addon remains uninstalled.

## 2026-10-17 — Operator-confirmed chat controls deployment (PR #43)

- The operator completed native privacy qualification at ops revision c973ac2535582038c52ba5881ef67c4e5e7fb267. Normal and detector-outage cases passed, including explicit off, default-on blocking, encrypted placeholder round trips and local-only project enforcement. Cleanup and unchanged production fingerprints passed; 11 synthetic jobs remained queued and unexecuted, with no cloud calls or API fees.
- The guarded app release succeeded at [private release reference]: commit 2f5b8e866f613b336ed24b5242dc93e535c985bc, image sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d. Fresh backups, source synchronization, persistent Compose pin and app health passed. Preserve that release directory and its guarded rollback; do not rerun the superseded release.
- API report: [private release reference]/result.json. Observed synthetic review timings were 8732 ms cold, 205 ms follow-up and 11 ms cached. Real browser UI, completed production statistics jobs and provider execution remain separate pending checks. Minecraft integration and its introduction remain inactive.
- Documentation records the operator output only; no production mutation or new model request is performed by this documentation change.

## 2026-10-17 — Guarded chat controls release qualification (PR #42)

- Operator evidence now confirms PR #41's actual Host Agent read and isolated application staging at e8b6b6e690aa893e3fc0a0641e07261c0414ffc6: 50 complete saved statistics files; Auto/Local/Normal and privacy-off queued-job checks passed. Production was unchanged, with no model/cloud calls or exported player records.
- Reuse the exact observed staging image sha256:5a2ee0f4b1b169114da5608a8a33f0ca08ce00c4016873208fa1d5518901f87d. A new operator pipeline qualifies native privacy on/off, original restoration and local-only routing against that image, including detector outage. No rebuild or provider call is requested.
- API success reports are now published only after temporary-resource cleanup and a final fingerprint of eight production containers and both Compose files. The app-only release requires the completed runtime baseline, actual read evidence and exact new API report, retaining fresh backups, image/source/Compose guards and rollback. Minecraft, worker, runner, databases and local inference/privacy services are retained.
- Offline verification: seven new release-gate/pipeline regressions, eight existing evaluator regressions, shell/Python/Node syntax and preparation against the actual archived helper snapshots passed. Operator native API qualification, deployment, browser UI and real provider execution remain unverified until their outputs are observed.

## 2026-10-17 Chat controls and local server statistics (#41)

Replace the web chat's always-visible mode tabs with a compact active-mode menu and add Auto as the default. Share the accessible controls with project chat. Add an explicit per-request privacy switch, default on: switching off skips prompt, provider and tool-evidence scans/replacement for that request using an authenticated encrypted job policy. Reject malformed preferences and keep login, project/server permissions, local-only project routing and budget boundaries independent of that switch. Earlier placeholders from the same conversation are restored locally under the explicit off choice so historical context stays coherent. Local execution no longer depends on the privacy feature flag.

Recognize German own-server inspection inflections and Minecraft statistics without the Minecraft keyword, including the common German record spelling error. Auto uses fixed read-only Host Agent sources for supported Minecraft statistics, otherwise retains existing cloud/tool routing and chooses existing modes without an extra classifier call. Native calculation covers five categories, exact player values, competition ranks, positive records, ties and saved-file read provenance. Incomplete, unnamed, invalid or unknown-player data fails without invented rankings or cloud fallback. Explicit Normal retains existing server tools. Unsupported local tool tasks give a useful mode choice instead of calling the text model. German research/analysis signals improve Auto selection.

Observed locally: 71 Node regressions across routing, actual request/enqueue and local execution, privacy policy/isolation, provider/tool masking, usage and rankings; two Python diagnostic regressions. Review regressions keep the dropdown outside clipped panels with viewport placement, stop player follow-ups at a real topic change, leave compound/conceptual requests to the appropriate route, separate original task text from retrieved evidence, reject cached players with no statistics file and reject explicit null counters. Prepare a pinned operator-only direct Host Agent read check that exports metadata only, plus isolated application staging against the confirmed runtime image. Operator execution and deployment of this change remain pending. No schema/dependency change, production restart, paid request or real chat send during development.

Record the operator passed captured Minecraft addon/API test from PR #40 at 5f5eb4185480ea9ea095d37ff1cdb273498f2031: both phases, restart limits, introduction replay and cleanup passed; production Compose/container identities/integration unchanged. Real Minecraft callback/Discord delivery, model knowledge and installation remain pending.

## 2026-10-16 Captured Minecraft addon qualification (#40)

Operator preflight confirms the exact installed 26.2/3.2.1 integration hash/API, complete 50-file saved-stat coverage, 63 readable mod metadata IDs and qualified local Qwen; Minecraft and inference use separate networks, and the host has no compiler. Production configuration/container identities stayed unchanged.

Factor only the host scheduling/identity/delivery boundary into a Bridge interface; retain actual addon greeting, signed transport, output and introduction logic. Add a synthetic captured addon-to-real-HTTP flow with temporary service restart, persistent rate limits and no repeated captured introduction. Local first/restart phases, existing 19 Python tests, Java checks and five new evaluator regressions pass. Extend CI to Java 17 and 25. Reproduce and fix the completion handoff race that silently dropped an immediate next question: admit one active HTTP request and one bounded completion handoff, reopening admission before publishing. The delayed-delivery regression fails before the fix and passes after it.

Prepare operator-run isolated container qualification with an exact official JDK image, installed nested API and existing qualified native Python image. Use an internal throwaway network, no published ports/production networks/credentials, unprivileged read-only containers, bounded resources, synthetic state and ownership-checked cleanup. No host package installation, production restart, model/cloud call or real message is performed. Operator Docker execution, real game/Discord delivery and knowledge/role/usage qualification remain pending; captured delivery is not proof of real-channel integration. Update project handoff and next command accordingly. Require every qualification-completion flag before reporting success, including interrupted runs. Retain bounded partial/completed step logs on timeouts/failures, distinguish confirmed Docker absence from daemon/permission failures, and keep uncertain cleanup closed. Nine evaluator regressions pass locally. Rename a public dependency-checksum constant to avoid a secret-scanner false positive without exclusions or weakening hash verification.

## 2026-10-16 Minecraft chat bridge components (#39)

Implement the operator-requested Minecraft-only input addon using the existing Discord Integration 3.2.1 bridge and its configured output channel; no separate Discord listener. Verify the official 26.2 source and actual public release hash/nested API packaging, compile against that exact API, and preserve normal chat. Add bounded asynchronous signed private requests with an explicit whole-response deadline and cancellation of late body subscriptions, server-thread identity/delivery, persistent hashed rate/replay state, deterministic saved statistics and disabled optional local knowledge using the shared CPU slot. Keep addon/introduction/knowledge inactive until operator qualification; persist an at-most-once introduction attempt rather than claiming acknowledged delivery.

Nine new Python runtime/actual HTTP tests pass locally, alongside Java HMAC, output, response-limit and durable introduction-claim checks. Add them to CI with the existing ten foundation tests. Prepare a read-only operator preflight for installed JAR/network/mount/stat coverage/model availability. No production configuration/database changed, model inference performed or message sent. Real-game/relay, private service packaging, restricted DB role, model quality/usage, custom Minecraft head, isolated operator staging and guarded installation remain pending. Update operator preferences and handoff with the Minecraft-only input scope and Discord-origin hook limitation.

## 2026-10-16 Runtime deployment confirmation (#36)

Record the operator read-only confirmation that the qualified runtime release is already deployed. Running image, release status/commit/image, active Compose bytes and source tree hash match. App is running with no OOM; diagnostic left Compose unchanged. Update the project handoff and final PR merge ledger. No restart, model request, new cutover or fresh HTTP health check is performed by this documentation update.

## 2026-10-16 Runtime release and continuation review (#36, #37)

Prepare the guarded release of operator-qualified runtime revision 8611082 and identical merged tree 60adca9, image c33a1b8. Operator staging and enabled native privacy API checks passed without executing synthetic jobs or calling a cloud provider. The latest operator release attempt stopped before deployment because the old composer profile no longer matches. The initial read-only comparison narrowed the drift to the app image. A subsequent operator diagnostic confirmed that runtime release [private release reference] was already deployed, with matching qualified commit/image, active Compose bytes and current source tree hash. The app is running without OOM. The repeated invocation correctly stopped at the old-profile guard; no further cutover is needed. Preserve the guard and rollback rather than rerunning a cutover blindly.

Review the four open PRs, record composer deployment evidence in #33 and the exact foundation scope/CI coverage in #34. Close empty #37: its description claimed changes absent from its zero-file initial-plan commit; carry those review tasks forward as unimplemented. Add a durable project handoff and operator preferences, required from AGENTS.md, so continuations retain instructions, pinned evidence, pending defects and Minecraft integration boundaries. Repository merges do not activate the bot or establish current server deployment.

## 2026-10-16 Runtime follow-up fixes

Limit Minecraft player continuation to standalone short follow-ups, including reversible placeholders. Prevent the local text-only executor from generating unsupported live-state answers before inference. Clarify that an additional privacy approval blocks new tool evidence, not the already submitted prompt. Targeted local regressions and operator staging/native API qualification passed; production deployment of commit 60adca9 and image c33a1b8 is confirmed by the matching completed release record, current source and Compose. Fresh real-provider/UI behavior remains to be verified. This does not yet add local server data access or interactive mid-job consent.

2026-10-16 — Privacy composer follow-up (#32): reject contextual contact labels misclassified as people, preserve ambiguous names and credential types, and retain the real API preview assertion. All 36 targeted local Node tests pass. Native server retest remains pending.

This changelog documents repository changes by date, with commit and pull
request identifiers when available. Entries are listed newest first.
Production deployments are tracked separately.

## 2026-10-16 Minecraft assistant foundation (#34)

Add a bounded read-only saved-statistics collector, deterministic rankings with ties and coverage checks, greeting-only admission, canonical-event deduplication, and three-per-user/twelve-global requests per minute. Ten synthetic Python tests pass locally and now run in Application CI. Prepare an emoji-free introduction. Chat/model integration, topic/output restrictions, durable delivery, operator-data qualification and production deployment remain pending. These modules do not yet read production files, invoke a model or send messages.

## 2026-10-16

### Compact privacy review beside the composer (#32)

- Show an immediate local checking indicator with elapsed seconds and a small accessible review card above the chat/project input. Remove the modal backdrop and eyebrow, simplify actions and preview labels, and keep fully local requests quiet. Test explicit consent, cancellation, stale scopes, duplicate sends and progress cleanup.
- Display only the current message in the default preview; separate context findings in a collapsed group while still protecting all included history, attachments and project retrieval. Batch uncached text segments in one native scan and reuse exact per-account successful results for at most five minutes with bounded in-memory storage. Changed context and other accounts rescan; cached work adds no fabricated encoder/API usage.
- Detect bare credential-shaped password values, explicit lowercase usernames and separate first-name references. Reject pronoun/code-heading false positives, trim Markdown edges on new person findings and respect person/username word boundaries. Preserve encrypted consent/vault handling and block failures before queue writes. Use synthetic regressions rather than the operator private prompt values.
- Local verification passes 38 Node tests and 8 deployment evaluator tests. Expanded operator qualification covers current-only previews, natural reset credentials, masked queued context, cache accounting and fresh-input outage blocking. The initial branch commit passes production build and CI. Construct dummy PEM markers only at test runtime to avoid a source-scanner false positive without excluding any files or rules; keep redacted scan diagnostics visible. Final CI, operator API/UI qualification and deployment remain pending; native service code/model weights are unchanged.

### Privacy release preparation after enabled API qualification (#31)

- Operator source/image release ba30c82 completed with healthy app and backups; privacy activation stopped before changing production Compose. Operator read-only diagnostics prove all four app mount definitions match exactly when order is ignored. Normalize only app mount ordering while preserving every mount field and rejecting duplicate targets. Resume an incomplete preparation only after exact qualified Git-byte, root ownership, mode, file type, link count and directory-content checks; preserve the private token without overwrite. All 16 offline release/profile/rollback/resume tests pass. Native activation retry remains pending.
- Add the operator-run guarded app release and separate private NER activation/feature rollback using the inspected archived helpers. Pin the qualified app/model images and tested/merged trees, preserve existing local workers and all other container identities, retain encrypted token access through read-only bind mounts, validate the full canonical Compose delta, and inspect actual runtime isolation/authenticated sleeping health without inference. Guard rollback against changed source, Compose, images or service ownership. Eleven offline release/profile/rollback regressions pass; generated YAML additionally parses and preserves all unrelated fields locally. Operator production execution remains pending.
- Operator pipeline at a20b9a6 passed the rebuilt staging image, 75 tests and the full privacy-enabled real app/native service/disposable PostgreSQL qualification, including the previously failing project metadata assertion. All 13 normal/outage checks passed. Six synthetic jobs remained queued; none executed, no cloud model was called, temporary resources were removed and production stayed unchanged. Preserve bounded synthetic evaluation evidence. Feature PR #30 merged as ba30c82 after all observed gates and CI passed.
- Prepare a read-only production release inventory using the existing archived helper factory. Report only selected release/profile hashes and flags, plus active helper program definitions without resolved Compose/environment values. No helper main/rollback is executed, no restart or model request occurs, and production activation remains pending. The archived release implementation exists only on the operator server, so its exact active behavior must be inspected before adapting source/image release and rollback around the already enabled local-worker profile.

### Project job metadata privacy boundary (#30)

- Operator API qualification at ff11044 reached the project-job assertion after earlier consent/local/history/upload/image checks, then correctly stopped because the durable privacy finding metadata still contained the original email. Reproduce the failure with the actual project route in a focused regression. Store placeholders for noncredential finding displays, full bullets for credentials (no prefixes/suffixes), and apply the confirmed privacy plan to retrieved filenames. Keep the pre-send local consent display and the full queued-payload expectations intact.
- Add field-path-only diagnostics to the synthetic API harness so future failures identify the metadata boundary without echoing private values. A new build/staging run is required for the runtime fix. Allow the API evaluator to receive a validated newly staged revision/image, retain the source-equality gate and bind native qualification to its independently observed b916048 report. The old app image is rejected when runtime source differs; native weights and all 32-case/API expectations remain unchanged. New staging and actual API retry remain pending; production remains inactive.

### Application-user API test dependency access (#30)

- Operator privacy-enabled API setup at ade4ff07 stopped before connecting to the app because the test client used UID 65534 while the image's application packages are owned by UID/GID 1001. The app itself started normally. Run this dependency-loading client as the same unprivileged application identity; retain the native service's separate UID 65534, read-only filesystems and existing resource/network limits. Do not modify image permissions or run the client as root.
- Preflight package.json, the actual pg Client export and the mounted API harness as UID/GID 1001 before the test begins. Record only bounded stage/error codes on failure and add client-identity/preflight regressions. Existing images, 32-case native qualification, source equality checks and API expectations remain unchanged. Real privacy-enabled API retry remains pending; no production activation occurred.

### Privacy-enabled application API qualification (#30)

- Operator retry at b916048 passed the private native HTTP service's 32 cases, consent/tool/runtime tests, idle unload/fresh wake, auth/limits and outage blocking. Operator app staging also passed its build, 74 tests and authenticated chat/file/project/server checks with privacy still disabled. Preserve bounded evidence separately; production source/configuration and running services stayed unchanged.
- Add a final operator-run qualification of the actual privacy-enabled built app, pinned native service and a fresh temporary PostgreSQL database. Exercise real login, review-before-chat/job-writes, account/request-bound confirmation, masked jobs, encrypted vault, response restoration with a synthetic assistant fixture, explicit unchanged send, quiet local requests, history, uploads, image limitations, project retrieval/access/local-only routing, encoder ledger metadata and outage blocking. Queue only synthetic jobs; start no worker or cloud provider. Reuse the observed app image only if Git proves all runtime/build sources still match the staged revision. No rebuild, production activation or production DB data writes are included. Docker/real-API execution of this new harness remains pending.

### Unprivileged privacy evaluation mount access (#30)

- Operator service qualification at 28bb9de stopped before running integration.mjs: the root runner's 0077 umask changed the requested 0755 input directory to 0700, preventing UID 65534 from traversing its read-only bind mount. Reproduce the restrictive-umask result, explicitly set only the synthetic/code mount root to 0755 and leave the release parent private. Add restrictive-umask and safe preflight-error regressions; actual unprivileged container access is checked by the operator-run preflight.
- Before starting the model service, verify all required scripts, fixtures and the synthetic token through the exact read-only client mounts as UID 65534. Report bounded error code/path metadata, retain container resource/auth/network limits and reuse the same qualified image and 32-case fixtures. Docker retry and app staging remain pending; the failed setup is not a model-quality failure or production activation.

### Private NER service and application adapter (#30)

- Operator server qualification at f7b5bb4 passed all 32 unchanged synthetic cases, including the previously missed surname; preserve compact evidence in docs/evaluations/privacy-ner-context-server-20261016.json. Short warm scans took 0.12–0.21 seconds, long fixtures up to 4.08 seconds, model load 9.596 seconds and peak RSS 2,816,296 KiB. No cloud requests, ledger writes or production activation occurred.
- Replace the application's unqualified generative privacy detector with the bounded, exact-span NER HTTP adapter. Keep existing consent, vault, authorization, provider/tool guards and quiet fully-local path. Record encoder text subwords as explicitly separate local metadata with zero API fees and no fabricated generative tokens. Preserve the earlier Qwen/Hermes comparison as an independent historical benchmark.
- Add an authenticated private service whose parent stays lightweight and whose model child loads on demand, exits after idle, and restarts cold. Reject excess input/concurrency and terminate a failed/timed-out child; no cloud fallback. Add client, HTTP/auth, failure, timeout and lifecycle tests plus an operator-run isolated 32-case service/runtime evaluation using the exact observed image, no downloads, no published ports and checked cleanup. Actual pinned-model local HTTP tests pass all 32 cases plus consent/tool/idle/wake checks; preserve bounded local evidence in docs/evaluations/privacy-ner-service-local-20261016.json. Real Docker service qualification and isolated application staging remain pending; no production installation or feature activation is included.

### Nested name spans and focused context verification (#30)

- Operator qualification at 2242f063 passed 27/28 cases; the long end-of-text case preserved only the first name and left its surname unprotected. Keep the original expected full name and the production gate. Reproduce the issue with the actual model locally: flat decoding suppresses an overlapping complete name and long surrounding text can weaken that name even with nested decoding. Retain nested exact-source spans at the unchanged 0.35 threshold and add at most 32 non-recursive original-sentence/neighborhood rechecks around detected people in multi-chunk inputs. Preserve all primary findings and word/subword bounds; count all recheck text in the explicitly labeled local tokenizer metrics. Reuse the model’s existing tokenizer rather than constructing it twice.
- All 32 actual-model local cases pass (the unchanged 28 plus four independent name-position/software controls); evidence is stored in docs/evaluations/privacy-ner-context-local-20261016.json. Add focused-window, nested-name retention, recheck-budget and token-accounting regressions. This is local evidence only; operator rerun, service/app integration and production activation remain pending.

### Bounded local privacy context qualification (#30)

- Operator retry at 7cedc0a confirmed the 0600-to-0444 public-weight fix and passed all 16 offline server cases. Warm short-case times were about 0.12–0.16 seconds, load 5.813 seconds and peak RSS 2,815,740 KiB; production stayed unchanged with no cloud calls or ledger writes. Preserve the observed pilot image for reuse.
- Add a separately qualified Python PERSON backend with complete splitter coverage, at most 64 words/192 raw-text subwords per chunk, 12-word overlap and strict exact-source spans. Reject omitted text, oversized words, oversized contexts and excessive chunk counts rather than truncating. Extend the unchanged 16 cases with eight synthetic credential checks and four long/Unicode/boundary controls, using the existing offline image without downloads. Record raw-text tokenizer counts with overlap explicitly; these are not provider billing totals. Extended actual-model qualification and app integration remain pending.
- Prevent a credential from appearing in another overlapping finding’s preview, including URL passwords recognized inside an email-shaped value. Recognize spaced API/access-token labels and quoted password phrases introduced by German/English verbs. Promote enclosing mappings and their saved aliases to the credential classification without altering ciphertext or reversibility; add regressions.

### Offline privacy pilot access recovery (#30)

- Operator server setup at 8126c50 completed, but unprivileged inference could not open converted model.safetensors. Locally reproduce safetensors 0.8.0 creating a 0600 file. Explicitly grant read-only access to this public weight asset, retain UID 65534, read-only inference and network isolation, and preflight weight readability before loading libraries. Add guarded reuse of the existing pilot image without downloads: verify the original model pin and converted-file checksum before changing permissions in a new derived image, preserve the original image, and rerun all 16 unchanged fixtures. Missing files, changed checksums and symlinks remain blocked. The subsequent operator retry passed all 16 cases with no production activation; the failed initial inference is not treated as a model-quality result.

## 2026-10-15

### Local privacy review and explicit external-send consent (#30)

- Operator model comparison at 75b5afa failed both candidates (6/9 each); Hermes was slower and missed different names. Keep staging and activation blocked. Prepare a separate CPU-only GLiNER PII PERSON pilot with digest/revision-pinned weights, restricted weights-only conversion to safetensors, package/version manifest, exact-source fixtures and existing placeholder roundtrip validation. Locally observed 16/16 short synthetic cases passing (the unchanged nine plus seven additional controls), roughly 0.2 seconds per warm case and about 2.7 GiB peak RSS. This evidence comes from the Codex workspace, not the operator server; long contexts and other PII model categories remain unqualified. The guarded server pilot downloads public dependencies into its own container, then tests with no network, 2 CPUs/4 GiB, read-only mounts and no persistent service or production changes. Add offline guard/fixture regressions and preserve failed candidate findings rather than claiming complete detection.

- Operator qualification at 1aa928e passed six of nine unchanged cases. Qwen omitted Anna and Mia, produced an inexact accented name, and returned no model findings for the injection fixture (deterministic rules covered that case). Keep privacy disabled and staging blocked. Add a comparison mode for the already installed, digest-pinned Qwen and Hermes using the same detector, prompt, nine fixtures and strict expectations; record the actual candidate in native usage and unload each model. No model switch or quality claim is made before observed comparison evidence.

- Operator qualification at 2302de8 passed three of six real local detector cases and failed German/full-name, standalone-first-name and accented-name cases. Production remained unchanged, staging did not run and no cloud call occurred. Clarify multilingual exact-span extraction with first-name/Unicode instructions, retain every original expected value and add three held-out cases. Report bounded synthetic-only detector diagnostics and missing expectations. This revised prompt remains unqualified until rerun on the actual server.

- Harden reviewed boundaries before qualification: promote all aliases of credential-shaped values and persist promotions without overwriting encrypted originals; preserve provider protocol identifiers; inspect decoded JSON and numeric tool leaves; require current approval for previously vaulted identities in unchanged-send jobs; respect the configured history window and avoid saving stopped local replies. Add focused regressions and an isolated PostgreSQL upsert/encryption check. Existing runtime-fixture bindings and once-only failure handling were corrected in preceding commits. Real detector quality and deployment remain pending server evidence.

- Add an opt-in `VECTOR_PRIVACY_REVIEW=1` path. A fixed private Qwen endpoint identifies exact sensitive spans locally, combined with deterministic credential/email rules. Preserve original wording around reversible, conversation-stable opaque placeholders and keep mappings in the existing encrypted vault. Include local detector tokens in the usage ledger at zero API rates, even when returned output is rejected.
- Review the prompt, authorized history and locally retrieved text context before message writes/enqueue. Require encrypted, expiring, account/content/context-bound confirmation before either masking or explicitly sending detected values unchanged. Display a compact accessible dialog with findings, masked credentials, preview, cancellation and both choices. Retain drafts on cancellation and discard stale chat-switch UI updates.
- Restore private values only for authorized local display and allowlisted local tools/renderers. Guard provider input centrally and examine subsequent tool evidence locally; new unapproved sensitive tool data blocks unchanged-send jobs. Never restore originals into web/sandbox tool arguments. Reject forged, expired or cross-account review tokens, incomplete detector responses and uninspectable-image masking; images require explicit unchanged-send permission.
- Add a separate native local text-chat path with no cloud routing, search, tools or failover, including local-only projects. It skips privacy warnings and uses a bounded 6 KB context. Local workers under a cloud parent remain external jobs and require the same review. Keep existing behavior while the feature flag is off.
- Add runtime, route/permission, reversal, fail-closed and local-only regressions, plus a synthetic-fixture server qualification script using the actual detector with synthetic names and credentials. The evaluator checks model pins, captures native usage, releases the shared inference lock and unloads weights without changing production or writing database data. Real model quality, browser interaction and production activation remain pending their observed checks; detecting every possible identity or retaining identical task quality cannot be guaranteed.


### Persistent local-worker deployment (#29)

- Operator activation ab2220c succeeded at 15:42 Europe/Zurich, confirming the persistent feature flag/private network, runtime/model pins, idle weights and healthy application. Harden saved rollback recovery for a positively confirmed missing app container; keep inspection errors and different images blocked. Require the inference runtime to use only its private network, and explicitly compare canonical mount lists. These maintenance-script improvements do not require a new app image or another activation.
- Operator source/image release 37130b5 succeeded with healthy app and unchanged supporting containers. Feature activation stopped before cutover because Compose included an extra `ipam` field on the external inference network; its private diagnostic confirmed this was the only differing path and the production Compose file was unchanged. Permit only an empty IPAM object at that exact external network in both preflight and post-cutover comparisons, with regressions retaining rejection of every nonempty IPAM configuration and unrelated change. Retrying activation remains pending operator evidence.
- The operator final b7bf796 actual-worker evaluation passed all eight unchanged synthetic fixtures, accounting for 1,157 input and 117 output tokens with zero local API cost. Exact-source isolated application staging passed, with production unchanged. PR #28 is merged as 37130b5 and its pinned image was subsequently released and activated.
- Pin the tested application image and reuse the established backup, source-tree equivalence, idle-job, health and automatic rollback release flow. Guard the observed original Compose hash before release.
- Prepare persistent activation of the app's local-worker flag and attachment to the existing private inference network. Preserve raw YAML/environment substitutions, compare the entire resolved candidate against the strictly permitted change, and keep other container identities fixed. Verify runtime version/model digests and unloaded weights from the app without inference, cloud calls or database writes.
- Save a separate guarded feature rollback; execute it before an optional source/image rollback. Test configuration preservation, ambiguous layout rejection, the canonical permitted delta and refusal to overwrite later deployment changes.

### Bounded local workers and evaluation (#28)

- The operator d283467 comparison completed with unchanged production, unloaded weights and all 24 native usage records. Qwen3 1.7B and Hermes each passed eight of eight synthetic cases; Qwen 0.6B passed six. Select the pinned 1.7B model for the proposed extraction role, retaining Hermes for structured summaries. These short fixtures do not certify general task accuracy.
- Run the same eight fixtures through the actual scoped worker/accounting core for final qualification, verify the observed 1.7B Ollama manifest digest, and retain the comparison's original expected values without duplicated fixtures.
- Add a read-only deployment shape probe for the subsequent persistent network/feature release. Report only allowlisted image/network/layout/flag metadata and the Compose hash; never print resolved credentials or full YAML. No production activation or configuration mutation.


- The 370150d operator staging passed and its evaluator confirmed unchanged production, but model quality still blocked activation: Qwen passed four of five extractions and invented a zero for an unmeasured value; Hermes invented service names/array structures. Keep both failed cases and their original expected facts in the evaluation.
- Apply the closed output-field schema to Hermes summaries as well as extraction; prose summaries use an explicit string field. Continue treating all results as unverified interpretation rather than equating schema validity with truth.
- Add an isolated eight-fixture comparison across existing Qwen 0.6B, official checksum/revision-pinned Qwen3 1.7B Q8_0 and Hermes. Import the additional 1.83 GB artifact without changing existing models, preserve token telemetry, production snapshots and cleanup, and never auto-select or activate a candidate. Reuse installed runtime/app images without an application rebuild.
- Add an offline comparison-harness regression proving the observed wrong-zero/array responses remain failures, all native token counts are retained and only a fully passing candidate is listed. Actual new-model quality and latency remain pending server evidence.


- The operator first application staging passed, while the subsequent real-model evaluation correctly blocked activation: Qwen returned wrong arrays/field names and Hermes passed its fixture. Retain these failures rather than calling the initial worker evaluation successful.
- Require explicit nullable extraction field names/types, send a native JSON schema and validate every returned key/type locally before accepting interpretation. Shorten role prompts and expand real-model checks to zero, missing values and different English/German counts. Schemas constrain structure, not factual accuracy.
- Canonicalize Docker mount/alias ordering in evaluator fingerprints, save private before/after snapshots, and report exactly which fields changed. Preserve detection of actual image, container, restart, mount-permission and network changes. The earlier unsaved difference cannot be retrospectively attributed to ordering alone.


- Record the operator successful isolated Hermes/Qwen CPU pilot and accounting release. Keep short-fixture timing distinct from general model quality or speed guarantees.
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

- Scope home usage, charts, models and recent projects to each member; preserve the global view for the platform operator.
- Hide all project summaries from accounts without project access, including shared membership leftovers.
- Require feature permission for chat, attachments, activity, Models & APIs and their relevant HTTP APIs; restrict global usage controls to the operator.
- Add authenticated HTTP regression coverage for tenant isolation, project visibility and denied features.
- No database migration, telemetry activation or production deployment in this pull request.

### docs: standardize changelog and release documentation (#16)

- Restore dated and commit-attributed entries for PR #13, #14 and #15.
- Document the separately committed screenshot assets.
- Add changelog requirements to development instructions and PR reviews.
- Update telemetry documentation and record the production preflight.
- No production deployment, database migration or service change.

### `b714f5a` — feat: add operator-only Model Intelligence dashboard (#15)

- Add Model Intelligence to the existing Models & APIs interface.
- Display 7-day and 30-day provider statistics, including request counts,
  success rates, response latency and reported token usage.
- Introduce a read-only API with server-side operator authorization and
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

- Require project membership and operator privileges for protected project operations.
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

The operator observed successful app/source release f38e44f with image 9a2b01e, persistent Compose pinning, health checks and rollback at [private release reference]. Preserve the guarded historical release script. Syntax and archived-helper preparation were verified. The later runtime-release preflight found a changed app image; this does not invalidate the observed composer deployment and does not establish what is currently deployed. Reconcile current release records before another cutover. No production action is performed by merging this PR.

