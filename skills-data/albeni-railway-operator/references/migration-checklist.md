# Railway Project Migration — Checklist

Quando si decide di sostituire un Railway project (per refactor, trial scaduto, riconfigurazione), seguire QUESTA sequenza per evitare la "ghost Railway" pattern (eventi reali persi silenziosamente).

## Pre-migrazione

- [ ] **Inventario clienti**: trova TUTTI i punti dove l'host Railway vecchio è hardcoded
  ```bash
  cd ~/Desktop/ALBENI/albeni.com
  grep -rIE "OLD-PROJECT-HOST\.up\.railway\.app" \
    --include="*.html" --include="*.js" --include="*.py" --include="*.sh" \
    --include="*.toml" --include="*.json" --include="*.env*" \
    | grep -v node_modules | grep -v __pycache__
  ```
  Includi anche:
  - Snippet WP installati (non nel repo): admin di MU + WoM, sezione WPCode
  - Hostinger Horizons SPA (PMS)
  - Codice Vercel di albeni1905.com
  - Webhook esterni (Notion, Klaviyo, Shopify)
  - Custom domain DNS records

- [ ] **Snapshot dati**: dump del DB del progetto vecchio prima di chiudere
  ```bash
  railway link -p OLD-PROJECT
  railway run --service Postgres bash -c 'pg_dump "$DATABASE_URL" > /tmp/backup-OLD.sql'
  scp /tmp/backup-OLD.sql ~/Desktop/ALBENI/backups/
  ```

- [ ] **Verifica del nuovo progetto**: `/health` deve essere `healthy`, plugin Postgres e Redis attivi, env vars complete
  ```bash
  railway link -p NEW-PROJECT
  curl -s https://NEW-DEPLOY.up.railway.app/health | python3 -m json.tool
  railway variables --service NEW-MAIN-SERVICE --kv | grep -E '^(DATABASE_URL|REDIS_URL|.*_API_KEY)'
  ```

## Migrazione

- [ ] **Aggiorna i clienti UNO PER VOLTA**, in quest'ordine:
  1. **Frontend interno** (dashboard, dev): cambia URL in `dashboard/index.html`
  2. **Snippet WP**: edit via `albeni-wp-operator` skill (CodeMirror) — no broadcast in massa, uno alla volta
  3. **SPA Vercel/Hostinger**: deploy nuovo bundle
  4. **Webhook esterni**: aggiorna URL in Notion/Klaviyo/Shopify settings
  5. **DNS custom domain**: ultimo, perché DNS prop è lento

- [ ] **Smoke test dopo OGNI modifica**:
  ```bash
  curl -X POST https://NEW-DEPLOY.up.railway.app/v1/track/event \
    -H "Content-Type: application/json" \
    -d '{"user_id":"migrate_test","session_id":"m","domain":"<dominio aggiornato>","event_type":"page_view","event_value":{"phase":"migration","step":N}}'
  ```
  Poi verifica scrittura in DB. Se 202 ma 0 nuove righe → STOP, c'è un problema (vedi Bug 1 in SKILL.md).

- [ ] **Ripopola seed se necessario**: per data-coerent demo
  ```bash
  python3 generate_seed.py
  railway run --service Postgres bash -c 'python3 run_seed.py'
  ```

## Post-migrazione

- [ ] **Verifica zero residui**: rilancia il grep del punto 1, deve essere vuoto
  ```bash
  grep -rIE "OLD-PROJECT-HOST" ~/Desktop/ALBENI/albeni.com | grep -v node_modules
  # Empty = OK
  ```

- [ ] **Periodo di osservazione**: lascia entrambi i progetti attivi per 24-48h, monitora i log del NUOVO che riceva traffico, e i log del VECCHIO che NON riceva nulla
  ```bash
  railway link -p OLD-PROJECT && railway logs --service main 2>&1 | grep -i "track\|event" &
  railway link -p NEW-PROJECT && railway logs --service main 2>&1 | grep -i "track\|event"
  ```

- [ ] **Decommissioning**: solo dopo conferma che il vecchio non riceve più eventi
  ```bash
  railway delete -p OLD-PROJECT-ID
  ```
  (Comando irreversibile — Railway chiede conferma esplicita digitando il nome del progetto.)

- [ ] **Aggiorna memoria progetto**: salva `feedback_railway_*.md` e `project_railway_deploy.md` con i nuovi project ID + URL e mark il vecchio come "decommissionato il YYYY-MM-DD"

## Cosa NON fare durante migrazione

- ❌ **Non cancellare immediatamente** il vecchio progetto. Aspetta 24-48h con il vecchio inattivo come safety net.
- ❌ **Non disabilitare i plugin** (Postgres/Redis) del vecchio prima di migrare i clienti — diventa subito "ghost Railway" che assorbe eventi senza scriverli.
- ❌ **Non confidare solo nello status code 202**: verifica sempre che l'evento arrivi in DB.
- ❌ **Non fare changes massivi al codice durante una migrazione di host**. Una cosa per volta: prima sposti l'host, poi rilasci feature nuove.

## Checklist rapida (per ogni progetto Albeni)

| Cliente | Dove vive | Come si aggiorna |
|---|---|---|
| Dashboard WoM/MU snippet | wp-admin WPCode | `albeni-wp-operator` skill |
| Repo file snippets | `ai-orchestration-layer/snippets/wordpress/` | sed/Edit, commit, push |
| Dashboard frontend | `ai-router/dashboard/index.html` | Edit `ML_API`, commit, push |
| PMS (Horizons SPA) | hpanel.hostinger.com → editor | Manuale, no API |
| albeni1905.com (Vercel) | repo Next.js → TrackingProvider | git commit, push, Vercel auto-deploy |
| Approval webhook (Notion → wp) | progetto separato `merino-approval-webhook` | Aggiorna env var su quel progetto Railway |
| Klaviyo flows con link tracking | Klaviyo dashboard | Manuale, replace URL nei template |
