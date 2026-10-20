# Local conversational candidate

The existing reviewed modes keep their behavior. Experimental mode `6` opts
into `GroundedDialogue` only after separate native qualification and rollout.
Merging this code does not activate it. The default service mode remains `0`.

Instead of matching a social expression or selecting a canned passage, the
candidate sends every admitted, permitted question to the existing qualified
local instruction model. One structured call may answer from reviewed game evidence,
fresh public observations and conversational context, or request one allowlisted lookup.
A lookup is followed by at most one answer call within the same 24-second
computation deadline and shared CPU-slot lease.

Public observations contain a configured-zone clock, fresh saved statistics
and relevant reviewed documentation. They never include the complete chat
channel, private Vector memory, arbitrary files, credentials or a world seed.
Self identity uses the authenticated game UUID. A Discord display name is not
a verified Minecraft identity. Lookup types are statistics, portraits, reviewed
documentation, recipes and the public installed-mod inventory. No command,
shell, arbitrary-file or web tool exists.

The candidate uses a 4096-token model context; legacy modes retain 2048 tokens.
The model writes its own short answer. It sees at most two recent exchanges
from the same authenticated author and source, expires them after three
minutes, and retains at most 256 scopes in RAM. Recent exchanges use native user/assistant roles. First-person references
add fresh counters only for the authenticated game UUID; third-person
references can carry their own recent subject. Old replies never replace
fresh reads. Variation is encouraged but is not guaranteed. Existing replay,
rate, input and output policy boundaries apply before and after generation.

Answers target one complete, brief sentence (ideally under 180 characters).
The JSON string may use up to 320 characters so a forced 160-character grammar
limit does not cut a sentence short. The prediction limit stays 80 tokens;
length-stopped output is still rejected. Complete reviewed passages are kept
rather than cut mid-sentence. Novel numeric tokens are rejected on the first
answer as well as after lookups. Visibly unfinished sentences are rejected.
These checks do not prove factual correctness. General
model knowledge can still be wrong; reviewed facts do not cover every mod or
server setting. Never claim universal accuracy. Do not activate merely because
mocked transport tests pass. Short native semantic and latency checks must pass
on the actual local model and restricted role. Keep the addon HTTP deadline in
mind: a model that cannot complete within this budget needs a runtime or model
improvement, not a silently relaxed safety gate.

`scripts/deploy/evaluate-minecraft-dialogue.py` uses the confirmed operator
release as its baseline, preserves the installed private catalog pins and
server aliases in a temporary candidate, and runs four synthetic questions in
a separate exec process. It records individual regression checks, including
unsupported temperatures, a missing game-based interpretation and fresh
self statistics changed between turns. Semantic review of actual answers
is still required even when these checks pass. Existing service code, profiles, game, channels and
production event state remain unchanged. Only temporary fixture state and a
private qualification report are written. Local token usage is reported in
that evidence, not written to the production usage ledger; no API fee applies.
The production constructor still uses its normal usage ledger callback if a
future guarded rollout opts in. No automatic activation follows evaluation.

Evaluation takes an explicit existing owned release-lock file. It saves the
transformed candidate sources, baseline record/profile, evaluator and a hash
manifest before execution. An in-container watchdog reaps its own process
group; host cleanup targets only the nonce-marked child via a PID descriptor
and verifies termination before leaving the release guard. No service is
stopped. Bounded leader observations explicitly mark omitted tied holders.
Apostrophe digit grouping is normalized for numeric checks; ambiguous decimal
and clock formats remain distinct.

## Rejected-answer diagnosis

`--diagnose-rejection` repeats only the synthetic clock and glass questions.
It uses the same candidate and limits and optionally records a rejected,
policy-safe synthetic answer of at most 320 characters with a bounded error
code. Unsafe output is omitted. No production conversation is captured.
Normal qualification does not log rejected prose. The mode cannot be combined
with streaming profiling; its completed diagnostic never sets a quality pass
or eligibility for activation. Semantic review remains required.
