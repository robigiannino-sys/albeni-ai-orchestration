#!/bin/bash
# =============================================================
# Albeni 1905 — AI Control Tower Deploy Script
# Aggiorna il Content Lake multilingua, il tracker unificato
# e la content_library dalla cartella di output alla tower.
#
# Uso:  chmod +x deploy-control-tower.sh && ./deploy-control-tower.sh
# =============================================================

set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────
ALBENI_ROOT="$HOME/Desktop/ALBENI/albeni.com/STEFANO/AI STACK APP/ai-orchestration-layer"
DASHBOARD_DIR="$ALBENI_ROOT/dashboard"
TRACKING_DIR="$ALBENI_ROOT/tracking"
SNIPPETS_DIR="$ALBENI_ROOT/snippets"

# Source files (same folder as this script)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTENT_LAKE="$SCRIPT_DIR/content-lake-multilingual.js"
UNIFIED_TRACKER="$SCRIPT_DIR/albeni-unified-tracker.js"
LIBRARY_PATCH="$SCRIPT_DIR/content-library-patch.json"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Albeni 1905 — AI Control Tower Deploy"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── 1. Verify paths ───────────────────────────────────────────
if [ ! -d "$ALBENI_ROOT" ]; then
  echo -e "${RED}✗ Cartella non trovata:${NC} $ALBENI_ROOT"
  echo "  Assicurati che la cartella ALBENI sia sul Desktop."
  exit 1
fi

echo -e "${GREEN}✓${NC} Cartella AI Stack trovata"

# Create target dirs if needed
mkdir -p "$DASHBOARD_DIR" "$TRACKING_DIR" "$SNIPPETS_DIR"

# ── 2. Deploy Content Lake Multilingual ───────────────────────
if [ -f "$CONTENT_LAKE" ]; then
  # Backup existing
  if [ -f "$DASHBOARD_DIR/content-lake-multilingual.js" ]; then
    cp "$DASHBOARD_DIR/content-lake-multilingual.js" \
       "$DASHBOARD_DIR/content-lake-multilingual.js.bak.$(date +%Y%m%d%H%M%S)"
    echo -e "${YELLOW}↻${NC} Backup precedente Content Lake creato"
  fi

  cp "$CONTENT_LAKE" "$DASHBOARD_DIR/content-lake-multilingual.js"
  echo -e "${GREEN}✓${NC} Content Lake Multilingual → dashboard/"

  # Also copy to tracking/ for the behavioral engine
  cp "$CONTENT_LAKE" "$TRACKING_DIR/content-lake-multilingual.js"
  echo -e "${GREEN}✓${NC} Content Lake Multilingual → tracking/"
else
  echo -e "${RED}✗${NC} content-lake-multilingual.js non trovato in $SCRIPT_DIR"
fi

# ── 3. Deploy Unified Tracker ─────────────────────────────────
if [ -f "$UNIFIED_TRACKER" ]; then
  # Backup old trackers
  for OLD_FILE in "$TRACKING_DIR/albeni-ai-tracker.js" "$SNIPPETS_DIR/tracking.js"; do
    if [ -f "$OLD_FILE" ]; then
      cp "$OLD_FILE" "${OLD_FILE}.bak.$(date +%Y%m%d%H%M%S)"
      echo -e "${YELLOW}↻${NC} Backup: $(basename "$OLD_FILE")"
    fi
  done

  cp "$UNIFIED_TRACKER" "$TRACKING_DIR/albeni-unified-tracker.js"
  echo -e "${GREEN}✓${NC} Unified Tracker → tracking/"

  # Also place in snippets/ for WP deployment
  cp "$UNIFIED_TRACKER" "$SNIPPETS_DIR/albeni-unified-tracker.js"
  echo -e "${GREEN}✓${NC} Unified Tracker → snippets/"
else
  echo -e "${RED}✗${NC} albeni-unified-tracker.js non trovato in $SCRIPT_DIR"
fi

# ── 4. Update content_library.json ────────────────────────────
LIBRARY_FILE="$DASHBOARD_DIR/content_library.json"
if [ -f "$LIBRARY_FILE" ] && [ -f "$LIBRARY_PATCH" ]; then
  cp "$LIBRARY_FILE" "${LIBRARY_FILE}.bak.$(date +%Y%m%d%H%M%S)"
  echo -e "${YELLOW}↻${NC} Backup content_library.json creato"

  # Use Python to merge the patch into content_library.json
  python3 - "$LIBRARY_FILE" "$LIBRARY_PATCH" << 'PYEOF'
import json, sys

lib_path, patch_path = sys.argv[1], sys.argv[2]

with open(lib_path, 'r') as f:
    library = json.load(f)

with open(patch_path, 'r') as f:
    patch = json.load(f)

existing_ids = {item['id'] for item in library['contents']}

added = 0
for entry in patch.get('new_entries', []):
    if entry['id'] not in existing_ids:
        library['contents'].append(entry)
        existing_ids.add(entry['id'])
        added += 1

library['total_entries'] = len(library['contents'])
library['last_updated'] = patch.get('date', '2026-03-31')

# Add new categories if needed
for cat in patch.get('new_categories', []):
    if cat not in library['categories']:
        library['categories'].append(cat)

with open(lib_path, 'w') as f:
    json.dump(library, f, indent=2, ensure_ascii=False)

print(f"  → {added} nuove entry aggiunte, totale: {library['total_entries']}")
PYEOF
  echo -e "${GREEN}✓${NC} content_library.json aggiornato"
else
  if [ ! -f "$LIBRARY_FILE" ]; then
    echo -e "${RED}✗${NC} content_library.json non trovato in dashboard/"
  fi
  if [ ! -f "$LIBRARY_PATCH" ]; then
    echo -e "${YELLOW}⚠${NC} content-library-patch.json non presente — skip update"
  fi
fi

# ── 5. Summary ────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Deploy completato!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  File deployati:"
echo "    • dashboard/content-lake-multilingual.js  (432 varianti IT/EN/DE/FR)"
echo "    • tracking/content-lake-multilingual.js   (copia per behavioral engine)"
echo "    • tracking/albeni-unified-tracker.js      (Layer 1 consolidato)"
echo "    • snippets/albeni-unified-tracker.js      (per deploy WP)"
echo ""
echo "  Prossimi passi:"
echo "    1. Verifica i file nella cartella ALBENI"
echo "    2. Per deploy Docker:  cd \"$ALBENI_ROOT\" && docker compose up -d --build"
echo "    3. Per deploy WP:     carica snippets/albeni-unified-tracker.js via WPCode"
echo ""
