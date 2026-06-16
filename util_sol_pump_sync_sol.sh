#!/usr/bin/env bash
# Sync sol-pump-app to SOL — configure paths via env (no hardcoded operator IPs in repo).
set -euo pipefail

SRC="${SOL_PUMP_SRC:-$HOME/sol-pump-app}"
DST="${SOL_PUMP_DST:-}"
SSH_KEY="${SOL_PUMP_SSH_KEY:-}"
SSH_HOST="${SOL_PUMP_SSH_HOST:-}"
REMOTE_DIR="${SOL_PUMP_REMOTE_DIR:-/home/sol/lojzo/sol-pump-app}"
POST_CHECK="${SOL_PUMP_SSH_CMD:-}"

if [[ -z "${DST}" ]]; then
  if [[ -n "${SSH_HOST}" ]]; then
    DST="${SSH_HOST}:${REMOTE_DIR}/"
  else
    echo "Set SOL_PUMP_DST=user@host:/path/ or SOL_PUMP_SSH_HOST" >&2
    exit 2
  fi
fi

RSYNC_SSH=()
if [[ -n "${SSH_KEY}" ]]; then
  RSYNC_SSH=(-e "ssh -i ${SSH_KEY} -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no")
fi

echo "Sync ${SRC}/ -> ${DST}"
rsync -av --delete "${RSYNC_SSH[@]}" \
  --exclude='.venv/' \
  --exclude='logs/' \
  --exclude='data/watchlist.json' \
  --exclude='wallet.json' \
  --exclude='credentials.json' \
  --exclude='.env' \
  --exclude='reports/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  "${SRC}/" "${DST}"

if [[ -n "${POST_CHECK}" ]]; then
  ${POST_CHECK} bash -s <<REMOTE
set -euo pipefail
cd "${REMOTE_DIR}"
chmod +x setup-sol-pump-venv.sh start-sol-pump.sh stop-sol-pump.sh scripts/*.sh 2>/dev/null || true
mkdir -p data logs reports
du -sh .
REMOTE
fi

echo "Done."
