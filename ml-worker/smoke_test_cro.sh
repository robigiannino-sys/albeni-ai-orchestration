#!/usr/bin/env bash
# Smoke test CRO Engine — Step 7.1 + 7.2
# Uso: API_KEY=albeni1905-internal-api-v1 ./smoke_test_cro.sh
set -euo pipefail

BASE="${BASE:-https://albeni-ai-orchestration-production.up.railway.app}"
KEY="${API_KEY:-albeni1905-internal-api-v1}"
SLOT_KEY="smoke_test_slot_$(date +%s)"
pass=0; fail=0

section() { echo; echo "── $1 ──"; }
check()   { if [[ "$1" == "$2" ]]; then echo "  PASS · $3"; pass=$((pass+1)); else echo "  FAIL · $3 (got=$1 expected=$2)"; fail=$((fail+1)); fi; }

section "1) Create slot senza auth → 401"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/v1/cro/slot" \
    -H "Content-Type: application/json" -d "{\"slot_key\":\"x\"}")
check "$code" "401" "missing auth rejected"

section "2) Create slot con auth"
body=$(curl -s -X POST "$BASE/v1/cro/slot" -H "x-api-key: $KEY" -H "Content-Type: application/json" \
    -d "{\"slot_key\":\"$SLOT_KEY\",\"description\":\"smoke test slot\"}")
echo "  body: $body"
echo "$body" | grep -q '"status":"created"' && { echo "  PASS · created"; pass=$((pass+1)); } || { echo "  FAIL"; fail=$((fail+1)); }

section "3) Create 3 variants"
for i in 1 2 3; do
  curl -s -X POST "$BASE/v1/cro/variant" -H "x-api-key: $KEY" -H "Content-Type: application/json" \
    -d "{\"slot_key\":\"$SLOT_KEY\",\"variant_key\":\"v$i\",\"text\":\"Variant $i text\",\"language\":\"it\"}" > /tmp/cro_v$i.json
done
n=$(ls /tmp/cro_v*.json 2>/dev/null | wc -l | tr -d ' ')
check "$n" "3" "created 3 variants"

section "4) GET microcopy ritorna 1 variant + exposure_id"
body=$(curl -s "$BASE/v1/cro/microcopy?slot=$SLOT_KEY&language=it&user_id=smoketest")
echo "  body: $body"
exp_id=$(echo "$body" | python3 -c "import sys,json;print(json.load(sys.stdin).get('exposure_id') or '')")
[ -n "$exp_id" ] && { echo "  PASS · exposure_id=$exp_id"; pass=$((pass+1)); } || { echo "  FAIL · no exposure_id"; fail=$((fail+1)); }

section "5) POST conversion linkata all'exposure"
body=$(curl -s -X POST "$BASE/v1/cro/conversion" -H "x-api-key: $KEY" -H "Content-Type: application/json" \
    -d "{\"exposure_id\":$exp_id,\"conversion_type\":\"smoke_lead\",\"value_eur\":10.0}")
echo "  body: $body"
echo "$body" | grep -q '"status":"ok"' && { echo "  PASS · conversion recorded"; pass=$((pass+1)); } || { echo "  FAIL"; fail=$((fail+1)); }

section "6) Stats per slot — la variant convertita ha cr > 0"
body=$(curl -s "$BASE/v1/cro/stats?slot=$SLOT_KEY")
echo "$body" | python3 -m json.tool | head -30
total_exp=$(echo "$body" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['slots'][0]['total_exposures'] if d['slots'] else 0)")
total_conv=$(echo "$body" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['slots'][0]['total_conversions'] if d['slots'] else 0)")
[ "$total_exp" = "1" ] && [ "$total_conv" = "1" ] && { echo "  PASS · stats coerenti (1 exp, 1 conv)"; pass=$((pass+1)); } || { echo "  FAIL"; fail=$((fail+1)); }

section "7) Conversion idempotente — re-POST stessa exposure → already_converted"
body=$(curl -s -X POST "$BASE/v1/cro/conversion" -H "x-api-key: $KEY" -H "Content-Type: application/json" \
    -d "{\"exposure_id\":$exp_id,\"conversion_type\":\"duplicate_attempt\"}")
echo "$body" | grep -q '"status":"already_converted"' && { echo "  PASS · idempotent"; pass=$((pass+1)); } || { echo "  FAIL"; fail=$((fail+1)); }

section "8) Slot non esistente → 404"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/v1/cro/stats?slot=nonexistent_slot_xyz")
check "$code" "404" "non-existent slot returns 404"

# Cleanup teardown nota: i dati smoke restano in DB. Per pulizia: DELETE WHERE slot_id = X.

echo
echo "════════════════════════════════════════"
echo "  PASSED: $pass · FAILED: $fail"
echo "════════════════════════════════════════"
rm -f /tmp/cro_v*.json
exit $fail
