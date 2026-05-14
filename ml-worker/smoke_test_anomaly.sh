#!/usr/bin/env bash
# Smoke test Anomaly Detection v0 — Step 3b
# Uso: API_KEY=albeni1905-internal-api-v1 ./smoke_test_anomaly.sh
# Test locale: BASE=http://localhost:8000 ./smoke_test_anomaly.sh

set -euo pipefail

BASE="${BASE:-https://albeni-ai-orchestration-production.up.railway.app}"
KEY="${API_KEY:-albeni1905-internal-api-v1}"

pass=0; fail=0
section() { echo; echo "── $1 ──"; }
check()   { if [[ "$1" == "$2" ]]; then echo "  PASS · $3"; pass=$((pass+1)); else echo "  FAIL · $3 (got=$1 expected=$2)"; fail=$((fail+1)); fi; }

section "1) GET /v1/anomaly/alerts senza auth → 200 (read-only)"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/v1/anomaly/alerts?days=7")
check "$code" "200" "lettura alert pubblica"

section "2) Risposta struttura"
body=$(curl -s "$BASE/v1/anomaly/alerts?days=7")
echo "$body" | python3 -m json.tool | head -15
for f in total counts alerts window_days; do
  echo "$body" | grep -q "\"$f\":" && { echo "  PASS · field '$f' present"; pass=$((pass+1)); } || { echo "  FAIL · field '$f' missing"; fail=$((fail+1)); }
done

section "3) POST /v1/anomaly/snapshot senza auth → 401"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/v1/anomaly/snapshot")
check "$code" "401" "snapshot trigger richiede auth"

section "4) POST /v1/anomaly/snapshot con auth → 200 + struttura"
body=$(curl -s -X POST "$BASE/v1/anomaly/snapshot" -H "x-api-key: $KEY")
echo "$body" | python3 -m json.tool | head -40
echo "$body" | grep -q '"status":"ok"' && { echo "  PASS · status ok"; pass=$((pass+1)); } || { echo "  FAIL · missing ok"; fail=$((fail+1)); }
echo "$body" | grep -q '"snapshot"' && { echo "  PASS · snapshot block"; pass=$((pass+1)); } || { echo "  FAIL"; fail=$((fail+1)); }
echo "$body" | grep -q '"detection"' && { echo "  PASS · detection block"; pass=$((pass+1)); } || { echo "  FAIL"; fail=$((fail+1)); }

section "5) GET /v1/anomaly/baseline?metric=cpa_7d → 200"
body=$(curl -s "$BASE/v1/anomaly/baseline?metric=cpa_7d&days=14")
echo "$body" | python3 -c "import sys,json;d=json.load(sys.stdin);print('  metric:',d['metric'],'snaps:',len(d.get('snapshots',[])),'avg:',d.get('avg'))"
echo "$body" | grep -q '"metric":"cpa_7d"' && { echo "  PASS · baseline structure"; pass=$((pass+1)); } || { echo "  FAIL"; fail=$((fail+1)); }

section "6) Idempotenza snapshot — rerun stesso giorno"
body1=$(curl -s -X POST "$BASE/v1/anomaly/snapshot" -H "x-api-key: $KEY")
sleep 1
body2=$(curl -s -X POST "$BASE/v1/anomaly/snapshot" -H "x-api-key: $KEY")
n1=$(echo "$body1" | python3 -c "import sys,json;print(json.load(sys.stdin)['snapshot']['written'])")
n2=$(echo "$body2" | python3 -c "import sys,json;print(json.load(sys.stdin)['snapshot']['written'])")
check "$n1" "$n2" "stesso numero di KPI scritti ai due rerun ($n1 vs $n2)"

section "7) Min severity filter"
all=$(curl -s "$BASE/v1/anomaly/alerts?days=7&min_severity=INFO" | python3 -c "import sys,json;print(json.load(sys.stdin)['total'])")
crit=$(curl -s "$BASE/v1/anomaly/alerts?days=7&min_severity=CRITICAL" | python3 -c "import sys,json;print(json.load(sys.stdin)['total'])")
[[ "$crit" -le "$all" ]] && { echo "  PASS · CRITICAL count ($crit) ≤ INFO count ($all)"; pass=$((pass+1)); } || { echo "  FAIL"; fail=$((fail+1)); }

echo
echo "════════════════════════════════════════"
echo "  PASSED: $pass · FAILED: $fail"
echo "════════════════════════════════════════"
exit $fail
