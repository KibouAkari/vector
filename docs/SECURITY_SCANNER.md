# Active asset scanner

The `/security` workspace runs bounded, non-exploitative checks against an
explicitly authorized asset. It is not a full penetration test and does not infer
that a target is secure from absent findings. No model API is required.

## Scope and authorization

Save a domain, IPv4, IPv6 or host:port, a name, type and up to 64 TCP ports. An owner
confirms authorization once per saved scope. Admin-created scopes await the
owner queue. Each scope retains its resolved addresses, selected checks and
external-advisory consent in an immutable digest. Subsequent runs use the saved
grant. Revocation cancels queued runs. Address changes require reauthorization.
A request UUID makes asset-save retries idempotent.

DNS resolution is bounded and every returned address must pass the network
policy. The worker resolves again and refuses changed addresses before probing.
Connections are pinned to validated literal addresses; HTTP preserves Host/SNI.
Redirects are recorded, never followed. URL credentials and paths are rejected.
Loopback, link-local, cloud metadata, reserved and transition addresses are
blocked. Private IPv4 is disabled unless the operator sets
`VECTOR_SECURITY_PRIVATE_CIDRS` to the authorized ranges. That allowlist cannot
permit metadata or loopback. Private IPv6 is not supported by this allowlist.
Do not broadly allow private networks on an internet-facing multi-user instance.

## Checks and evidence

| Check | Evidence | Limit |
| --- | --- | --- |
| TCP discovery | Open, closed, timeout/error; bounded passive banner | Four concurrent connections, 1200ms connect deadline, at most 64 selected ports |
| HTTP | Status, selected headers, server banner, CSP, HSTS, framing and nosniff observations | At most six web endpoints, no redirect or authenticated session, 64KiB response body |
| Exposed files | Positive-format evidence for `/.env` and `/.git/HEAD`; `/robots.txt` and `/admin` as information | No downloaded secret body retained; an HTML fallback is not treated as a leaked file |
| TLS | Chain/hostname result, issuer, validity dates, negotiated protocol/cipher | One negotiated connection; not exhaustive cipher enumeration |
| Minecraft Java | Status MOTD, advertised version/protocol, player counts | No login, sample player names discarded; online-mode/authentication cannot be established from status |
| OSV | Advisory matches for explicitly supplied ecosystem/package/exact version | Opt-in, up to ten packages |
| NVD | Version candidates for recognized nginx, Apache or OpenSSH banners | Opt-in, up to three recognized products, paced requests |

OSV/NVD requests go only to the fixed official API destinations. They disclose
product/package versions, not target names, private credentials or page bodies.
The asset form makes that separate choice explicit. Optional `NVD_API_KEY` is
server-only. An API outage is reported as unavailable/partial, not zero risk.
Banner versions may be hidden, misleading or patched by distributions. Candidate
matches require applicability verification and are not confirmed exploits.
Unrecognized severity remains informational; the scanner does not invent CVSS.

## Queue, cancellation and limits

The existing authenticated worker endpoint claims a scan when no agent job is
available. One scan runs globally; at most three queued/running runs per user are
accepted, with a 60-second per-asset cooldown and 50 active assets per account.
A run has a 75-second deadline. Cancellation, account state and authorization are
rechecked during progress. Already issued bounded probes can finish before
cancellation returns. A stale run is marked interrupted rather than replayed.
Chat jobs have priority; a long-running check may delay the next worker poll.

The report separates severity, open-port tables, web/TLS observations, Minecraft
status, advisory candidates and coverage. JSON/Markdown export is owner scoped.
Normalized reports are stored in PostgreSQL; protect its volumes and access.
Scans do not download or persist `.env` credentials. Evidence descriptions may
still contain sensitive hostnames/banners, so reports are not public documents.

## Module boundaries

`targets.mjs` parses and pins scope. `probes.mjs` implements sockets and HTTP/TLS.
`advisories.mjs` queries version services. `active-scan.mjs` orchestrates deadlines
and deterministic reports. `scan-store.js` owns PostgreSQL state, grants and queue.
The UI calls authenticated asset/run endpoints. There is no shell execution,
arbitrary scan script, exploitation, UDP discovery or automatic remediation.

The previous strict Nmap XML importer remains at `/security/evidence` for
separately obtained evidence and PDF export. Its scope is independent.

References: [OSV query API](https://google.github.io/osv.dev/post-v1-query/),
[NVD vulnerability API](https://nvd.nist.gov/developers/vulnerabilities).
