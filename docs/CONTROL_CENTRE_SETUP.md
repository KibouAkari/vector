# Control centre setup

Use the existing deployment architecture. This source update does not contain
operator-specific Compose files and does not activate a server release.

1. Build the exact reviewed commit with Node.js 22 or the existing Node.js 24
   container and locked dependencies: `npm ci`, then `npm run build`.
2. Retain PostgreSQL, Redis, encrypted file storage, existing authentication
   secrets, provider keys and the private worker authentication. Populate the
   new settings from `.env.example` through the existing secret mechanism.
3. Set `VECTOR_PRIVACY_REVIEW=1` and `VECTOR_PRIVACY_DETECTOR=rules` for the fast
   deterministic path. No local model is needed. Use `ner` only when the existing
   private NER service is configured and its additional latency is acceptable.
4. Verify configured provider prices and USD/CHF conversion. Hard admission
   rejects paid models without usable prices. Configure monthly user/project
   limits in Usage & Budgets; environment daily/monthly limits are still ceilings.
5. Leave `VECTOR_SECURITY_PRIVATE_CIDRS` empty for public assets only. For an
   authorized NAS/private host, allow only its intended IPv4 CIDR. The worker
   still needs network reachability. Never publish a new unauthenticated scanner
   endpoint or mount a Docker socket for this feature.
6. Keep the existing worker polling `/api/internal/jobs/run-one`. Scan jobs share
   this authenticated endpoint and run when no chat job is available. A page can
   save scope without a worker, but queued scans will not execute until it runs.
7. Authenticate with an owner account. Review model/tool policies, test the fast
   privacy drawer with synthetic text and add only a target you own/are authorized
   to assess. Keep external-advisory lookups off unless version disclosure is wanted.

Schema additions use the current idempotent startup mechanism, including the
asset, run, role-policy, skill-version and reservation tables. Run authenticated
CI before deployment; a successful build alone does not prove database behavior.
Do not execute real queued production jobs as a staging test. Independent game,
inference, bridge and other host services do not need to be recreated for this
web change. Follow the existing app-only release procedure.

## Verification evidence

Offline tests exercise exact selection/receipt payloads, scope pinning, metadata
blocking, redirect refusal, bounded sockets, fragmented Minecraft status,
parameter validation, single-use grants and reservation failure behavior.
Authenticated CI uses disposable PostgreSQL and signed account cookies to check
ownership, read-only mutation refusal, scope approval, scan cancellation, skill
versions and concurrent budget admission. It calls no paid model and launches no
external target scan. Browser component fixtures use synthetic data; they do not
establish live-provider quality or a production rollout.
