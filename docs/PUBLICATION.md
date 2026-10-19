# Publication boundary

A clean current source tree is necessary but does not make a formerly private repository safe to publish.

Before a public release:

1. Run `python3 scripts/check_public_source.py` and the existing Gitleaks check. Supply additional private search terms locally through `--deny-file`; do not commit that file or paste its matches into public issues.
2. Review all branches, tags, Git history, pull request bodies, workflow artifacts, screenshots, release attachments and external links. A source scan does not cover these stores.
3. Export the reviewed tree into a fresh repository/history when historical operating details cannot safely be retained. Do not rewrite or publish the private source repository as a side effect of a documentation change.
4. Review project licensing, dependency notices, documentation provenance and distributable assets. Do not redistribute integration API binaries in the addon.
5. Provide generic configuration examples, versioned release checks and a separately reviewed deployment plan. Keep operator data, real identities, domains, tokens, deployment manifests, source inventories and private preferences outside the public tree.

The `owner` string is an authorization role in the application and database. It is not a person's name and must not be renamed by a publication cleanup. Changelog entries describe product behavior and verified engineering changes; they do not contain private deployment diaries.
