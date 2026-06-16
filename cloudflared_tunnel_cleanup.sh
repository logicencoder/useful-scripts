#!/usr/bin/env bash
# List (and optionally kill) duplicate cloudflared tunnel processes.
set -euo pipefail

PATTERN="${CLOUDFLARED_PATTERN:-cloudflared}"
KILL="${1:-}"

list_pids() {
  pgrep -af "${PATTERN}" 2>/dev/null | grep -v "cloudflared_tunnel_cleanup" || true
}

echo "=== cloudflared processes (pattern: ${PATTERN}) ==="
ROWS=$(list_pids)
if [[ -z "${ROWS}" ]]; then
  echo "None found."
  exit 0
fi
echo "${ROWS}"

if [[ "${KILL}" != "--kill" ]]; then
  echo ""
  echo "Dry run. Pass --kill to SIGTERM then SIGKILL survivors."
  exit 0
fi

mapfile -t PIDS < <(pgrep -f "${PATTERN}" 2>/dev/null | grep -v "$$" || true)
if [[ ${#PIDS[@]} -eq 0 ]]; then
  echo "Nothing to kill."
  exit 0
fi

echo "Sending SIGTERM to: ${PIDS[*]}"
kill -TERM "${PIDS[@]}" 2>/dev/null || true
sleep 1
for pid in "${PIDS[@]}"; do
  if kill -0 "${pid}" 2>/dev/null; then
    echo "SIGKILL ${pid}"
    kill -KILL "${pid}" 2>/dev/null || true
  fi
done
echo "Done."
