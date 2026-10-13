# Vector Roadmap

This document describes planned milestones,
not a claim that every feature has shipped.

| Phase | Focus |
| --- | --- |
| 5.9.0 | Current architecture and test inventory |
| 5.9.1 | Provider gateway, routing, telemetry and fallback |
| 5.9.2 | Fast, artifact and agent execution paths |
| 5.10 | Artifact studio, previews and file editing |
| 5.11 | Multi-agent workflows and sandbox execution |
| 5.12 | Skill registry, evaluations and self-improvement |
| 5.13 | Email, WhatsApp, Discord, Minecraft and users |
| 5.14 | Voice, home automation and video |

## Quality measurements

Every major release should measure:

- Task completion and correctness.
- P50 and P95 latency.
- Actual cost per task in CHF.
- Provider and tool reliability.
- Retry and fallback performance.
- Security and privacy violations.
- Approval handling and duplicate side effects.

## Release requirements

Implementation, tests, evaluation, documented rollback
and approval before production release.
