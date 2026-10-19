# Local privacy review

Privacy review is separate from model mode, ownership and tool permissions. `VECTOR_PRIVACY_REVIEW=1` enables the native detector path; the user can explicitly turn review off for a request. Local-only projects remain local regardless of that switch.

## Send behavior

Authorization runs before review. The outbound message, included history, text attachments and selected project context are inspected locally before the new request is saved/enqueued. A compact review offers cancel, reversible placeholders, or original submission. Credential previews contain bullets. A review ticket is encrypted, expires after ten minutes and binds the account and exact request/context, including the separate tool-evidence preference. Confirmation reuses the scan.

**Original submission covers the reviewed prompt and context.** The composer separately discloses that newly read tool evidence will be inspected and replaced with placeholders. The signed job policy carries that choice and exact original message snapshots. New mappings cannot rewrite those snapshots on later provider rounds; tool results and arguments never inherit the message exemption. Previously known values returned in credential fields are promoted to a hidden credential type before future review metadata. An unsealed payload cannot override it. This permits authorized server investigations to continue without approving unknown future secrets. Legacy policies without that preference retain the stricter additional-consent block.

Tool JSON keys and scalar values are inspected; sensitive credential field names preserve the association with their values. Protocol roles, tool names, call identifiers and opaque provider fields are not rewritten. Encrypted local mappings restore answers and approved local tool arguments, including advancement lookups. Web search, external fetches and sandbox commands never receive restored secrets through that allowlist. Existing authorization still applies after restoration.

A fully local request bypasses detector/review and has no cloud fallback. A cloud parent that uses a local helper remains cloud-bound. Images cannot be reliably anonymized here: remove them or explicitly approve unchanged external transmission.

## Detector and failure behavior

PERSON extraction uses the pinned `urchade/gliner_multi_pii-v1` encoder; deterministic rules also inspect credentials and email addresses. Finite synthetic tests do not guarantee detection of every private value. The optional `services/privacy-ner/server.py` has a lightweight parent and a spawned model child. Health does not wake the model. Warm scans reuse it; after300 idle seconds the child exits. The next request loads it again.

The deployment must supply the private service, strict token ownership, read-only offline model files, resource limits and private networking. There is no cloud/download fallback. Invalid output, overload, unavailable detection, excessive input or scan deadline failure blocks external sending. Cold starts and long contexts can take longer. The current implementation bounds inspected input at160,000 UTF-8 bytes and rejects incomplete coverage.

## Verification and accounting

Synthetic runtime tests cover exact-request consent, original/replace/off, key/value evidence masking, JSON structure, ownership, local-only routing, detector outage, encrypted vault restoration and legacy-policy behavior. CI also exercises PostgreSQL-backed authorization/vault/accounting. Live authenticated HTTP and actual provider/worker behavior require a separate isolated release qualification; source tests are not evidence of production activation.

NER has no generated tokens or API fees. Encoder text-token/chunk metrics are recorded separately from generative usage; private text, detected values and tokens do not belong in usage metadata. Failed usage persistence blocks sending. Existing provider calls retain real input/output usage.

Do not put host-specific activation scripts, production records or rollback evidence into this document. See [deployment boundary](DEPLOYMENT.md).
