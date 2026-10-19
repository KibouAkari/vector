# Changelog

This file describes product and engineering changes. Deployment diaries, personal preferences, host identifiers and operator-specific rollback records are private operating material. Historical Git entries are retained in the private repository; this file is not evidence that a release is live.

## 2026-10-19

### Web reliability — PR #91

- Preserve original-send consent for the reviewed prompt/context while separately protecting newly read tool evidence with placeholders.
- Bind the evidence preference to the signed review, preserve legacy fail-closed behavior and mask structured credential fields.
- Restore advancement arguments only inside authorized local tools.
- Keep short local requests usable in long chats by dropping oldest complete turns.
- Keep own-server corrections within the latest uninterrupted statistics task.

### Repository portability — PR #92

- Separate private deployment scripts, inventories and operating notes from reusable source.
- Document Minecraft as an optional independent integration, with operator-supplied data locations and aliases.
- Build container dependencies with `npm ci` and the committed lockfile.
- Refresh README and engineering guidance. Preserve authorization role identifiers and existing private Git history.
- Reject dangling/directory symlinks in source checks and detect configuration disappearance during a read-only inventory.
- Add a source publication check and read-only web deployment inventory; no game deployment or restart is performed by this change.
