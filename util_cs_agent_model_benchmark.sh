#!/usr/bin/env bash
# Quick model benchmark via le-cs-agent REST API.
set -euo pipefail

API="${CS_AGENT_URL:-http://127.0.0.1:3000}"
MODELS="${CS_AGENT_MODELS:-}"
LIMIT="${CS_AGENT_MODEL_LIMIT:-5}"

echo "=== CS Agent model benchmark ==="
models_json=$(curl -sf "${API}/api/models")
echo "${models_json}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
models = d.get('models') or d.get('data') or []
if isinstance(models, dict):
    models = models.get('data') or []
ids = [m.get('id') for m in models if isinstance(m, dict) and m.get('id')]
print(f'free_models_total={len(ids)}')
for mid in ids[:int('${LIMIT}')]:
    print(f'  - {mid}')
"

if [[ -z "${MODELS}" ]]; then
  MODELS=$(echo "${models_json}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
models = d.get('models') or d.get('data') or []
if isinstance(models, dict):
    models = models.get('data') or []
ids = [m.get('id') for m in models if isinstance(m, dict) and m.get('id')]
print(','.join(ids[:int('${LIMIT}')]))
")
fi

IFS=',' read -ra arr <<< "${MODELS}"
ok=0
fail=0
for model in "${arr[@]}"; do
  [[ -z "${model}" ]] && continue
  echo "Testing ${model}…"
  if resp=$(curl -sf -X POST "${API}/api/test-one" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"${model}\",\"prompt\":\"Reply with exactly: OK\"}" 2>/dev/null); then
    if echo "${resp}" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)"; then
      ms=$(echo "${resp}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('latency_ms','?'))")
      echo "  OK ${ms}ms"
      ok=$((ok+1))
    else
      echo "  FAIL ${resp}" | head -c 200
      echo ""
      fail=$((fail+1))
    fi
  else
    echo "  FAIL request error"
    fail=$((fail+1))
  fi
done

echo "SUMMARY ok=${ok} fail=${fail}"
[[ "${fail}" -eq 0 ]]
