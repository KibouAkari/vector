# FEGCraft local assistant foundation

Status: draft components, not connected to chat, not deployed.

The collector follows the existing seven movement counters and tick/hour conversion in the owner-provided statistics script. Runtime paths are configured by the operator: saved player statistics and usercache only. No access to world metadata, server properties, ops lists, credentials, commands or arbitrary paths is needed. Read timestamps are not live player-state timestamps. Missing counters in valid custom maps follow the existing zero convention; unreadable or unnamed records prevent definitive ranking claims. Ties are included and positive records are reported by exact case-insensitive player name.

Admission accepts only an initial greeting followed by Vector, ignores bots and ordinary messages, caps requests at three per authenticated principal and twelve globally per minute, bounds event memory, and rejects duplicates for five minutes. The future authenticated bridge must provide stable source identities and the same original event ID for relayed copies. Current limiter is process-local; deployment must use one instance and define restart persistence.

Replies and introduction contain no emoji. INTRODUCTION is prepared text only. Sending it is authorized by the owner after final qualification. A durable delivery record, uncertain-delivery handling and separate channel outcomes are required before enabling it; no automatic resend after uncertain delivery.

Remaining work: authenticated Minecraft/Discord adapter against installed Discord Integration 3.2.1 APIs; verified local-only knowledge and recipe sources for the actual version/modpack; topic and output restrictions; no seed/commands or administrative allegations; local model integration and bounded queue; durable event/introduction state; Discord avatar and version-compatible Minecraft presentation; read-only mounts and network isolation; staging and owner release/rollback. No cloud fallback. Private assistant memory must not enter public game chat.

Validation: ten synthetic Python tests pass locally. No real player data, server scripts, logs or credentials are committed. No server or model calls made by these tests.
