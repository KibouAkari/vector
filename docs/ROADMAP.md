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

1. Restore reliable web consent and server investigation paths with regressions for original/replace/off and new tool evidence.
2. Qualify an exact app/worker release against the observed host baseline while preserving the independent Minecraft integration.
3. Measure routing, native cold/warm latency, tool completeness and actual provider costs before changing gateways or orchestration.
4. Add representative task evaluations for conversations, server reads, file work and failure recovery. Preserve ownership and privacy boundaries throughout.
5. Complete history/artifact/license review before any public release; keep deployment evidence private.

## Workspace and harvester delivery

The [workspace plan](WORKSPACE_PLAN.md) defines the proposed source-to-artifact
journey, explicit acceptance gates and candidate integration roles. It supplements
the existing deployment/privacy priorities above; it does not mark the versioned
phases as delivered. First harden project knowledge, then qualify ingestion,
evidence-backed answers, resumable execution, scoped memory and optional studios.

The static public [source importer](SOURCE_INGESTION.md) is implemented in source.
Next qualify ingestion against the live web stack, add document extraction and
source lifecycle controls, then evaluate passage-level citation support.

## Shared platform delivery

The [control/skills/security delivery](PLATFORM_DELIVERY.md) adds protected owner
approvals, project instruction skills and a scoped local evidence/report flow.
It maps the requested integrations to explicit adapter and release requirements.
Live voice, general channels, device installers, parallel agent teams and media
generation are still incomplete. Source inventory is not runtime readiness.

## Free capacity and billing reconciliation

Delivered source controls include free-inference constraints, selective privacy and own-account provider-call pagination. Next runtime gates are native detector qualification and exact app/worker rollout. Organization billing reconciliation, non-inference tool budgets and full channel/device/voice executors remain separate work; unlimited premium capacity is not a release claim.
