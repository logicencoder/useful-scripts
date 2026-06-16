#!/usr/bin/env bash
# Generate sitemap + ping search engines via remote wp-cli.
set -euo pipefail

SSH_TARGET="${HOSTINGER_SSH:-}"
WP_ROOT="${WP_REMOTE_ROOT:-}"

if [[ -z "${SSH_TARGET}" || -z "${WP_ROOT}" ]]; then
  cat >&2 <<'EOF'
Regenerate Logic Encoder sitemap and ping engines on Hostinger.

Required:
  HOSTINGER_SSH
  WP_REMOTE_ROOT
EOF
  exit 2
fi

remote_cmd=$(cat <<'EOS'
set -e
cd "$WP_ROOT"
if wp help sitemap 2>/dev/null | grep -q generate; then
  wp sitemap generate
else
  wp eval 'if (function_exists("logicencoder_sitemap_generate")) { logicencoder_sitemap_generate(); echo "logicencoder_sitemap_generate OK\n"; } else { echo "No sitemap generator hook found\n"; }'
fi
if wp help sitemap 2>/dev/null | grep -q ping; then
  wp sitemap ping || true
fi
echo "done"
EOS
)

ssh "${SSH_TARGET}" "WP_ROOT=$(printf '%q' "${WP_ROOT}") bash -s" <<< "${remote_cmd}"
