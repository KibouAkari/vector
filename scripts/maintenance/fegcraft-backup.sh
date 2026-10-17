#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 /opt/fegcraft-updated/backup_minecraft.py "$@"
