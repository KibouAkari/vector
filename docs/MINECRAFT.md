# Optional Minecraft integration

The bridge consists of a Java DiscordIntegration addon and a separate Python assistant. It is not part of a web app restart. Operators supply their own world, identities, configuration, tokens and model runtime. No real player data or server inventory is distributed here.

## Components

- `integrations/minecraft-addon`: case-insensitive addressed greetings, Minecraft/Discord input hooks and authenticated private delivery.
- `services/minecraft-assistant`: policy filters, replay protection, bounded per-user context, rate limits, statistics, recipe/catalog adapters and local knowledge composition.
- `scripts/build-minecraft-addon.py`: compile and test against the pinned integration API; it installs nothing.
- `scripts/build-minecraft-identity.py`: generate brand-only chat assets. A Minecraft head needs a compatible client resource pack; a Discord avatar needs a reachable PNG and webhook configuration.

Ordinary unaddressed chat is ignored. The service has no command execution API or cloud fallback. Commands and their output, seeds, credentials, administrative state, gamemode and cheating questions remain excluded. Discord display names are not trusted Minecraft identity links. First-person queries require an authenticated Minecraft UUID or a verified operator-managed link.

## Data and knowledge

Mount only the required input files read-only. Persist rate-limit/replay state separately and protect token/DSN files with strict ownership and mode. A restricted database role coordinates the shared local CPU slot; it must not read application data. The deployment must qualify actual database privileges, including inherited PUBLIC grants.

Statistics are read afresh for each query. Rankings require complete saved data and retain ties. Saved files can lag ongoing play. Advancements and item-use counters do not prove who killed whom or how a kill occurred. Humorous portraits must stay grounded in the available game counters.

The generic knowledge pack is a set of reviewed, paraphrased source-backed facts, not proof that every mod, version or server setting is understood. Operators provide their own installed-mod list and recipe catalog. Base recipes are not guaranteed to match a server's effective datapack/mod recipes. Keep source attribution and verify version-specific recipes/settings before claiming certainty.

## Web statistics configuration

These settings belong to the web app's private runtime configuration, never to a chat request:

| Variable | Meaning |
| --- | --- |
| `VECTOR_MINECRAFT_DATA_PATH` | Absolute read-only data root reachable through the existing authorized Host Agent |
| `VECTOR_MINECRAFT_STATS_PATH` | Relative statistics path beneath that root; default `world/players/stats`, adjust to the actual layout |
| `VECTOR_MINECRAFT_SERVER_ALIASES` | Optional comma-separated server labels for intent normalization |

The web adapter reads `usercache.json` and the configured statistics folder. Paths from a user's prompt cannot override this configuration. An unconfigured or incomplete source fails clearly; it is never silently replaced with an invented answer.

## Rollout boundaries

The generic source intentionally uses Minecraft-specific names, role names and example paths. It is not a migration for an existing installation. Do not replace live mounts, secrets or database roles merely because source names changed. Qualify a separate game rollout against the installed API, preserve world/player/mod state and tested backups, and keep rollback evidence. A one-time welcome needs durable replay protection and readiness confirmation. Never replay it during a web release.
