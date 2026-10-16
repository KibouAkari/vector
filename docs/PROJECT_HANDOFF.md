# Vector project handoff

Updated 2026-10-16 after owner confirmation of the deployed runtime release. Read OWNER_PREFERENCES.md, AGENTS.md and current repository status first. This document preserves decisions and evidence, not secret values or a substitute for a live-state check.

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
| Current runtime deployment | CONFIRMED by owner read-only evidence: vector-runtime-privacy-release-20261016T165856Z-c0c023 has status deployed; commit 60adca9398dff938e97df4f00bf8a2c476dde907 and qualified image c33a1b8 match actual runtime/source/Compose. No repeat deployment is needed |
| Native privacy service | Previously activated private authenticated GLiNER service; local workers retained; model unloads after 300 idle seconds |
| Local inference | Private vector-local-inference, Qwen 1.7B extraction/text and Hermes 8B summaries; no public inference ports |

Runtime qualification pins:
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
- Local text executor now blocks unsupported live/tool lookups before inference instead of inventing server stats. It still has no server data access.
- New tool secrets under original-send consent are blocked before that tool evidence is exported. Error wording now distinguishes this from the prompt already sent.

Still required:
1. Interactive consent/resume for newly discovered tool evidence. Do not broaden consent or disable protection to remove the error.
2. Diagnose intermittent native-review failures with bounded reason codes for busy/timeout/invalid response/size, preserving fail-closed external sending. Earlier synthetic health success is not a root-cause fix.
3. Verify real user-facing provider execution for fresh mail requests after runtime deployment, plus current-only compact UI behavior. No real credentials in tests.
4. Implement and independently test the unimplemented #37 review items: credential alias type promotion/persistence; structured and numeric provider values without altering protocol fields; vaulted identities in original-send checks; configured history bounds; duplicate failure/cancelled-local-job completion handling. The old PR description is not evidence of a fixed vulnerability.
5. Continue actual provider-cost reconciliation: original owner samples showed repeated large cumulative input usage across tool rounds (293741 and 793264 input tokens), despite short visible history. Do not invent corrected historical bills. Verify ledger completeness, failed/retried calls, cached/reasoning tokens, pricing/version, currency conversion, time/project scope and provider billing differences from actual records.

## FEGCraft foundation and integration plan

Owner update 2026-10-16: input integration is Minecraft only; reuse existing Discord forwarding/output. No separate Discord listener. Verified that Discord-origin system messages do not invoke the Minecraft player hook, so they do not automatically trigger the assistant.

New source phase: a disabled-by-default Discord Integration addon compiles against the actual Fabric 26.2 / 3.2.1 nested API; private HMAC Python transport and deterministic statistics, persistent limits/replays and optional local-only knowledge adapter are implemented. Nine new Python tests plus Java interoperability/output/body/intro checks pass locally. Existing ten foundation tests remain. No addon installed, service activated, model called or introduction sent. Owner read-only preflight at cbc7cc8b5a9502de58085db8e3651f14caa980ea passed: exact public integration hash/API, 50/50 readable named stat files, 63 mod metadata IDs, Qwen available; mc-net and vector-local-inference are separate; no host javac or installed Vector addon. Compose and production identities unchanged. Next run the pinned evaluate-fegcraft-bridge.py captured container qualification described in docs/FEGCRAFT_ASSISTANT.md. Real-game/relay, isolated service packaging, restricted CPU-slot role, model quality/usage and guarded install/rollback remain unqualified.

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
1. Owner read-only preflight is complete. Run isolated captured addon/API qualification next: container compiler instead of host packages, synthetic inputs, no real sends/model calls, temporary service restart. The Bridge fixture captures host scheduling/identity/delivery and exercises actual addon/HTTP logic; actual game callback/relay remains a separate gate.
2. Provide narrow read-only statistics/mod/recipe sources to local execution. Prefer deterministic retrieval/calculation for records; give the local model only bounded approved facts. No arbitrary filesystem/shell tools.
3. Apply topic/output policy before public sending, neutral handling of administrative allegations, no seed/credentials/commands/private memory. Add version/mod-aware Minecraft knowledge with provenance; never fabricate recipes.
4. Implement local-only inference, bounded work queues, limits and durable dedup/introduction state. No cloud fallback. Format concise channel-specific replies with author greeting.
5. Qualify on synthetic fixtures and isolated owner environment, then guarded deployment/rollback. Only then send the authorized once-per-channel introduction and verify delivery outcomes. Logo/avatar/head support remains unimplemented.

## Release handling cautions

Archived release helpers live only on the owner machine. Local copies can test syntax/factory preparation but not prove server state. Existing machinery protects source, images, Compose, other containers, backups and rollback. New repository documentation/ops commits do not mean /opt/vector/app should be switched to new main without a qualified application release. Preserve exact tested-image/source equality and never rebuild solely to archive docs.

A repeated release may stop because its previous successful run changed the image. Establish a matching completed release record and actual app/source/Compose health. If changed state is unknown, stop before mutation and reconcile it. Do not reinterpret image-only drift as a successful deployment.

## Captured staging preparation

The owner preflight has no pending retry. New evaluator source prepares only a private temporary service/network and compiler containers, without changing Minecraft/app/NER/Ollama services. It uses an exact pinned official JDK image and the existing qualified native Python image; no production credentials, data or public network ports enter the evaluation. Local captured first/restart phases and nine evaluator regressions pass. PR #40 reproduces and fixes silent loss of an immediate next question during worker completion, using single-request admission and a bounded completion handoff before visible delivery. Interrupted/incomplete qualification cannot pass; partial timeout/completed logs are bounded and daemon/permission inspection errors propagate to cleanup failure. Owner Docker qualification is pending; do not mark it passed until result.json is observed. Actual knowledge inference, dedicated CPU-slot DB role, native token telemetry, recipes/mod correctness, game callback/Discord delivery, logo and guarded installation remain pending. No announcement has been sent to real channels.
