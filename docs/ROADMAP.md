# Roadmap

> Planned milestones do not imply delivered features.

| Phase | Focus | Success condition |
| :-- | :-- | :-- |
| 5.9.0 | Architecture baseline | Representative evaluation tasks |
| 5.9.1 | Provider gateway and routing | Measured quality, costs and safe fallback |
| 5.9.2 | Event and execution model | Fast, artifact and agent paths |
| 5.10 | Artifact Studio | Previews, batches and accurate editing |
| 5.11 | Agent orchestration | Verified isolated execution |
| 5.12 | Skills and self-improvement | Evaluated, approval-gated changes |
| 5.13 | Channels and users | Email, WhatsApp, Discord, Minecraft, quotas |
| 5.14 | Multimodal | Voice, home automation, future video |

## Evaluation gates

- Task correctness and completion rate.
- P50 and P95 latency.
- Actual cost per task in CHF.
- Provider and tool availability.
- Retry and fallback safety.
- Privacy violations and duplicate side effects.
- Accessibility and rollback readiness.

## Immediate priority

Audit existing routing behavior, then compare gateway
candidates before changing production traffic.
