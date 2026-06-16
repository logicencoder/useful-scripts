#!/usr/bin/env bash
# Tail common Hostinger / WordPress debug logs over SSH.
set -euo pipefail

SSH_TARGET="${HOSTINGER_SSH:-}"
WP_ROOT="${WP_REMOTE_ROOT:-}"
LOGS="${HOSTINGER_LOG_FILES:-debug.log wp-content/debug.log wp-content/wp-visitor-stats-debug.log}"

if [[ -z "${SSH_TARGET}" || -z "${WP_ROOT}" ]]; then
  cat >&2 <<'EOF'
Tail WordPress debug logs on remote Hostinger host.

Required:
  HOSTINGER_SSH     ssh target (user@host)
  WP_REMOTE_ROOT    absolute WordPress root on remote

Optional:
  HOSTINGER_LOG_FILES   space-separated log paths relative to WP root
EOF
  exit 2
fi

paths=()
for rel in ${LOGS}; do
  paths+=("${WP_ROOT%/}/${rel}")
done

echo "Tailing: ${paths[*]}"
exec ssh "${SSH_TARGET}" "tail -n 80 -F $(printf '%q ' "${paths[@]}")"
