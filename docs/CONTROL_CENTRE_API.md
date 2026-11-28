# Control centre API

All endpoints require the existing signed session. Errors do not expose other
users' records. Critical POST/DELETE operations enforce role and ownership at
the API and again before execution. Request bodies are bounded JSON.

| Endpoint | Methods | Contract |
| --- | --- | --- |
| `/api/security/assets` | GET, POST, DELETE | Own assets/recent runs; save immutable authorized scope with `requestId`, `name`, `target`, `kind`, optional `ports`, `packages`, `checkAdvisories`; revoke by `id`. Owner/admin only. |
| `/api/security/scans` | POST | Queue `{assetId}` after matching approval; returns 202 with run. |
| `/api/security/scans/{id}` | GET, DELETE | Own run/status/report or cancellation. `?format=json` / `?format=md` downloads an attachment. |
| `/api/skills` | GET, POST | Own global skills. POST `create`, `revise`, `activate` or `retire`. |
| `/api/projects/{id}/skills` | GET, POST | Same lifecycle with existing project permissions and owner activation. |
| `/api/approvals` | GET | Owner-only bounded queue, including the requester and verified saved scope for scanner approvals. `?summary=1` returns pending count. |
| `/api/approvals/{id}/decision` | POST | Owner CAS decision `{decision:"approved"}` or `rejected`; scanner approval also requires the reviewed `scopeDigest`. Decisions are audited. |
| `/api/permissions/policies` | GET, POST | Owner role allowlists and critical-action policy. |
| `/api/budgets` | GET, POST | Own limits/reservations, or owner administration. POST scope, currency, monthlyWarning, monthlyHard. |
| `/api/usage/calls` | GET | Own cursor-paginated provider ledger. Optional `after`, exact `model` and `project` UUID filters. |
| `/api/chat` | POST | Existing chat fields plus selected `skillIds` and typed `skillParameters`. Privacy review returns 409 before enqueue when consent is required. |
| `/api/projects/{id}/chat` | POST | Same skill/privacy contract with project context and access. |
| `/api/internal/jobs/run-one` | POST | Existing worker authentication; agent jobs first, then one queued scan. No public execution grant. |

Skill revision includes `parentId` and `baseContentSha256`; activation/retirement
includes `id` and `contentSha256`. Privacy confirmation includes the bound token,
`privacyDecision` and selected `privacyReplaceIds`; never substitute local preview
aliases for these server-issued identifiers. Confirmed responses retain a privacy
receipt with the actual protected current-message text. Local restoration of a
message in the conversation is not evidence of plaintext external transmission.

Budget scopes are `workspace`, `user:{UUID}` or `project:{UUID}`. Role allowlists
use `null` for the existing allowed set and `[]` to deny all. Model entries are
exact `provider/model`; tool entries are exact runtime names. Unknown or invalid
scope, version, digest or selection fails before execution.

## Observatory telemetry

The authenticated activity/resource endpoints, extended signed traffic payloads,
limits and collection permissions are specified in [Observatory](OBSERVATORY.md#api-additions).
