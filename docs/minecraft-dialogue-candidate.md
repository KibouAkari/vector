# Local conversational candidate

The existing reviewed modes keep their behavior. Experimental mode `6` opts
into `GroundedDialogue` only after separate native qualification and rollout.
Merging this code does not activate it. The default service mode remains `0`.

Instead of matching a social expression or selecting a canned passage, the
candidate sends every admitted, permitted question to the existing qualified
local instruction model. One structured call may answer from general game
knowledge and fresh public observations, or request one allowlisted lookup.
A lookup is followed by at most one answer call within the same 24-second
computation deadline and shared CPU-slot lease.

Public observations contain a configured-zone clock, fresh saved statistics
and relevant reviewed documentation. They never include the complete chat
channel, private Vector memory, arbitrary files, credentials or a world seed.
Self identity uses the authenticated game UUID. A Discord display name is not
a verified Minecraft identity. Lookup types are statistics, portraits, reviewed
documentation, recipes and the public installed-mod inventory. No command,
shell, arbitrary-file or web tool exists.

The model writes its own short answer. It sees at most two recent exchanges
from the same authenticated author and source, expires them after three
minutes, and retains at most 256 scopes in RAM. The prior answer and a changing
wording hint encourage variation; variation is not guaranteed. Existing replay,
rate, input and output policy boundaries apply before and after generation.

Structured output and numeric checks do not prove factual correctness. General
model knowledge can still be wrong; reviewed facts do not cover every mod or
server setting. Never claim universal accuracy. Do not activate merely because
mocked transport tests pass. Short native semantic and latency checks must pass
on the actual local model and restricted role. Keep the addon HTTP deadline in
mind: a model that cannot complete within this budget needs a runtime or model
improvement, not a silently relaxed safety gate.

`scripts/deploy/evaluate-minecraft-dialogue.py` uses the confirmed operator
release as its baseline, preserves the installed private catalog pins and
server aliases in a temporary candidate, and runs four synthetic questions in
a separate exec process. Existing service code, profiles, game, channels and
production event state remain unchanged. Only temporary fixture state and a
private qualification report are written. Local token usage is reported in
that evidence, not written to the production usage ledger; no API fee applies.
The production constructor still uses its normal usage ledger callback if a
future guarded rollout opts in. No automatic activation follows evaluation.
