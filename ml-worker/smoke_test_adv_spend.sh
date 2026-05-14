#!/usr/bin/env bash
# Smoke test /v1/adv/spend/* — Step 3a Sessione 1
# Uso: API_KEY=albeni1905-internal-api-v1 BASE=https://albeni-ai-orchestration.up.railway.app ./smoke_test_adv_spend.sh
# Per test locale: BASE=http://localhost:8000 ./smoke_test_adv_spend.sh

set -euo pipefail

BASE="${BASE:-https://albeni-ai-orchestration.up.railway.app}"
KEY="${API_KEY:-albeni1905-internal-api-v1}"
TODAY=$(date -u +%Y-%m-%d)
YDAY=$(date -u -v-1d +%Y-%m-%d 2>/dev/null || date -u -d "yesterday" +%Y-%m-%d)

pass=0; fail=0
section() { echo; echo "── $1 ──"; }
check()   { if [[ "$1" == "$2" ]]; then echo "  PASS · $3"; pass=$((pass+1)); else echo "  FAIL · $3 (got=$1 expected=$2)"; fail=$((fail+1)); fi; }

section "1) Auth: POST senza API key → 401"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/v1/adv/spend/report" \
    -H "Content-Type: application/json" \
    -d "{\"channel\":\"google_ads\",\"date\":\"$TODAY\",\"amount_eur\":10.00}")
check "$code" "401" "missing api key rejected"

section "2) Auth: POST con API key valida → 200"
body=$(curl -s -X POST "$BASE/v1/adv/spend/report" \
    -H "Content-Type: application/json" -H "x-api-key: $KEY" \
    -d "{\"channel\":\"google_ads\",\"date\":\"$TODAY\",\"campaign_id\":\"SMOKE-c001\",\"campaign_name\":\"smoke test\",\"amount_eur\":12.34,\"impressions\":100,\"clicks\":5,\"country\":\"IT\",\"source\":\"smoke_test\"}")
echo "  body: $body"
echo "$body" | grep -q '"status":"ok"' && { echo "  PASS · status ok"; pass=$((pass+1)); } || { echo "  FAIL · missing ok"; fail=$((fail+1)); }

section "3) Validation: channel invalido → 400"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/v1/adv/spend/report" \
    -H "Content-Type: application/json" -H "x-api-key: $KEY" \
    -d "{\"channel\":\"facebook_classic\",\"date\":\"$TODAY\",\"amount_eur\":1}")
check "$code" "400" "unsupported channel rejected"

section "4) Validation: amount negativo → 400"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/v1/adv/spend/report" \
    -H "Content-Type: application/json" -H "x-api-key: $KEY" \
    -d "{\"channel\":\"google_ads\",\"date\":\"$TODAY\",\"amount_eur\":-5}")
check "$code" "400" "negative amount rejected"

section "5) UPSERT: re-POST stessa chiave aggiorna invece di duplicare"
body1=$(curl -s -X POST "$BASE/v1/adv/spend/report" \
    -H "Content-Type: application/json" -H "x-api-key: $KEY" \
    -d "{\"channel\":\"google_ads\",\"date\":\"$TODAY\",\"campaign_id\":\"SMOKE-c001\",\"amount_eur\":99.99,\"source\":\"smoke_test\"}")
total1=$(echo "$body1" | python3 -c "import sys,json;print(json.load(sys.stdin)['total_rows'])")
body2=$(curl -s -X POST "$BASE/v1/adv/spend/report" \
    -H "Content-Type: application/json" -H "x-api-key: $KEY" \
    -d "{\"channel\":\"google_ads\",\"date\":\"$TODAY\",\"campaign_id\":\"SMOKE-c001\",\"amount_eur\":50.00,\"source\":\"smoke_test\"}")
total2=$(echo "$body2" | python3 -c "import sys,json;print(json.load(sys.stdin)['total_rows'])")
check "$total1" "$total2" "row count invariato dopo UPSERT (total $total1 → $total2)"

section "6) Batch: 3 righe in un solo POST"
batch_body=$(cat <<EOF
{"rows":[
  {"channel":"meta_ads","date":"$YDAY","campaign_id":"SMOKE-m001","amount_eur":22.50,"source":"smoke_test"},
  {"channel":"meta_ads","date":"$TODAY","campaign_id":"SMOKE-m002","amount_eur":18.75,"source":"smoke_test"},
  {"channel":"google_ads","date":"$YDAY","campaign_id":"SMOKE-c002","amount_eur":33.00,"source":"smoke_test"}
]}
EOF
)
batch_resp=$(curl -s -X POST "$BASE/v1/adv/spend/batch" \
    -H "Content-Type: application/json" -H "x-api-key: $KEY" \
    -d "$batch_body")
inserted=$(echo "$batch_resp" | python3 -c "import sys,json;print(json.load(sys.stdin)['inserted'])")
check "$inserted" "3" "batch ingest 3 rows"

section "7) GET /v1/adv/spend/summary?days=7 (no auth richiesta)"
summary=$(curl -s "$BASE/v1/adv/spend/summary?days=7")
echo "$summary" | python3 -m json.tool | head -30
spend_total=$(echo "$summary" | python3 -c "import sys,json;print(json.load(sys.stdin)['total_spend_eur'])")
echo "  Total spend 7d: €$spend_total"
echo "$summary" | grep -q '"by_channel"' && { echo "  PASS · summary structure"; pass=$((pass+1)); } || { echo "  FAIL"; fail=$((fail+1)); }

section "8) Filter by channel"
gads=$(curl -s "$BASE/v1/adv/spend/summary?days=30&channel=google_ads" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['filter_channel'])")
check "$gads" "google_ads" "channel filter applied"

echo
echo "════════════════════════════════════════"
echo "  PASSED: $pass · FAILED: $fail"
echo "════════════════════════════════════════"
exit $fail
