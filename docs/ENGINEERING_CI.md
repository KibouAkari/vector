# Engineering checks

Pull requests run a Next.js production build, synthetic unit/API tests, PostgreSQL-backed authorization and usage checks, documentation validation, a source-publication scan and the pinned Gitleaks working-tree scan. The optional Minecraft addon is compiled against its pinned upstream API on Java17 and25 and exercises offline signed transport, identity, replay and policy boundaries.

Tests never require production credentials. Host-specific installers, deployment inventories and their historical qualification reports are private operating material. Removing those installers from the reusable repository does not replace live staging qualification.

Run Node tests with `node --test tests/*.test.mjs` only when the required dependency and database services are available; database-backed entrypoints need the environment shown in the CI workflow. For a targeted change run its meaningful unit tests first. Python policy/runtime tests use synthetic temporary files and mocked local inference; native model quality and actual Minecraft/Discord delivery need separate operator-side qualification.

CI deploys nothing and sends no game messages. A green source build is not evidence that an app image is running or that a real client rendered its resource pack. See [deployment policy](DEPLOYMENT.md) and [publication boundary](PUBLICATION.md).
