#!/usr/bin/env bash
# Preflight checks before karaoke render jobs.
set -euo pipefail

API="${KARAOKE_API:-http://127.0.0.1:8765}"
JOBS_DIR="${KARAOKE_JOBS_DIR:-$HOME/le-karaoke-studio/jobs}"

echo "=== Karaoke operator preflight ==="

fail=0
check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "OK  $label"
  else
    echo "FAIL $label"
    fail=1
  fi
}

check "node" node --version
check "python3" python3 --version
check "ffmpeg" ffmpeg -version
check "curl" curl --version

if command -v nvidia-smi >/dev/null 2>&1; then
  echo "OK  nvidia-smi"
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null | sed 's/^/    /' || true
else
  echo "WARN nvidia-smi not found (CPU-only render)"
fi

if [[ -n "${HF_TOKEN:-}" || -n "${HUGGINGFACE_HUB_TOKEN:-}" ]]; then
  echo "OK  HF token env present"
else
  echo "WARN HF_TOKEN / HUGGINGFACE_HUB_TOKEN not set"
fi

if curl -sf "${API}/health" >/dev/null; then
  echo "OK  karaoke API ${API}/health"
else
  echo "FAIL karaoke API ${API}/health"
  fail=1
fi

if [[ -d "${JOBS_DIR}" ]]; then
  echo "OK  jobs dir ${JOBS_DIR}"
else
  echo "WARN jobs dir missing: ${JOBS_DIR}"
fi

exit "${fail}"
