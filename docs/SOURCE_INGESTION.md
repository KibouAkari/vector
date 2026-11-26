# Retained project web sources

Source implementation, 26 November 2026. A successful source build does not
establish that this feature is installed on a server.

## Use

Open a project's Files tab. In Sources, enter a public HTTP or HTTPS URL and
choose Import URL. Vector requests that page directly without sending chat,
project content, cookies or authorization headers to the website. Only project
editors and owners can import; readers can inspect the retained results.
Local-only projects reject web imports. Existing file uploads remain available.

The source panel shows importing, searchable, partial, failed or interrupted
state. Completed imports add a read-only text file to the existing project file
browser. It can be searched through the existing project chat and project_search
tool. Source metadata includes the final URL, retrieval time, extraction method
and separate original/text SHA-256 hashes. Retrieval time is not publication time.
The original response can be downloaded as an attachment; HTML is never served
inline by the source snapshot endpoint.

Repeated delivery of the same request UUID reuses the same source record without
another network fetch. Failed imports may be retried after 30 seconds, with at
most three attempts. A process interruption leaves a retained record; after two
minutes the interface marks it interrupted and offers retry. There is no automatic
worker queue or restart/resume promise in this bounded request-based importer.

## Supported scope and limits

| Boundary | Current behavior |
| --- | --- |
| Content | Static HTML, plain text and Markdown |
| Download | At most 2 MiB, 15 seconds total including DNS and redirects |
| Redirects | At most three; revalidate DNS and destination on every hop; no HTTPS downgrade |
| Connections | Pin a validated public IP in the HTTP client's lookup; preserve the original Host and TLS identity |
| Network scope | Reject private, loopback, link-local, metadata, reserved, documentation, multicast and transition ranges; reject mixed public/private DNS answers |
| URL syntax | No embedded credentials, non-HTTP protocols, custom ports, local names or trailing-dot hosts; fragments removed |
| Request body | JSON only, at most 4096 bytes and five seconds to read |
| Extraction | At most 180,000 input text characters, with bounded physical lines; longer pages marked partial; reject excessive HTML nesting/element counts |
| Compression | Request identity encoding; reject compressed responses rather than decompressing unbounded data |
| Capacity | 100 snapshots per project; five claimed attempts per project per minute; one active import per project and two globally |
| Retention | Original snapshot and derived text retained until explicitly removed with their project; removing the derived file alone keeps the original source snapshot |

JavaScript rendering, authenticated sites, OCR, PDFs/Office web imports,
recursive crawling, scheduled refresh, source removal controls and a durable
background import queue remain outside this change. Static extraction can contain
navigation or layout noise and does not establish factual correctness. Empty text
and unsupported encodings/types return a failed outcome. An indexed page is
searchable evidence, not a verified statement.

The model receives source evidence only through the existing permission and
privacy paths. New source URLs and text are included in project privacy review;
tool results retain the existing evidence sanitization. Imported content cannot
grant tools, permissions or authority. The importer itself never calls a model.
Cloud answers still require the existing request policy; this feature does not
silently change local-only routing or consent.

## Storage and consistency

`project_sources` stores project-scoped provenance, attempt identity, lifecycle,
content hashes and the encrypted original response. `project_source_attempts`
records claimed starts for a cross-process rate limit. A short shared advisory
transaction lock serializes capacity checks; it is not held during the download.

The extracted text uses existing encrypted project-file storage. PostgreSQL text
chunks retain the existing database storage model; they are not independently
field-encrypted. Protect the database, storage volume and backups accordingly.
No project or chat data is sent to an external extraction service.

Source metadata, file metadata and index chunks commit in one transaction. An
index failure rolls back those writes and records a public error code; cleanup
only targets the newly staged encrypted file. The original stored response is
encrypted with the existing file key. A revoked project editing permission is
checked again after acquisition, before materialization. An attempt token prevents
an expired request from overwriting a newer attempt.

Imported text files cannot be edited through the file PATCH route. Make a separate
working document to edit text while retaining its original evidence. Tool evidence
is returned only when the linked file's hash still matches the retained extracted
text hash. The original snapshot remains separately downloadable by project
members. Acquisition time and source hashes identify a snapshot, not live website
freshness or a publication date.

## Dependencies and verification

HTML extraction uses exactly `htmlparser2@10.0.0` (MIT), as a parser only. It does
not execute scripts or load subresources. The package lock pins the resolved
transitive tree. Next.js is patched from 16.4.0 to 16.4.6 for the advisories reported
by the npm registry. ExcelJS's UUID dependency is constrained to CommonJS-compatible
11.1.1; a real conditional-format XLSX round-trip verifies that usage.

Tests cover private addresses and URL forms, DNS rebinding/mixed answers,
redirects, pinned local test transport, byte/type/encoding limits, extraction,
authentication/project roles, attachment-only originals, privacy review of
provenance and PostgreSQL import atomicity, idempotency, retry and revocation.
Network tests use loopback fixture servers and injected DNS; no public website,
model provider or production data is contacted by these tests.

A production release still needs exact-image staging, schema privilege/storage
qualification, UI review and an owner-authorized deployment. npm audit is a
registry dependency check, not a guarantee of application security.
