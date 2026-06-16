#!/usr/bin/env bash
# Health → process job → poll until done (env-based wrapper).
set -euo pipefail

API="${KARAOKE_API:-http://127.0.0.1:8765}"
JOB_ID="${1:-${KARAOKE_JOB_ID:-}}"
MODEL="${KARAOKE_MODEL:-tiny}"
LANG="${KARAOKE_LANG:-en}"
MAX_POLLS="${KARAOKE_MAX_POLLS:-90}"

if [[ -z "${JOB_ID}" ]]; then
  echo "Usage: KARAOKE_JOB_ID=<id> $0" >&2
  echo "   or: $0 <job_id>" >&2
  exit 2
fi

echo "Health: $(curl -sf "${API}/health")"
echo "Process job ${JOB_ID} (model=${MODEL}, lang=${LANG})…"
curl -sf -X POST "${API}/jobs/${JOB_ID}/process" \
  -H 'Content-Type: application/json' \
  -d "{\"language\":\"${LANG}\",\"model\":\"${MODEL}\"}"
echo ""

for i in $(seq 1 "${MAX_POLLS}"); do
  st=$(curl -sf "${API}/jobs/${JOB_ID}")
  status=$(echo "${st}" | python3 -c "import sys,json; s=json.load(sys.stdin); p=s.get('progress',{}); print(s.get('status','?'), p.get('overall',''), p.get('step',''))")
  echo "[${i}] ${status}"
  if echo "${st}" | python3 -c "import sys,json; s=json.load(sys.stdin); raise SystemExit(0 if s.get('status') in ('done','error') else 1)"; then
    break
  fi
  sleep 2
done

echo "--- final ---"
curl -sf "${API}/jobs/${JOB_ID}" | python3 -m json.tool | head -30
