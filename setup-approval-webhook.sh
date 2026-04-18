#!/usr/bin/env bash
# ============================================================================
# ALBENI 1905 — Approval Webhook Setup
# Add the approval-webhook as a new Railway service in the existing
# albeni-ai-orchestration project. Designed to be run once after git push.
#
# Prerequisites:
#   - Railway CLI authenticated (railway login done)
#   - Project linked (railway link to albeni-ai-orchestration)
#   - approval-webhook/.env populated (NOTION_TOKEN + WEBHOOK_SECRET)
#   - Changes committed and pushed to origin/main
#
# Usage (from monorepo root):
#   chmod +x setup-approval-webhook.sh && ./setup-approval-webhook.sh
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "\n${BLUE}━━━ STEP $1: $2 ━━━${NC}\n"; }
print_ok()   { echo -e "${GREEN}✓ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_err()  { echo -e "${RED}✗ $1${NC}"; }

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ALBENI 1905 — Approval Webhook Setup                ║"
echo "║   Add approval-webhook service to Railway             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ----------------------------------------------------------------------------
# STEP 1: Prerequisites
# ----------------------------------------------------------------------------
print_step "1" "Verifica prerequisiti"

command -v railway >/dev/null 2>&1 || { print_err "Railway CLI non installata"; exit 1; }
print_ok "Railway CLI: $(railway --version)"

if ! railway whoami &> /dev/null; then
  print_err "Non autenticato su Railway. Esegui: railway login"
  exit 1
fi
print_ok "Railway: loggato come $(railway whoami 2>&1 | tail -1)"

if [[ ! -f approval-webhook/.env ]]; then
  print_err "approval-webhook/.env mancante"
  exit 1
fi
print_ok "approval-webhook/.env presente"

# shellcheck disable=SC1091
source approval-webhook/.env
if [[ -z "${NOTION_TOKEN:-}" || "${NOTION_TOKEN}" == *"PASTE_"* ]]; then
  print_err "NOTION_TOKEN mancante o placeholder"
  exit 1
fi
if [[ -z "${WEBHOOK_SECRET:-}" || "${WEBHOOK_SECRET}" == *"change_me"* ]]; then
  print_err "WEBHOOK_SECRET mancante o placeholder"
  exit 1
fi
print_ok ".env valido (NOTION_TOKEN ${NOTION_TOKEN:0:12}…)"

# ----------------------------------------------------------------------------
# STEP 2: Create Railway service
# ----------------------------------------------------------------------------
print_step "2" "Crea servizio 'approval-webhook' su Railway"

echo "Creo il service (se non esiste già)…"
railway add --service approval-webhook 2>/dev/null || print_warn "Service già esistente — skip"

# ----------------------------------------------------------------------------
# STEP 3: Set environment variables
# ----------------------------------------------------------------------------
print_step "3" "Imposta variabili d'ambiente"

railway variables --service approval-webhook --set "NOTION_TOKEN=$NOTION_TOKEN"
railway variables --service approval-webhook --set "NOTION_DB_ID=$NOTION_DB_ID"
railway variables --service approval-webhook --set "WEBHOOK_SECRET=$WEBHOOK_SECRET"
railway variables --service approval-webhook --set "ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-*}"

print_ok "Variabili settate"

# ----------------------------------------------------------------------------
# STEP 4: Deploy (from approval-webhook/ as root directory)
# ----------------------------------------------------------------------------
print_step "4" "Deploy del service"

(cd approval-webhook && railway up --service approval-webhook --detach)

# ----------------------------------------------------------------------------
# STEP 5: Generate public domain
# ----------------------------------------------------------------------------
print_step "5" "Genera dominio pubblico"

DOMAIN_OUTPUT=$(railway domain --service approval-webhook 2>&1 || true)
echo "$DOMAIN_OUTPUT"

URL=$(echo "$DOMAIN_OUTPUT" | grep -oE 'https://[a-zA-Z0-9.-]+\.up\.railway\.app' | head -1)

if [[ -z "$URL" ]]; then
  print_warn "URL non rilevato automaticamente."
  print_warn "Recuperalo manualmente: railway domain --service approval-webhook"
else
  print_ok "URL pubblico: $URL"
fi

# ----------------------------------------------------------------------------
# STEP 6: Health check
# ----------------------------------------------------------------------------
if [[ -n "$URL" ]]; then
  print_step "6" "Test /health (attendo 30s perché Railway fa il build)"
  sleep 30
  if curl -sf "$URL/health" > /tmp/health.json; then
    print_ok "Health OK:"
    cat /tmp/health.json
    echo ""
  else
    print_warn "Health check ancora non risponde. Controlla: railway logs -s approval-webhook"
  fi
fi

# ----------------------------------------------------------------------------
# Wrap up
# ----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Setup completato.${NC}"
echo ""
if [[ -n "$URL" ]]; then
  echo "  URL webhook: ${BLUE}$URL${NC}"
  echo ""
  echo "  Aggiorna tools/dashboard-generator/.env con:"
  echo "    WEBHOOK_URL=$URL"
  echo ""
  echo "  Poi:"
  echo "    cd tools/dashboard-generator"
  echo "    pip install -r requirements.txt"
  echo "    python generate.py --open"
fi
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
