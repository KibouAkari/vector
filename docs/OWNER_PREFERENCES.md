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
- Current scope (owner update 2026-10-16): integrate Minecraft chat input only and reuse the existing linked Discord output channel; no separate Discord listener/bot. The actual Minecraft hook does not receive Discord-origin system messages, so those do not automatically trigger Vector. Discord avatar and Minecraft logo/head presentation need version-supported implementations.
- Send one brief introduction only after final successful integration/qualification. Owner has authorized that eventual introduction, not repeated sends during tests or restarts. Persist channel delivery state and handle uncertain outcomes without automatic resend.
