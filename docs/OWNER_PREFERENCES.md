# Owner instructions for Vector work

Read this file and PROJECT_HANDOFF.md at the start of a continuation. These are project instructions, not public-assistant memory. Update the handoff after new evidence; check current GitHub/server state before using old pins.

## Collaboration and delivery

- Communicate in concise, natural German with Swiss spelling. No emojis. Prefer connected prose; avoid decorative headings, dashes and repeated explanatory labels in user-facing text.
- Continue authorized development autonomously. Do not repeatedly ask permission already given. A later deployment or message must remain within the actual owner authorization; never invent approval.
- Supply complete, copyable shell commands with exact server paths. Do not provide only ZIP downloads. The owner executes server commands; no direct server or SSH access is available in this workspace.
- Scripts go in /root/vector-workspace/current and run through /root/vector-workspace/bin/run. Use pinned Git revisions, validate fetched heads and script syntax, reject unexpected symlinks or differing existing files, and preserve rollback.
- Do not overwrite failed scripts to hide changed content or bypass a guard. Diagnose actual state first. A repeated command can mean the release already succeeded.
- Keep quality and cost together: simple requests use the fast path; reuse qualified images/evidence when runtime code has not changed. Do not create agent swarms or repeat expensive builds without a concrete reason.
- Review all affected changes, run meaningful checks, and update CHANGELOG.md in every change PR with date, PR number and observed results. Distinguish source merged, staging qualified, production deployed and actual end-to-end behavior.
- Never claim complete security, perfect detection, successful deployment or operational integration without observed evidence.
- Keep secrets, owner prompts, player records, private logs, databases and screenshots out of Git. Synthetic fixtures only. Diagnostics must avoid dumping environment/configuration/token values.

## Product preferences

- Owner update 2026-10-17: show only the active chat mode in a small chooser, with Auto, Low, Normal, High, Search and Lokal options on demand. Default Auto should choose a supported cheap/local path when qualified and retain necessary data tools for other tasks. Add a separate visible default-on request switch for names/credentials privacy scanning and replacement; an explicit off choice sends that request unchanged. Keep authorization, project boundaries and command restrictions independent of this switch.
- Quiet, compact, polished and readable UI. Immediate visible checking state with elapsed time where a local privacy scan can delay submission.
- Privacy review belongs above the input/current prompt, not in a large centered modal. Remove the small eyebrow above its title. Show current-prompt findings/preview by default; separate relevant outgoing history/context so it is not confused with the new prompt.
- Before external transmission, offer explicit placeholder replacement or sending the reviewed originals, plus cancellation. Restore approved placeholders locally in the response. Fully local processing stays quiet.
- Protect all data actually leaving Vector, including tool results and retrieved context. Never interpret an original-send choice as blanket consent for newly discovered tool secrets. Failure must stop the affected external send; provide a useful recoverable state.
- Prefer fast local work with verified, scoped data access; do not invent stats or websites when local text models lack tools. Use on-demand loading/unloading with measured latency, not unverified performance claims.
- Cost/token displays must match all actual provider calls and clearly separate local encoder metrics and zero API fees from cloud billing.

## FEGCraft channel behavior requested

- Answer only messages beginning with a greeting directed at Vector, such as hi/hey/yoo/hallo Vector. Ignore ordinary chat and bot/relayed duplicates.
- Minecraft answers use local models only, without cloud fallback. Allowed topics: saved statistics/records, items, crafting recipes, Minecraft features/facts, redstone, installed mods and relevant troubleshooting.
- Use the authenticated sender's name, a matching short greeting and concise readable formatting. No emojis in either channel or introduction.
- Do not expose seed, passwords/API keys, private assistant memory, raw configuration, administrative internals or commands; do not execute commands from chat. Requests for blanket denial of cheating/creative powers must not become unsupported factual claims: use a neutral scoped answer.
- Rate-limit per authenticated user and globally. Initial foundation defaults are 3/user/minute and 12/global/minute; deduplicate Minecraft/Discord relay events.
- Current scope (owner update 2026-10-17): accept addressed human questions from Minecraft and the existing linked Discord chat channel, through the installed integration. This supersedes the earlier Minecraft-input-only scope after the owner tested Discord-origin questions and expects replies there. Do not add a separate bot or read other channels/DMs; reject bot/webhook/relay copies and retain account/global limits. Discord input requires its explicitly enabled qualified addon hook. Avatar/head presentation remains subject to actual client verification.
- Owner update 2026-10-17: send the one brief Minecraft welcome now, before manual chat tests, once installed service/game readiness and ownership are verified. This explicit timing choice supersedes waiting for complete real-channel qualification. No repeated sends on tests/restarts/uncertain delivery; persist the same durable introduction attempt marker. The announcement does not prove real question routing or Discord delivery.


- Owner update 2026-10-17: show Vector as <Vector> with the actual Vector logo as a Minecraft head and per-message Discord avatar. Preserve unrelated server/bot identities and the durable one-time welcome marker. The welcome is confirmed visible in both chats; styling must not resend it. Pair the head texture with working client pack delivery and report acceptance/rendering limits honestly.

- Owner choice 2026-10-17: the small logo-only Minecraft resource pack shall be mandatory. Explain the one game recreation and client acceptance before the guarded deployment command; preserve all other resource/game settings and the delivered welcome marker.

- Owner update 2026-10-17 16:35 Europe/Zurich: hold the PR #56 deployment command until current data persistence/startup safety is checked. The owner intends to make a backup; this is not evidence that a consistent backup was verified. Explicitly authorizes ONE additional welcome through Vector's native output (not console say), at least 15 seconds after confirmed server readiness. This supersedes the earlier no-resend instruction only for the new owner-authorized v2 event. Preserve the old v1 marker; give v2 its own durable attempt marker and never resend on later restarts/retries or uncertain delivery.

- Owner update 2026-10-17 18:07 Europe/Zurich: the full-folder offline backup caused an unacceptable roughly 36-minute outage. It was cancelled; the same game container is healthy again. Do not rerun that backup, delete its partial archive, or recreate Minecraft while persistence/backup gates remain unresolved. Future backup design must first establish filesystem/snapshot capabilities and a realistic bounded outage; do not promise a quick snapshot on an unverified filesystem. Prioritize the world, all player and mod data.
- Owner asks for helpful contextual Minecraft guidance, including inferring the installed mod from an action and handling spelling/dialect variants. Short per-author followups may use bounded ephemeral topic state; ordinary chat and other people’s context are not permission to read/store a channel transcript. Keep unsupported freeform models disabled until qualified. Prefer a service-only update over another game restart where possible.


- Owner update 2026-10-17 18:36 Europe/Zurich: broad general Minecraft and all installed-mod topics (including claims/parties) should use the local model, with useful short answers and own contextual followups. Do not substitute another fixed narrow guide or promise correctness for every mod. Commands, command outputs/execution, gamemode/cheating, seed and private/administrative information remain forbidden. No cloud fallback or private channel transcript. Actual model quality, scoped CPU admission and role/driver must be qualified before activation.
- The old backup entrypoint has a root-owned 03:00 cron. Replace long offline full archives with online precopy plus a bounded consistent final delta and deduplicated retention; preserve old/partial archives. The initial copy can be large and slow online. Installation must not stop Minecraft or immediately run a backup; do not claim a verified restore point until the actual job succeeds. Root-layer recreation gate still applies.


- Owner update 2026-10-18 18:43 Europe/Zurich: before the pending game restart, add first-person Minecraft statistics bound to the authenticated player, combined metric questions and all-rank views. Support human input from the existing Discord channel and natural short local smalltalk rather than repeating a capabilities list. Keep existing command/seed/gamemode/cheating/private-data restrictions, anchored address requirement and limits. Minimize repeated native tests; reuse qualified components. Discord display names alone are not a verified account link; ask for a Minecraft name rather than assuming identity.

- Owner update 2026-10-18 19:01 Europe/Zurich: keep Minecraft replies short but warmer, avoid repeating the addressed player's name and the saved-file provenance suffix. Expand public context across all installed mods, especially claim building permissions and backpack acquisition/crafting. Greetings must accept any casing. Preserve command/private-data restrictions and minimize native retests. New image-config preservation failure requires diagnosis before another game restart; do not weaken it.
