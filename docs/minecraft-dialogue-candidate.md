# Local conversational candidate

The existing reviewed modes keep their behavior. Experimental mode `6` opts
into `GroundedDialogue` only after separate native qualification and rollout.
Merging this code does not activate it. The default service mode remains `0`.

The candidate separates deterministic capabilities, reviewed evidence and
local generation. Configured-zone wall-clock questions and existing reviewed
simple replies can answer without inference. A single reviewed passage can
also answer directly when lexical subject coverage is strong and its requested
procedure/explanation form matches. This is a narrow optimization, not a
semantic relevance guarantee; weak and ambiguous matches still need inference.

An explicit player assessment with one freshly resolved public player also
uses the existing portrait backend directly. The request form, including combat
style, is preserved; no model invents a second tool query or rewrites the result.
The backend still rereads the statistics. Multiple subjects, unresolved names,
unlinked first-person identity and ordinary counter questions do not take this
shortcut. This reduces routing errors; it is not general semantic understanding.

A category-focused portrait keeps the requested metric even when a different
metric ranks higher. Small and zero counters are included rather than silently
replaced by a stronger achievement. A successful structured lookup retains its
metric identifiers with the recent author/source-scoped turn, independently of
the answer wording. An unambiguous referential own-count follow-up can reuse
that category and read the authenticated player's fresh counters without
inference. Explicit categories override history; multiple inherited categories
need clarification. New objects, unrelated turns, expired contexts and other
authors/sources do not inherit the category. Generated tool queries cannot
change a bound category. This is bounded reference resolution, not persistent
player memory or a claim of general understanding.

Other admitted questions make at most one call to the existing local model.
Supported scoped ranking pages, explicit player counters, selected-category
top lists and comparisons keep their existing statistics backend. These routes
avoid model planning and retain metric metadata for follow-ups. The bounded
category spelling corrections match the existing ranking parser. They do not
turn arbitrary mentions of monsters into a statistics request. Generic chat
still reaches generation and player assessments retain their portrait route.
It can write a short answer or resolve one standalone allowlisted tool query.
Trusted tool results are rendered directly; no second model call rewrites their
facts. Explicit player-count and assessment requests use their actual backend,
while ordinary first-person smalltalk remains conversational. The existing
24-second computation deadline and shared CPU lease remain unchanged.

Public observations contain a configured-zone clock, fresh saved statistics
and relevant reviewed documentation. They never include the complete chat
channel, private Vector memory, arbitrary files, credentials or a world seed.
Self identity uses the authenticated game UUID. A Discord display name is not
a verified Minecraft identity. Lookup types are statistics, portraits, reviewed
documentation, recipes and the public installed-mod inventory. No command,
shell, arbitrary-file or web tool exists.

The candidate uses a 4096-token model context; legacy modes retain 2048 tokens.
The model handles conversation and semantic query resolution. It sees at most two recent exchanges
from the same authenticated author and source, expires them after three
minutes, and retains at most 256 scopes in RAM. Recent exchanges use native user/assistant roles. First-person references
add fresh counters only for the authenticated game UUID; third-person
references can carry their own recent subject. Old replies never replace
fresh reads. Self-only tool queries may not replace the authenticated player
with another known or fuzzy-matched player; an unlinked self query needs an
explicit Minecraft name. Variation is encouraged but is not guaranteed. Existing replay,
rate, input and output policy boundaries apply before and after generation.

Answers target one complete, brief sentence (ideally under 180 characters).
The candidate's general instruction is now written in German and shortened.
This is an instruction change, not a demonstrated improvement in native model
quality or latency. The installed model and inference resource limits are unchanged.
The JSON string may use up to 320 characters so a forced 160-character grammar
limit does not cut a sentence short. The prediction limit stays 80 tokens;
length-stopped output is still rejected. Complete reviewed passages are kept
rather than cut mid-sentence. Novel numeric tokens and visibly unfinished sentences in generated drafts
are rejected. A recoverable draft error can use exactly one complete,
policy-safe reviewed passage; unsafe output and ambiguous/truncated evidence
are not recovered this way. This can return a source-backed answer instead of
a generic outage notice, but does not establish that the model understood it.
Trusted tool results keep their own figures and may use up to 350 characters;
long lists are explicitly bounded rather than silently cut.
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
a separate exec process: generated smalltalk, game help, a player portrait and
an own-player follow-up. A separate direct clock check uses no inference and
is cleared from conversational context before the four questions. It records individual regression checks, including
unsupported temperatures, a missing game-based interpretation and fresh
self statistics changed between turns. Semantic review of actual answers
is still required even when these checks pass. Reply origins and their totals
separate direct clock, reviewed, generated, tool and fallback responses. Clock
qualification expects no model call; player cases require trusted backends.
Both player cases also require zero redundant inference, and their checks
reject player-kill figures substituted for requested mob kills. The temporary
candidate includes the portrait module itself, alongside the four service
modules, so qualification exercises the proposed backend rather than the
installed older version. These source changes have not by themselves passed
the native qualification or activated a production service.
A native timeout stops subsequent probes even when a reviewed fallback was
available. Client/process cleanup does not prove that the inference backend
has already cancelled all internal work. Existing service code, profiles, game, channels and
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

## Signed transport qualification

`scripts/deploy/qualify-minecraft-dialogue-transport.py` consumes a pinned,
successful four-case native report. It verifies the immutable source hashes,
baseline profile/code and current assistant generation before preparing a
private projected code tree. It retains the captured provider/fact modules,
projects the reviewed native-routing changes, and preserves the installed
service token mount and recognized environment-key bindings in `main` only.
Token contents and environment values are not printed or copied. A missing,
writable or ambiguous token mount fails qualification.

The signed HTTP suite runs in a temporary container without external networking,
with synthetic game data, token and usage state. It exercises actual
`Assistant.handle` and HTTP authentication, fresh self follow-ups, counters,
top lists, comparisons, all ranking pages, source isolation, rate-limit page
resumption, replay/policy boundaries, one mocked generated reply and service
construction. These are transport and routing checks, not new model-quality
evidence or real addon/Discord delivery. The earlier native model evidence is
retained separately. No model call, production write, restart or activation is
performed; cleanup and unchanged live identities/profile/code are verified.
The resulting capsule remains ineligible for automatic activation. A separate
guarded rollout must bind the final candidate, profile, evidence and rollback.

## Rejected-answer diagnosis

`--diagnose-rejection` repeats only the synthetic clock and glass questions.
Native profiling and rejection diagnosis explicitly bypass direct routes to
measure the model, while normal qualification uses the actual hybrid route.
The rejection diagnostic uses the same candidate and limits and records a rejected,
policy-safe synthetic answer of at most 320 characters with a bounded error
code. Unsafe output is omitted. No production conversation is captured.
Normal qualification does not log rejected prose. The mode cannot be combined
with streaming profiling; its completed diagnostic never sets a quality pass
or eligibility for activation. Semantic review remains required.

The neutral smalltalk case also rejects previously observed irrelevant death
claims and greetings addressed to the assistant itself. These are targeted
regression checks, not a complete language or meaning evaluator. A grammatically
or factually poor answer can still pass superficial checks and requires manual
review. The single-player portrait case requires the trusted backend and zero
model calls. Cold model loading is reported separately from prompt processing
and generation; a fast warm request does not establish cold-start readiness.
