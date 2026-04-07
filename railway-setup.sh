#!/bin/bash
# ============================================================
# ALBENI 1905 — AI Orchestration Layer
# Railway Deployment Setup Script
# ============================================================
# Questo script configura e deploya l'intero sistema su Railway.
# Eseguilo dal terminale nella root del progetto:
#   chmod +x railway-setup.sh && ./railway-setup.sh
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "\n${BLUE}━━━ STEP $1: $2 ━━━${NC}\n"; }
print_ok() { echo -e "${GREEN}✓ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
print_err() { echo -e "${RED}✗ $1${NC}"; }

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ALBENI 1905 — AI Orchestration Layer               ║"
echo "║   Railway Deployment Setup                            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================
# STEP 1: Check Prerequisites
# ============================================================
print_step "1" "Verifica prerequisiti"

# Check Git
if command -v git &> /dev/null; then
    print_ok "Git installato: $(git --version)"
else
    print_err "Git non trovato. Installa Git: https://git-scm.com"
    exit 1
fi

# Check Railway CLI
if command -v railway &> /dev/null; then
    print_ok "Railway CLI installata: $(railway --version)"
else
    print_warn "Railway CLI non trovata. Installazione in corso..."
    if command -v brew &> /dev/null; then
        brew install railway
    elif command -v npm &> /dev/null; then
        npm install -g @railway/cli
    else
        curl -fsSL https://railway.app/install.sh | sh
    fi

    if command -v railway &> /dev/null; then
        print_ok "Railway CLI installata: $(railway --version)"
    else
        print_err "Installazione Railway CLI fallita."
        echo "Installa manualmente: https://docs.railway.app/guides/cli"
        exit 1
    fi
fi

# Check GitHub CLI (optional but recommended)
if command -v gh &> /dev/null; then
    print_ok "GitHub CLI installata: $(gh --version | head -1)"
else
    print_warn "GitHub CLI non installata (opzionale). Installa con: brew install gh"
fi

# ============================================================
# STEP 2: Railway Login
# ============================================================
print_step "2" "Login su Railway"

echo "Verifica login Railway..."
if railway whoami &> /dev/null 2>&1; then
    print_ok "Già loggato su Railway come: $(railway whoami 2>/dev/null)"
else
    echo "Apri il browser per il login..."
    railway login
    if railway whoami &> /dev/null 2>&1; then
        print_ok "Login effettuato: $(railway whoami 2>/dev/null)"
    else
        print_err "Login fallito"
        exit 1
    fi
fi

# ============================================================
# STEP 3: Initialize Git repo (if needed)
# ============================================================
print_step "3" "Inizializzazione repository Git"

if [ -d ".git" ]; then
    print_ok "Repository Git già inizializzato"
else
    git init
    print_ok "Repository Git inizializzato"
fi

# Add all files
git add -A
git status

echo ""
read -p "Vuoi fare il commit iniziale? (y/n): " DO_COMMIT
if [ "$DO_COMMIT" = "y" ]; then
    git commit -m "feat: AI Orchestration Layer - Railway deployment setup

- ML Worker (Python FastAPI): IDS calculator, content generator, SEO agent
- AI Router (Node.js Express): cross-domain routing, tracking, CRM sync
- Dashboard: control tower, behavioral engine, content lake
- Skills data: SEO agent, MT translator/validator/orchestrator, SEMrush
- Railway config: Dockerfile optimized, railway.toml per service"
    print_ok "Commit creato"
fi

# ============================================================
# STEP 4: Create GitHub Repository
# ============================================================
print_step "4" "Creazione repository GitHub"

if git remote get-url origin &> /dev/null 2>&1; then
    REPO_URL=$(git remote get-url origin)
    print_ok "Remote origin già configurato: $REPO_URL"
else
    echo "Creiamo il repo GitHub..."
    read -p "Nome del repository (default: albeni-ai-orchestration): " REPO_NAME
    REPO_NAME=${REPO_NAME:-albeni-ai-orchestration}

    read -p "Repository privato? (y/n, default: y): " IS_PRIVATE
    IS_PRIVATE=${IS_PRIVATE:-y}

    VISIBILITY="--private"
    if [ "$IS_PRIVATE" = "n" ]; then
        VISIBILITY="--public"
    fi

    if command -v gh &> /dev/null; then
        gh repo create "$REPO_NAME" $VISIBILITY --source=. --remote=origin
        print_ok "Repository GitHub creato: $REPO_NAME"
    else
        echo ""
        echo "GitHub CLI non disponibile. Crea il repo manualmente:"
        echo "  1. Vai su https://github.com/new"
        echo "  2. Nome: $REPO_NAME"
        echo "  3. Visibilità: Privato"
        echo "  4. NON aggiungere README, .gitignore o License"
        echo ""
        read -p "Incolla l'URL del repo (es. https://github.com/user/repo.git): " MANUAL_URL
        git remote add origin "$MANUAL_URL"
    fi
fi

# Push to GitHub
echo "Push su GitHub..."
git push -u origin main 2>/dev/null || git push -u origin master 2>/dev/null || {
    BRANCH=$(git branch --show-current)
    git push -u origin "$BRANCH"
}
print_ok "Push completato"

# ============================================================
# STEP 5: Create Railway Project
# ============================================================
print_step "5" "Creazione progetto Railway"

echo "Creazione progetto Railway..."
railway init

print_ok "Progetto Railway creato"
echo ""
echo "Ora collegheremo il repository GitHub al progetto."
echo "Apri la Railway Dashboard e:"
echo "  1. Seleziona il progetto appena creato"
echo "  2. Clicca 'New Service' → 'GitHub Repo'"
echo "  3. Seleziona il repository: $REPO_NAME"
echo ""

# ============================================================
# STEP 6: Add PostgreSQL and Redis
# ============================================================
print_step "6" "Aggiunta database PostgreSQL e Redis"

echo "Aggiunta PostgreSQL al progetto Railway..."
echo "(Questo apre la dashboard — aggiungi PostgreSQL e Redis come plugin)"
echo ""
echo "Nella Railway Dashboard:"
echo "  1. Clicca '+ New' → 'Database' → 'PostgreSQL'"
echo "  2. Clicca '+ New' → 'Database' → 'Redis'"
echo ""
echo "Railway genererà automaticamente:"
echo "  - DATABASE_URL (per PostgreSQL)"
echo "  - REDIS_URL (per Redis)"
echo ""
read -p "Premi INVIO quando hai aggiunto entrambi i database..." _

# ============================================================
# STEP 7: Create Services
# ============================================================
print_step "7" "Configurazione servizi"

echo "╔══════════════════════════════════════════════════════╗"
echo "║  Ora crea i 2 servizi nella Railway Dashboard:       ║"
echo "║                                                       ║"
echo "║  SERVIZIO 1: ml-worker                                ║"
echo "║    → New Service → GitHub Repo → seleziona il repo   ║"
echo "║    → Settings → Root Directory: /ml-worker            ║"
echo "║    → Settings → Port: 8000                            ║"
echo "║                                                       ║"
echo "║  SERVIZIO 2: ai-router                                ║"
echo "║    → New Service → GitHub Repo → seleziona il repo   ║"
echo "║    → Settings → Root Directory: /ai-router            ║"
echo "║    → Settings → Port: 3000                            ║"
echo "║    → Settings → Generate Domain (per URL pubblica)   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
read -p "Premi INVIO quando hai creato entrambi i servizi..." _

# ============================================================
# STEP 8: Set Environment Variables
# ============================================================
print_step "8" "Configurazione variabili d'ambiente"

echo "Configurazione variabili d'ambiente per i servizi..."
echo ""
echo "Per ogni servizio, vai su Variables nella dashboard e aggiungi:"
echo ""

# Read from .env if exists
if [ -f ".env" ]; then
    echo "Trovato file .env — uso i valori esistenti."
    echo ""

    echo "━━━ VARIABILI CONDIVISE (aggiungi a ENTRAMBI i servizi) ━━━"
    echo ""

    # Extract key vars
    GEMINI_KEY=$(grep "^GEMINI_API_KEY=" .env | cut -d'=' -f2-)
    KLAVIYO_KEY=$(grep "^KLAVIYO_API_KEY=" .env | cut -d'=' -f2-)
    KLAVIYO_PUB=$(grep "^KLAVIYO_PUBLIC_KEY=" .env | cut -d'=' -f2-)
    SEMRUSH_KEY=$(grep "^SEMRUSH_API_KEY=" .env | cut -d'=' -f2-)
    NOTION_TOKEN=$(grep "^NOTION_API_TOKEN=" .env | cut -d'=' -f2-)
    JWT_SECRET=$(grep "^JWT_SECRET=" .env | cut -d'=' -f2-)
    API_KEY_VAL=$(grep "^API_KEY=" .env | cut -d'=' -f2-)

    echo "Le seguenti variabili vanno impostate via Dashboard o CLI:"
    echo ""
    echo "railway variables set AI_PROVIDER=gemini"
    echo "railway variables set GEMINI_API_KEY=$GEMINI_KEY"
    echo "railway variables set GEMINI_MODEL=gemini-2.5-flash"
    echo "railway variables set KLAVIYO_API_KEY=$KLAVIYO_KEY"
    echo "railway variables set KLAVIYO_PUBLIC_KEY=$KLAVIYO_PUB"
    echo "railway variables set KLAVIYO_REVISION=2024-02-15"
    echo "railway variables set SEMRUSH_API_KEY=$SEMRUSH_KEY"
    echo "railway variables set NOTION_API_TOKEN=$NOTION_TOKEN"
    echo "railway variables set JWT_SECRET=$JWT_SECRET"
    echo "railway variables set API_KEY=$API_KEY_VAL"
    echo "railway variables set DOMAIN_TOFU=https://worldofmerino.com"
    echo "railway variables set DOMAIN_MOFU=https://merinouniversity.com"
    echo "railway variables set DOMAIN_BOFU_TECH=https://perfectmerinoshirt.com"
    echo "railway variables set DOMAIN_BOFU_HERITAGE=https://albeni1905.com"
    echo ""
    echo "━━━ VARIABILI SPECIFICHE ml-worker ━━━"
    echo "DATABASE_URL → collegata automaticamente da PostgreSQL plugin"
    echo "REDIS_URL → collegata automaticamente da Redis plugin"
    echo ""
    echo "━━━ VARIABILI SPECIFICHE ai-router ━━━"
    echo "ML_WORKER_URL → http://ml-worker.railway.internal:8000"
    echo "REDIS_URL → collegata automaticamente da Redis plugin"
    echo "NODE_ENV=production"
    echo ""
else
    print_warn "File .env non trovato. Configura le variabili manualmente dalla dashboard."
fi

read -p "Premi INVIO quando hai configurato le variabili..." _

# ============================================================
# STEP 9: Deploy
# ============================================================
print_step "9" "Deploy!"

echo "Con GitHub auto-deploy configurato, ogni push triggera il deploy."
echo "Per fare il primo deploy manuale:"
echo ""
echo "  git add -A && git commit -m 'deploy: initial Railway setup' && git push"
echo ""
echo "Oppure forza il deploy dalla dashboard cliccando 'Deploy' su ogni servizio."
echo ""

read -p "Vuoi fare push ora per triggerare il deploy? (y/n): " DO_DEPLOY
if [ "$DO_DEPLOY" = "y" ]; then
    git add -A
    if git diff --cached --quiet; then
        print_warn "Nessuna modifica da committare"
    else
        git commit -m "deploy: Railway configuration and optimized Dockerfiles"
        git push
        print_ok "Push completato — deploy in corso su Railway!"
    fi
fi

# ============================================================
# STEP 10: Verify
# ============================================================
print_step "10" "Verifica deployment"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  VERIFICA CHECKLIST                                   ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                       ║"
echo "║  □ PostgreSQL plugin: verde nella dashboard           ║"
echo "║  □ Redis plugin: verde nella dashboard                ║"
echo "║  □ ml-worker: build riuscita, status 'Active'        ║"
echo "║  □ ai-router: build riuscita, status 'Active'        ║"
echo "║  □ Health check ml-worker: GET /health → 200         ║"
echo "║  □ Health check ai-router: GET /health → 200         ║"
echo "║  □ Dashboard accessibile via URL pubblica             ║"
echo "║                                                       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Per controllare i log in tempo reale:"
echo "  railway logs -s ml-worker"
echo "  railway logs -s ai-router"
echo ""
echo "Per aprire la dashboard Railway:"
echo "  railway open"
echo ""

print_ok "Setup completato! 🚀"
echo ""
echo "URL utili:"
echo "  Dashboard Railway: https://railway.app/dashboard"
echo "  Docs: https://docs.railway.app"
echo ""
