# Coding instructions

Read VISION.md, docs/ARCHITECTURE.md, docs/SECURITY.md, docs/DESIGN_SYSTEM.md and docs/PROJECT_HANDOFF.md before implementation.

1. Work on an isolated branch and preserve existing API contracts and authorization.
2. Keep credentials, real user records, host inventories and deployment diaries outside Git. Use synthetic test fixtures.
3. Prefer direct and deterministic paths where sufficient. Do not introduce orchestration or model calls without need.
4. Test meaningful boundaries: privacy consent, ownership, permissions, routing and failure behavior.
5. Update CHANGELOG.md with accurately verified user-facing and engineering changes. Distinguish source checks from live deployment evidence.
6. Do not deploy, send messages, restart services or change data outside the user's authorized scope.
7. Keep web and Minecraft deployments independent. Source refactoring never authorizes a game rollout.
8. Preserve immutable release evidence and rollback guards. Do not rewrite Git history or publish a repository without explicit authorization.
9. Review external dependencies, licensing and security implications. Never claim success without evidence.
10. Maintain private project-specific handoff material outside this repository. This file contains reusable engineering rules, not personal operating instructions.

11. Preserve the full dated changelog and useful README sections. Extend them; generalize private references narrowly instead of deleting history. Restore verified original assets when appropriate.
