# Observatory interface and local telemetry

The authenticated workspace uses a black canvas, quiet silver accents, visible
celestial backgrounds and the existing Vector identity. Login and intro source
are unchanged. The overview prioritizes tasks, provider calls, recorded spend and
token/model breakdowns. Host CPU, RAM and storage stay in a compact secondary
column. Navigation, chat, providers, privacy review and control surfaces share
these typography, contrast and frame rules.

Interface preferences remain account-specific in the browser. Ambient decoration
can be disabled separately from motion. Both system reduced-motion preferences
and Vector's motion control stop globe/planet animation. Graphical summaries have
legends, figures or tables; color is not the only status indicator.

## What the measurements mean

| Measurement | Source | Meaning |
| --- | --- | --- |
| Provider calls and cost | Existing usage ledger | Provider-attributed entries and recorded CHF; unpriced/incomplete entries retain their existing status |
| Tasks | Account-owned background jobs | Running/queued work plus recent results; 24-hour counts are labelled separately |
| HTTP requests | Trusted nginx JSON metadata log | Completed web requests, service name, method, status, elapsed time and response bytes |
| TCP connections | Linux conntrack original tuples | Established inbound connections to configured host destinations/ports, including forwarded Docker/Minecraft traffic |
| UDP flows | Linux conntrack | Tracked flows, **not** proof of an authenticated player or TCP session |
| Connection attempts | Observed conntrack events | Starts/state changes; **not** every packet, scan or blocked firewall event |
| Scan activity | Account-owned Vector scan records | Runs the user can access; viewing Traffic never launches a scan |
| Host CPU | `/proc/stat` interval delta | Overall host percentage; Docker container percentages are never added together and called host CPU |
| Host RAM | `/proc/meminfo` | Total minus available memory |
| Storage | `statvfs` of configured volumes | Used and available bytes on each selected filesystem |

When no collector is present, Overview can use the existing host-agent memory and
root-disk snapshot. Human-readable values are approximate. CPU remains unknown
until an actual sampler is available. It is never fabricated.

## Traffic view

The map uses real Natural Earth polygons. Switch between current connections,
HTTP requests and connection attempts. Filter by service, country or client IP;
open an observation for its recorded metadata. Unknown locations stay unlocated.
IP geolocation is approximate and cannot identify a person or prove their actual
physical location. Country-only databases use a representative country point.

The API accepts 15-minute, 1-hour, 6-hour and 24-hour windows. Up to 10,000 events,
500 client groups/current flows and 80 recent individual events are returned.
Caps, dropped events, degraded readers and stale sources are visible. Sources
have a 20-second heartbeat freshness window; connection snapshots expire after
45 seconds. The collector samples connections every 15 seconds and sends host
samples/events every 5 seconds while the page polls every 5 seconds when visible.

These are deliberately bounded observations. They do not promise every request
or connection across the internet. Services hosted elsewhere, including Vercel,
need their own log feed/collector; installing the Linux collector on one host
cannot observe another provider's edge network. Existing firewall/NOTRACK rules,
proxy source-IP handling, logging exclusions and dropped netlink events can also
limit coverage.

## Installation

Use a complete, revision-pinned checkout on the operator's Debian/Ubuntu host.
The collector is optional and requires explicit operator authorization.

```sh
python3 scripts/deploy/update-observatory.py \
  --workspace /absolute/private-workspace \
  --revision FULL_COMMIT_SHA \
  --public-url https://vector.example
```

The wrapper retains the existing app-only updater's image checks, Compose
round-trip validation, healthy-app check and automatic restoration on a failed
web update. It adds the local ingest credential to the app configuration, then
installs the collector. It performs no paid inference, external target scan,
message sending, Minecraft restart or data backup. If collector setup fails
after a healthy app update, the report distinguishes those outcomes. Re-running
the collector installer does not require rebuilding the web image.

The installer uses distribution packages (`conntrack`, `iproute2`,
`python3-maxminddb`, `ca-certificates`) and a dedicated `vector-observatory`
system user. The collector has no Docker socket. Its systemd service has a
read-only filesystem, a loaded credential, a 160 MB memory limit, a 5% CPU quota
and only `CAP_NET_ADMIN` for the kernel connection reader. That capability is
privileged: the shipped code only invokes fixed read operations (`conntrack -E`,
`conntrack -L`, `ss`, `ip`). Do not substitute unreviewed collector code.

Local files:

| Path | Purpose |
| --- | --- |
| `/etc/vector-observatory/config.json` | Service/port map, trusted logs, volumes and local GeoIP database |
| `/etc/vector-observatory/ingest.key` | Root-readable signing credential, supplied through systemd credentials |
| `/etc/vector-observatory/installation.json` | Private installation/coverage evidence |
| `/opt/vector-observatory` | Collector source copied from the pinned release |
| `/var/log/vector-observatory` | Dedicated metadata logs for host nginx |

Docker published ports are discovered once at installation, with an explicit
Minecraft default. Configure additional host services and NAT destinations in
`config.json`. A port shared by several destinations needs an unambiguous
service label; HTTP service names come from trusted `server_name` mappings.
The installer supports host nginx and the documented Nginx Proxy Manager custom
HTTP/server includes. Existing log directives remain, `nginx -t` runs before a
reload, and failed hook validation restores the original file bytes and modes.
Disabled logging, unsupported config fragments and location overrides are not
silently treated as complete HTTP coverage. Existing custom JSON logs can be
configured manually. Protected/unreadable mount paths are reported by the log
reader and may need a narrow operator-managed read permission.

Use `systemctl status vector-observatory` and
`journalctl -u vector-observatory` for local diagnostics. Installation verifies a
recent signed ingestion record separately from systemd's running state. The
Traffic Collection panel is the live source of heartbeat/reader health. To stop
collection, run `systemctl disable --now vector-observatory`; disabling collection
does not remove existing records or the additive nginx logging hooks.

## Privacy and retention

The dedicated nginx format excludes URLs/paths/query strings, request bodies,
cookies, authorization headers, referrers and user-agent strings. The collector
never captures packets or message payloads. Source/destination IPs, ports, service
names and timestamps are still sensitive operational metadata. Traffic is
restricted to owners/admins; host resources use the existing server feature
permission. Task/scan summaries are scoped to the signed-in account.

Ingestion uses timestamped HMAC over the exact request bytes, nonce replay
protection, a 256 KB body limit and bounded event/source schemas. Event and host
sample contents, including source state, are encrypted with the application's
existing encryption key. Nonce checks and ingestion are serialized in a database
transaction. Unknown fields do not become stored event payloads. Snapshots and
HTTP requests are separate records and counts.

API history windows are limited to 24 hours. Physical event/resource rows older
than 24 hours are pruned on subsequent ingestion; inactive source states are
pruned after seven days. Cleanup is not a timer when ingestion is stopped.
The optional local logrotate rule retains one rotated metadata log plus the
current file; rotation timing and copy/truncate can cause observation gaps.
The queue holds 4,000 events, a batch contains at most 200 events, and the reader
reports overflow/lost submissions instead of replaying uncertain batches.

## Local geography and licensing

Natural Earth 1:110m geography is public domain. The bundled simplified asset is
pinned to `nvkelso/natural-earth-vector` commit
`ca96624a56bd078437bca8184e78163e5039ad19`. Polygons use two decimal places;
unassigned regional identifiers are retained as distinct geography features.
Country codes are normalized for map matching, including Taiwan as `TW`.

The optional installer downloads the current monthly **DB-IP Country Lite**
MMDB using HTTPS, bounds compressed/decompressed sizes, validates the database
and records its local SHA-256/source. The database is not committed to Git.
Lookups run locally: client IPs are not sent to a geolocation API. If download
or lookup fails, locations remain unknown and source health reports that state.
DB-IP data is CC BY 4.0; views using it link to [DB-IP](https://db-ip.com).
A configured existing local MaxMind-compatible database can be used instead.

Primary references: [nginx logging](https://nginx.org/en/docs/http/ngx_http_log_module.html),
[Nginx Proxy Manager custom includes](https://nginxproxymanager.com/advanced-config/),
[conntrack operations](https://netfilter.org/projects/conntrack-tools/conntrack-manpage.html),
[DB-IP Country Lite](https://db-ip.com/db/download/ip-to-country-lite),
[Natural Earth terms](https://www.naturalearthdata.com/about/terms-of-use/).

## API additions

| Endpoint | Access | Behavior |
| --- | --- | --- |
| `GET /api/operations/activity` | Chat/projects feature | Own recent tasks/scans and 24-hour task counts |
| `GET /api/server/resources` | Server feature | Latest encrypted host sample, bounded history and freshness |
| `GET /api/traffic?minutes=60` | Owner/admin | Bounded events, source health, current flows, timeline and own scan activity |
| `POST /api/traffic` | Exact signed request | Existing event batches plus optional source heartbeat, snapshot and host metrics |

Legacy signed event batches remain accepted. Heartbeat-only submissions are
valid. Invalid, oversized, replayed and out-of-order source batches are rejected.
No endpoint starts a scan or model call as a side effect of reading telemetry.
