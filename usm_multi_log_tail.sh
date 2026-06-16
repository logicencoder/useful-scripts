#!/usr/bin/env bash
# Tail log files for a USM services.yaml group (default: webapps).
set -euo pipefail

YAML="${USM_SERVICES_YAML:-}"
GROUP="${1:-webapps}"
HOST="${USM_SMOKE_HOST:-127.0.0.1}"
SSH_WRAP="${USM_SSH_CMD:-}"

if [[ -z "${YAML}" || ! -f "${YAML}" ]]; then
  echo "Usage: USM_SERVICES_YAML=/path/to/services.yaml $0 [group]" >&2
  echo "Optional: USM_SSH_CMD='ssh sol@host' to tail on remote host" >&2
  exit 2
fi

mapfile -t LOGS < <(python3 - "$YAML" "$GROUP" <<'PY'
import sys, yaml
path, group = sys.argv[1], sys.argv[2]
with open(path) as f:
    data = yaml.safe_load(f) or {}
for name, cfg in sorted((data.get("services") or {}).items()):
    if cfg.get("group") != group:
        continue
    log_file = cfg.get("log_file")
    if log_file:
        print(f"{name}|{log_file}")
PY
)

if [[ ${#LOGS[@]} -eq 0 ]]; then
  echo "No log_file entries for group: ${GROUP}" >&2
  exit 1
fi

echo "Tailing ${#LOGS[@]} logs (group=${GROUP}). Ctrl+C to stop."
for entry in "${LOGS[@]}"; do
  name="${entry%%|*}"
  file="${entry#*|}"
  if [[ -n "${SSH_WRAP}" ]]; then
    ${SSH_WRAP} "tail -n 0 -F '${file}'" 2>/dev/null | sed -u "s/^/[${name}] /" &
  else
    tail -n 0 -F "${file}" 2>/dev/null | sed -u "s/^/[${name}] /" &
  fi
done
wait
