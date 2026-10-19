# Deployment boundary

A repository merge is not a production release. CI builds and tests synthetic fixtures; it has no deployment step. Host-side automation, Git polling, image update services and third-party triggers must be audited separately before unattended deployment is considered.

Before a web release, inspect the actual app and worker images, code mounts, Compose configuration and health endpoints without printing environment values or secrets. `scripts/diagnostics/web-release-readiness.py` is a read-only starting inventory. It changes no containers, databases, model state or game configuration; concurrent live changes invalidate its unchanged-state check. Source files may be absent inside a standalone Next.js image, so null source hashes are not proof of a mismatch or a matching revision.

Prepare a concrete release plan against that observed baseline. Pin the source and image; use locked dependencies, isolated qualification with synthetic data and a disposable database, fresh configuration backups, health checks and a rollback that verifies its own scope. Preserve listener binding on all intended interfaces. Check whether a separate worker consumes changed source before calling a change app-only.

Do not migrate or restore a production database as an incidental part of a web update. Do not rebuild/restart Minecraft, its assistant, local inference, backups or private networks in a web rollout. The generic Minecraft source layout/configuration is not an automatic migration of an existing pinned installation.

Keep deployed image IDs, host paths, manifests, source hashes, operator approvals and rollback records in private operating material. Never edit release evidence to bypass a rollback guard. See [security](SECURITY.md), [engineering checks](ENGINEERING_CI.md) and [Minecraft deployment boundaries](MINECRAFT.md).

## Isolated web candidate

`scripts/deploy/stage-web-recovery.py` accepts explicit operator paths, container names, an exact revision/native image and a private read-only readiness JSON baseline. It exports that revision, builds a fresh application image with the locally pinned Node base and enforced CPU/memory limits, and qualifies the built API with synthetic users, a disposable PostgreSQL database and an offline native privacy service. Original submission, separate tool masking, replacement, privacy-off, ownership and detector outage are included. Queued jobs are not executed and no cloud credentials or live data mounts enter the fixture.

The stage retains a candidate image and private evidence. It never updates source, Compose or a production container. All-container fingerprints and source/configuration hashes must stay unchanged; temporary containers, network and synthetic secrets must be removed. Native qualification holds the existing cooperative CPU slot so concurrent local inference can report busy. Image builds are bounded separately. A successful stage is a prerequisite for a later guarded release, not a live fix or proof of cloud/provider execution. Docker/native qualification runs on the operator host; synthetic script tests alone do not prove it passed.
