#!/usr/bin/env bash
# Deploy Logic Encoder theme files and purge WordPress caches on remote host.
set -euo pipefail

THEME_SRC="${WP_THEME_SRC:-}"
REMOTE="${WP_THEME_REMOTE:-}"
SSH_BIN="${WP_DEPLOY_SSH:-ssh}"
WP_CLI="${WP_CLI_CMD:-wp}"
REMOTE_WP_ROOT="${WP_REMOTE_ROOT:-}"

if [[ -z "${THEME_SRC}" || -z "${REMOTE}" ]]; then
  cat >&2 <<'EOF'
Deploy Logic Encoder theme + cache purge.

Required:
  WP_THEME_SRC       local theme directory
  WP_THEME_REMOTE    user@host:/path/to/wp-content/themes/logic-encoder-theme

Optional:
  WP_DEPLOY_SSH      full ssh command prefix (default: ssh)
  WP_REMOTE_ROOT     WordPress root on remote for wp-cli (auto-guessed if empty)
  WP_CLI_CMD         wp command name (default: wp)
EOF
  exit 2
fi

echo "Rsync ${THEME_SRC}/ -> ${REMOTE}/"
rsync -av --delete \
  -e "${SSH_BIN}" \
  --exclude='.git/' \
  --exclude='node_modules/' \
  --exclude='tests/' \
  "${THEME_SRC}/" "${REMOTE}/"

HOST="${REMOTE%%:*}"
REMOTE_PATH="${REMOTE#*:}"

if [[ -z "${REMOTE_WP_ROOT}" ]]; then
  REMOTE_WP_ROOT="$(dirname "$(dirname "${REMOTE_PATH}")")"
fi

echo "Cache purge on ${HOST} (WP root ${REMOTE_WP_ROOT})"
${SSH_BIN} "${HOST}" "cd '${REMOTE_WP_ROOT}' && ${WP_CLI} cache flush 2>/dev/null; ${WP_CLI} litespeed-purge all 2>/dev/null; echo done"

echo "Finished."
