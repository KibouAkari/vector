# Production app source and Compose pinning

This one-time maintenance procedure aligns the host's app build source with
the application image already deployed from the reviewed **9b405f9** release.
It is not an application deployment and it makes no changes to databases,
worker, runner, Redis, external providers, or mounted encrypted file storage.

## Why

The original production Compose service has no `image:` and builds from
`/opt/vector/app`, which contains an older application snapshot. The
currently running `vector-app` comes from a previously validated versioned
image and an override stored in a timestamped release directory. Running
Compose against the base file alone could therefore rebuild old code.

## Safety

- Script: `scripts/deploy/pin-live-app-595.py`
- Guarded git revision: `9b405f95862e14335a2693b2026e75970e9b123c`
- Guarded current Docker image ID: `sha256:2bc46ad8e4f0a181374873465f2208f99fa09153d00cce082cb837a8a0ac85e2`
- Guarded image tag: `vector-app:staging-9b405f9-20261014T154943Z-2943147`
- The script does **not** run `docker compose up`, `docker build`,
  migrations, or any provider request.
- Both the original app source directory and Compose file are preserved.
- The candidate Compose output is compared to the original and must differ
  only by the app image. Runtime Compose settings are not re-rendered manually.
- No untracked host files or folders are deleted by the source overlay.
- Backup and temporary Compose files may contain confidential configuration
  and must remain restricted to root.

## Operation

From the production host, confirm that the tested 9b405f9 app is still
running, the source checkout is clean, and all background jobs are idle.

Fetch the branch carrying this audited script *without changing the main
checkout* and review the script before execution.

```bash
git -C /root/vector-workspace/github/vector fetch origin ops/persistent-app-pinning-20261014
git -C /root/vector-workspace/github/vector show FETCH_HEAD:scripts/deploy/pin-live-app-595.py \
  > /root/vector-workspace/current/vector-595-persistent-source-pin.py
python3 -m py_compile /root/vector-workspace/current/vector-595-persistent-source-pin.py
python3 /root/vector-workspace/current/vector-595-persistent-source-pin.py
```

If any preflight fails, do not bypass it. The script preserves the running
app and refuses a changed image, checkout, Compose configuration, or topology.

After a successful run, the original source is retained under
`/opt/vector/.vector-app-backup-<UTC timestamp>`, and a restricted
manifest plus the original Compose file are saved under
`/root/vector-workspace/releases/vector-595-persistent-<UTC timestamp>`.

## Production status (2026-10-14)

The operator ran the previously reviewed `083bbd2` revision of this
maintenance script successfully after the 5.9.5 application release.
The reported outcome was a synchronized app source directory, a versioned
image pin in base Compose and no container recreation. Backups were saved
with UTC timestamp `20261014T204744Z`.

Review feedback subsequently hardened the script to reject additional mount
and build-context overlaps and to preserve Compose backup consistency and
permissions. **Do not rerun it against an already pinned installation**:
the preflight intentionally rejects a base Compose service with an image.
Instead, verify the source hashes, running image, base Compose image, and
backup existence read-only before making further changes.

## Future releases

The image pin remains intentionally versioned. For a later reviewed release,
update both the source snapshot and the app image pin together using an
equivalent staging, backup, and rollback gate. Avoid unreviewed
`docker compose up --build` and never rely on a timestamped deployment
override as the only durable source of the image version.
