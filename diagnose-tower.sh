#!/bin/bash
# =============================================================
# Albeni 1905 — AI Control Tower Diagnostica & Restart
# Verifica lo stato dei container Docker e riavvia se necessario
#
# Uso:  chmod +x diagnose-tower.sh && ./diagnose-tower.sh
# =============================================================

set -uo pipefail

STACK_DIR="$HOME/Desktop/ALBENI/albeni.com/STEFANO/AI STACK APP/ai-orchestration-layer"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Albeni 1905 — Control Tower Diagnostica"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── 0. Check Docker ──────────────────────────────────────────
echo -e "${CYAN}[1/6] Verifico Docker Desktop...${NC}"
if ! command -v docker &> /dev/null; then
  echo -e "${RED}✗ Docker non trovato. Installa Docker Desktop per Mac.${NC}"
  exit 1
fi

if ! docker info &> /dev/null; then
  echo -e "${RED}✗ Docker non è in esecuzione. Avvia Docker Desktop.${NC}"
  echo "  → Apri Docker Desktop dall'Applications folder"
  exit 1
fi
echo -e "${GREEN}✓${NC} Docker Desktop attivo"

# ── 1. Check stack directory ─────────────────────────────────
echo ""
echo -e "${CYAN}[2/6] Verifico cartella stack...${NC}"
if [ ! -d "$STACK_DIR" ]; then
  echo -e "${RED}✗ Cartella non trovata:${NC} $STACK_DIR"
  exit 1
fi

if [ ! -f "$STACK_DIR/docker-compose.yml" ]; then
  echo -e "${RED}✗ docker-compose.yml non trovato${NC}"
  exit 1
fi
echo -e "${GREEN}✓${NC} Stack directory OK"

# ── 2. Check container status ────────────────────────────────
echo ""
echo -e "${CYAN}[3/6] Stato container...${NC}"
cd "$STACK_DIR"

CONTAINERS=$(docker compose ps --format json 2>/dev/null || docker-compose ps 2>/dev/null)
if [ $? -ne 0 ]; then
  echo -e "${YELLOW}⚠${NC} Nessun container attivo. I container non sono mai stati avviati o sono stati rimossi."
  echo ""
  echo -e "${CYAN}[FIX] Avvio lo stack completo...${NC}"
  docker compose up -d --build 2>&1
  echo ""
  echo -e "${CYAN}Attendo 15 secondi per l'avvio...${NC}"
  sleep 15
  docker compose ps
  echo ""
  echo -e "${GREEN}Stack avviato. Prova:${NC} http://localhost:3000"
  exit 0
fi

echo "$CONTAINERS"
echo ""

# Check each service
for SVC in albeni-ai-router albeni-ml-worker albeni-db albeni-redis; do
  STATUS=$(docker inspect --format='{{.State.Status}}' "$SVC" 2>/dev/null)
  if [ $? -ne 0 ]; then
    echo -e "${RED}✗${NC} $SVC — non trovato"
  elif [ "$STATUS" = "running" ]; then
    echo -e "${GREEN}✓${NC} $SVC — running"
  else
    echo -e "${RED}✗${NC} $SVC — $STATUS"
  fi
done

# ── 3. Check ports ───────────────────────────────────────────
echo ""
echo -e "${CYAN}[4/6] Verifico porte...${NC}"
for PORT in 3000 8000 5432 6379; do
  if lsof -i :$PORT &>/dev/null; then
    PROC=$(lsof -i :$PORT -t 2>/dev/null | head -1)
    echo -e "${GREEN}✓${NC} Porta $PORT — in uso (PID: $PROC)"
  else
    echo -e "${RED}✗${NC} Porta $PORT — libera (servizio non attivo)"
  fi
done

# ── 4. Check logs for errors ─────────────────────────────────
echo ""
echo -e "${CYAN}[5/6] Ultimi log ai-router...${NC}"
docker logs --tail 20 albeni-ai-router 2>&1 || echo -e "${RED}Container ai-router non disponibile${NC}"

echo ""
echo -e "${CYAN}[5b/6] Ultimi log ml-worker...${NC}"
docker logs --tail 10 albeni-ml-worker 2>&1 || echo -e "${RED}Container ml-worker non disponibile${NC}"

# ── 5. Offer restart ─────────────────────────────────────────
echo ""
echo -e "${CYAN}[6/6] Azione consigliata...${NC}"

ROUTER_STATUS=$(docker inspect --format='{{.State.Status}}' albeni-ai-router 2>/dev/null)

if [ "$ROUTER_STATUS" != "running" ]; then
  echo -e "${YELLOW}Il router non è attivo. Riavvio lo stack...${NC}"
  docker compose down 2>/dev/null
  docker compose up -d --build 2>&1
  echo ""
  echo "Attendo 15 secondi..."
  sleep 15
  docker compose ps
  echo ""
  echo -e "${GREEN}Stack riavviato. Prova:${NC} http://localhost:3000"
else
  echo -e "${GREEN}Il router è attivo.${NC}"
  echo ""
  echo "Se la pagina non carica, prova:"
  echo "  1. curl http://localhost:3000/health"
  echo "  2. docker compose restart ai-router"
  echo "  3. docker compose down && docker compose up -d --build"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Diagnostica completata"
echo "═══════════════════════════════════════════════════════════"
echo ""
