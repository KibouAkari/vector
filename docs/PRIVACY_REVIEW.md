# Local privacy review

PR #30 remains disabled until native service and isolated application staging
are observed on the owner server. A passed finite fixture set is not a guarantee
that every name, password or other private datum will be detected.

## Send behavior

- Cloud-bound text, included history, attachments represented as text and project
  context are inspected before saving/enqueueing the new request. The existing
  account/project authorization checks run first.
- A compact dialog offers replace, explicitly send unchanged, or cancel. Credentials
  in findings use bullets. A confirmation ticket is encrypted, expires after ten
  minutes and binds the account, context and destination. Confirmation reuses the
  result rather than paying for another scan.
- Opaque conversation-stable placeholders preserve exact originals in the encrypted
  local vault. Response restoration and approved local tools restore originals in
  one pass. Web tools and sandbox commands do not receive restored secrets.
- A fully local text request bypasses the warning, detector and cloud providers.
  A cloud job using a local helper still follows the cloud review path.
- New tool evidence is inspected locally before it can reach a provider. Replace
  consent covers substitution of new tool findings; unchanged-send consent does
  not silently approve previously unseen data. Image masking is not claimed:
  remove images or explicitly approve their unchanged external transmission.

## Detector and runtime

PERSON extraction uses Apache-2.0 `urchade/gliner_multi_pii-v1` at immutable
revision `1fcf13e85f4eef5394e1fcd406cf2ca9ea82351d`; credentials and emails also
use deterministic local rules. Other NER PII categories are not qualified.
The observed 32 synthetic server cases passed at f7b5bb4, including Unicode,
first names, full names in longer contexts, credential previews and reversibility.

`services/privacy-ner/server.py` has a lightweight standard-library parent and a
single spawned model child. Health checks do not wake it. The first scan loads
the model; warm requests reuse it; after 300 idle seconds the child exits, returning
its model memory to the OS. The next request starts a fresh child. There is no
hidden queue, network/model download fallback or cloud fallback. Scan deadlines
kill a stalled worker and block the external request. Failed loading, bad detector
output, excessive input or unavailable local capacity also block the send.

The proposed private service has no published port, an internal-only Docker
network, UID 65534, a read-only filesystem, dropped capabilities, 2 CPUs/4 GiB,
no production data mounts and offline Hugging Face settings. A 256-bit bearer
secret is read from `/run/secrets/vector_privacy_ner_token` in the app and service;
never log it or commit it. The app uses the fixed private service hostname.
Production installation and Compose integration are still pending; the evaluation
script creates temporary isolated containers and removes its random token.

Input is bounded at 160,000 UTF-8 bytes with complete word-splitter coverage,
64 words/192 text subwords per chunk, 12-word overlap and at most 32 original
focused context rechecks. Exact spans and nested names are retained at threshold
0.35. Exceeded bounds are errors, not silent truncation. Cold starts and long
texts take longer than short warm requests.

## Accounting and evidence

The NER encoder has no generated output tokens and incurs zero API fees. Its
actual raw-text subword counts, overlap and rechecks are recorded separately in
`local-privacy-scan` usage metadata. They are not added to generative input/output
or provider billing totals. Model/version, chunk counts and timing are metadata;
text, findings, originals and bearer secrets never enter usage metadata. Ledger
persistence failure blocks sending. Existing local chat/provider usage continues
to use its actual native counts.

The historical Qwen/Hermes evaluator is an explicit separate candidate benchmark;
neither failed candidate is the current application privacy backend. The current
native service evaluation covers all 32 fixtures over authenticated HTTP, actual
app consent/runtime behavior, tool JSON protection, idle unload/wake, service-outage
blocking, zero API fees and production fingerprints. It uses in-memory synthetic
vault/usage adapters; this is not an authenticated browser or production database
integration test. CI separately exercises routes, authorization, PostgreSQL vault
promotion/encryption and the application build. Owner application staging remains
a release prerequisite.

## Rollback and deployment boundary

No production activation is included in the service qualification. Failed checks
remove only their owned temporary containers, token and private network; production
source, images, configuration and database contents stay unchanged. Keep PR #30
unmerged and `VECTOR_PRIVACY_REVIEW` off until the remaining evidence passes.
A production release must preserve source/image equality, back up Compose/source,
add only the reviewed service/token/network/feature settings and provide a tested
feature rollback followed by the existing application/source rollback. Do not
reuse an isolated evaluation network or temporary token for production.
