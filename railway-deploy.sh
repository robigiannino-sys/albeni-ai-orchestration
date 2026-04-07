#!/bin/bash
# ============================================================
# ALBENI 1905 — Quick Deploy to Railway
# Usa questo script per push rapidi dopo il setup iniziale.
# Uso: ./railway-deploy.sh "messaggio commit"
# ============================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

MSG="${1:-deploy: update AI Orchestration Layer}"

echo -e "${BLUE}━━━ ALBENI 1905 — Railway Deploy ━━━${NC}"
echo ""

# Sync dashboard to ai-router (needed for Railway monorepo build)
if [ -f "./railway-prebuild.sh" ]; then
    bash ./railway-prebuild.sh
fi

# Check for changes
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo -e "${YELLOW}⚠ Nessuna modifica rilevata. Niente da deployare.${NC}"
    exit 0
fi

# Show what changed
echo "Modifiche rilevate:"
git status --short
echo ""

# Stage, commit, push
git add -A
git commit -m "$MSG"
git push

echo ""
echo -e "${GREEN}✓ Push completato — Railway auto-deploy attivato!${NC}"
echo ""
echo "Monitora il deploy:"
echo "  railway logs -s ml-worker"
echo "  railway logs -s ai-router"
echo "  railway open"
echo ""

# Quick health check after 30s
echo "Attendo 60 secondi per il build e poi verifico..."
echo "(Premi Ctrl+C per saltare la verifica)"
sleep 60

# Try to get the Railway domain
DOMAIN=$(railway domain 2>/dev/null || echo "")
if [ -n "$DOMAIN" ]; then
    echo "Verifica health endpoint..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✓ ai-router healthy: https://$DOMAIN/health${NC}"
    else
        echo -e "${YELLOW}⚠ Health check returned $HTTP_CODE — il deploy potrebbe essere ancora in corso${NC}"
    fi
fi
