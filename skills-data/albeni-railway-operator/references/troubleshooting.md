# Railway Troubleshooting — Symptom → Diagnosis → Fix

## Sintomi e cause più probabili

### "Il dashboard è vuoto"
Procedere in ordine:
1. **Cache browser**: hard refresh `Cmd+Shift+R` o incognito
2. **Frontend punta a localhost**: aprire DevTools → Network, controllare se le chiamate `/v1/*` vanno a `localhost:8000`. Se sì, fix `ML_API`/`ROUTER_API` in `dashboard/index.html` a empty string (same-origin)
3. **API risponde ma DB vuoto**: `curl https://.../v1/dashboard/metrics` — se total_users=0 il DB è davvero vuoto, vedi sotto
4. **DB non popolato**: lancia `seed_demo.sql` via `railway run --service Postgres bash -c 'python3 ...'` per dati demo
5. **DB ha dati ma dashboard non li vede**: bug del frontend, oppure cache LiteSpeed sul WP che mostra una versione cachata del dashboard (ma il dashboard è su Railway, non WP — solo se un proxy intermedio)

### "Gli eventi reali non arrivano in DB" (più subdolo) — DECISION TREE

Procedi in ordine, fermati al primo "no":

1. **Snippet WP punta al Railway giusto?** Apri wp-admin → WPCode → snippet 2943 (MU) o 1181 (WoM), verifica `endpoint:` nel JS — deve essere `creative-perfection-production-57b5.up.railway.app` (NON tunnel Cloudflare, NON tender-nurturing).

2. **Endpoint `/v1/track/event` risponde?** Test:
   ```bash
   curl -s -X POST https://creative-perfection-production-57b5.up.railway.app/v1/track/event \
     -H 'Content-Type: application/json' \
     -d '{"visitor_id":"diag_'$(date +%s)'","domain":"worldofmerino.com","event_type":"page_view","timestamp":"'$(date -u +%FT%TZ)'"}'
   ```
   Status atteso: `200/202` con `persisted: true` E `latency_ms > 100`. Se diverso vai al sintomo specifico:
   - **400 Bad Request** → ai-router non riconosce il payload. Verifica che la versione deployata abbia il fix schema-tolerant (commit `d8ded3d`+). Se è un deploy vecchio: `git pull && git push` per forzare redeploy, oppure verifica `railway logs --service creative-perfection`.
   - **502 cached_only + ml_worker_unreachable** → ai-router non raggiunge ml-worker. Controlla:
     ```bash
     railway variables --service creative-perfection --kv | grep ML_WORKER_URL
     # Atteso: ML_WORKER_URL=http://albeni-ai-orchestration.railway.internal:8080
     # Se mancante: railway variables --service creative-perfection --set ML_WORKER_URL=http://albeni-ai-orchestration.railway.internal:8080
     ```
   - **502 + status code 422 from ml_worker** → mismatch schema. Controlla i log ml-worker per vedere il campo che non passa Pydantic. Quasi sempre è `timestamp` (deve essere int ms, non string ISO) — verifica che ai-router abbia il commit `3d9315b`+ con la coercion.
   - **latency < 50ms con 202** → SOSPETTO! Probabilmente ai-router risponde 202 senza aver effettivamente forwardato (codice pre-fix). Verifica versione deployata: `git log --oneline | head -5` su Mac, deve includere d8ded3d e 3d9315b.

3. **L'evento è scritto in DB?**
   ```bash
   cd ai-orchestration-layer
   railway run --service Postgres bash -c 'python3 -c "
   import os, psycopg2
   c = psycopg2.connect(os.environ[\"DATABASE_PUBLIC_URL\"]).cursor()
   c.execute(\"SELECT COUNT(*) FROM behavioral_signals WHERE created_at >= NOW() - INTERVAL %s\", (\"5 minutes\",))
   print(c.fetchone()[0])
   "'
   ```
   - **>= 1**: write path OK ✓
   - **0** dopo 1 minuto dal POST → ml-worker stesso non scrive. Controlla `railway logs --service albeni-ai-orchestration` per Pydantic ValidationError o DB exception.

4. **Container ha DB+Redis healthy?**
   ```bash
   curl -s https://creative-perfection-production-57b5.up.railway.app/health | python3 -m json.tool
   ```
   Se `database: unhealthy` o `redis: unhealthy` → è un **ghost Railway**. Probabilmente i plugin sono dismessi o in altro project. Verifica `railway list --json` e i service IDs. Vedi sez. "Rule 4 — Ghost Railway pattern" in SKILL.md.

5. **WPCode snippet runtime cache (subdolo)** — se hai modificato lo snippet 2943/1181 via REST API (non via UI nativa WPCode), il sito frontend potrebbe ancora usare la versione vecchia. WPCode Lite ha una runtime cache separata che si invalida solo cliccando "Aggiorna" sull'editor admin. Vai su `https://merinouniversity.com/wp-admin/admin.php?page=wpcode-snippet-manager&snippet_id=2943` e clicca il bottone blu "Aggiorna" anche se non hai modificato niente — questo forza il ricompilato. Stesso per worldofmerino.com snippet 1181.

6. **Hostinger CDN (hcdn) — purge separato** — il dashboard Railway non passa da hcdn ma il sito WoM/MU sì. Se i tuoi cambi ai snippet WP non si vedono nel browser anche dopo LiteSpeed purge: vai su `https://hpanel.hostinger.com/websites/worldofmerino.com` → "Cancella la cache" → "Clear cache". Vedi sez. correlata in `albeni-wp-operator`.

7. **False negative "tracker non caricato"** — se cerchi gli script tracker con `document.querySelectorAll('script[src*="albeni"]')` ottieni 0 risultati anche se il tracker funziona. Causa: lo snippet inline carica i tracker via `fetch + appendChild` con `script.textContent = code`, quindi gli script appaiono come **inline** non external. Il check corretto è cercare per `textContent`:
   ```javascript
   Array.from(document.querySelectorAll('script')).filter(s =>
     !s.src && /AI Orchestration Layer Tracker|Behavioral Engine v2/i.test(s.textContent || '')
   ).length
   // → 2 quando funziona
   ```
   Vedi Bug 4 in SKILL.md per dettagli + l'unica verifica end-to-end affidabile (query DB).

8. **`navigator.sendBeacon` non si vede in network monitor** — il tracker usa `sendBeacon` su page unload per reliability. Chrome MCP `read_network_requests` e altri network monitor **non lo catturano**. Non significa che non funziona — verifica solo via DB. Per debug locale, sostituisci temporaneamente con `fetch()` per vederlo in DevTools → Network.

### "Custom domain non si attiva su Railway"

1. **DNS records non propagati**: `dig +short CNAME tower.example.com` deve risolvere a `<random>.up.railway.app.`. Se vuoto, il record non è stato propagato. Hostinger DNS è veloce (immediato), altri provider possono richiedere 5-30 min.
2. **TXT verification token sbagliato**: il TXT record name è `_railway-verify.<subdomain>` (con il dot). Il valore è `railway-verify=<token>` (con il prefix `railway-verify=`). Verifica con `dig TXT _railway-verify.tower.example.com`.
3. **Polling Railway lento**: il primo dominio di un service viene verificato in 1-2 min, il secondo richiede 5-10 min. È normale, non è un bug. Lo stato in dashboard mostra "Waiting for DNS update" (giallo) durante il polling.
4. **404 "Application not found" durante l'attivazione**: significa che DNS è OK ma TXT non ancora verificato da Railway. Il proxy riceve la request ma non sa a quale service mapparla. Aspetta 5-10 min, ri-prova.
5. **SSL Let's Encrypt in emissione**: dopo che TXT è verificato, Railway emette il certificato in 1-5 min. Durante questa finestra `curl https://...` fallisce con `ssl_verify=1` ma `curl -k https://...` (skip cert) funziona.

### "railway run dice 'No linked project found'"
- Sei nella cartella sbagliata. `cd ai-orchestration-layer/` (non a `AI STACK APP/`)
- Se la cartella non è ancora linkata: `railway link -p kind-prosperity`

### "Connessione DB rifiutata da Mac"
- Stai usando `DATABASE_URL` (interna `*.railway.internal`) da fuori → cambia a `DATABASE_PUBLIC_URL`
- Public networking non abilitata: Railway dashboard → Postgres → Settings → Networking → "Generate Domain"

### "Build failed dopo git push"
1. `railway logs --service <svc> --filter build` per vedere l'errore
2. Verifica `railway.toml` del service (path, builder)
3. Verifica `Dockerfile` o `package.json`/`requirements.txt`
4. `railway-prebuild.sh` deve essere eseguito? Il dashboard frontend viene copiato lì.

### "Container in restart loop"
- `railway logs --service <svc>` per vedere stack trace
- Spesso: env var mancante (es. `DATABASE_URL` non collegata), o porta sbagliata
- Verifica `PORT` env var: ai-router e ml-worker devono ascoltare su `process.env.PORT` (Railway lo assegna dinamicamente)

### "/health ritorna degraded"
Il container è UP ma uno o più servizi non rispondono:
- `redis: unhealthy` → plugin Redis dismesso o non collegato
- `database: unhealthy` → plugin Postgres dismesso o non collegato
- `ai_provider: gemini_configured` ma `klaviyo: not_configured` → env var mancante (è solo un warning, non blocking)

Fix: vai su Railway dashboard → service → Variables, controlla che `DATABASE_URL`, `REDIS_URL` puntino ai plugin attivi del PROGETTO CORRENTE (non di un altro project ghost).

### "Snippet WP modificato ma cambiamento non si vede"
- LiteSpeed cache: dal wp-admin → "Svuotare e pulire tutta la cache"
- Browser cache: hard refresh
- WPCode cache: edit + save dello snippet rigenera anche la cache plugin
- Verifica nel browser frontend con DevTools → Sources che lo script caricato sia quello nuovo

### "Domain custom non risolve"
- DNS propagation può richiedere 5-30 min
- Verifica con `dig +short ai.albeni.com` — deve risolvere all'IP CNAME di Railway
- Su Hostinger DNS panel: tipo CNAME, nome `ai`, valore = quello dato da Railway
- HTTPS automatico via Let's Encrypt parte solo dopo che il DNS è propagato

## Pattern di debug avanzato

### Trace di un evento dal browser fino al DB
```bash
# 1. Apri Chrome → Network tab → filtra "track/event"
# 2. Visita una pagina del sito target
# 3. Ispeziona la POST: status, response body
# 4. Sul Mac, query DB:
railway run --service Postgres bash -c 'python3 -c "
import os, psycopg2
c = psycopg2.connect(os.environ[\"DATABASE_PUBLIC_URL\"]).cursor()
c.execute(\"SELECT id, event_value, created_at FROM behavioral_signals ORDER BY created_at DESC LIMIT 3\")
for r in c.fetchall(): print(r)
"'
# Se l'evento NON appare entro 30 sec, il consumer è morto
```

### Verifica quale Railway project sta servendo un host
```bash
curl -sI https://creative-perfection-production-57b5.up.railway.app/health | head -5
# Confronta con
railway list --json | python3 -c '
import json, sys
for p in json.load(sys.stdin):
    for s in p.get("services", {}).get("edges", []):
        print(p["name"], "->", s["node"]["name"])
'
```

### Recupera DATABASE_URL di un progetto da CLI senza linkarlo
```bash
# Linka temporaneamente, esporta, unlink (workaround)
railway link -p tender-nurturing
URL=$(railway variables --service Postgres --kv | grep '^DATABASE_PUBLIC_URL=' | cut -d= -f2-)
echo "Got URL of length: ${#URL}"
railway link -p kind-prosperity   # torna al main
```

(Usa con cautela; l'unlink esplicito non esiste, basta rilinkare.)
