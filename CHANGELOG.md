# Changelog

This changelog records the commits available in this repository history.

## 2026-10-14

### `6e10ca9` — fix(cost): attribute usage events to users and verify budget isolation (#11)

- Store the owning user ID with provider usage events, including when a background job supplies the user ID.
- Centralize usage-event persistence and per-user total/monthly cost aggregation.
- Add a user-and-date index for usage lookups and create the privacy-events table.
- Add isolated-PostgreSQL integration coverage for user attribution and budget separation, and run it in application CI.

### `5945c33` — security: enforce project membership and server resource access (#10)

- Require project membership and owner privileges for protected project operations.
- Apply access checks to file, task, tool, conversation, and related server-resource routes.
- Add authenticated project API integration coverage using isolated PostgreSQL, and run it in CI only when its fixture is available.
- Preserve successful response bodies in integration tests and cover the file-write guard and editor deletion behavior.

## 2026-10-13 — Repository foundation

- Captured a sanitized private Git snapshot.
- Added architecture, security and attribution documentation.
- Introduced a reviewable branch and pull request workflow.
