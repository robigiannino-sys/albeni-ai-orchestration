---
name: albeni-railway-operator
description: |
  **Albeni 1905 Railway Operator**: Manages the Railway cloud infrastructure for the Albeni 1905 AI Stack. Covers project lifecycle (create/link/delete), service deployment, plugin management (PostgreSQL/Redis), public/internal networking, custom domains, environment variables, smoke testing, and the migration patterns learned during the kind-prosperity setup and tender-nurturing decommission.
  - MANDATORY TRIGGERS: railway, Railway, deploy railway, railway deploy, railway CLI, railway link, railway delete, railway run, railway logs, railway service, railway status, postgres railway, redis railway, public networking railway, DATABASE_PUBLIC_URL, DATABASE_URL railway, railway.toml, ai-router railway, ml-worker railway, creative-perfection, kind-prosperity, container railway, plugin railway, custom domain railway, smoke test railway, tracking endpoint
  - Also trigger when: user asks to deploy/redeploy something to Railway, switch between Railway projects, debug a "why is the dashboard empty" or "why don't real events arrive" problem, manage Postgres/Redis plugins, set env vars, configure custom domains, decommission an old Railway project, or migrate snippets/clients between Railway endpoints.
---

# Albeni 1905 — Railway Operator

You are the operational agent for the **Railway cloud infrastructure** of the Albeni 1905 AI Stack. This skill encodes patterns learned setting up the kind-prosperity project, decommissioning tender-nurturing, and debugging the "ghost Railway" issue that silently lost weeks of real visitor events.

## The Railway Ecosystem (snapshot)

### Active Projects (April 2026)

| Project ID | Name | Region | Role | Status |
|---|---|---|---|---|
| `e86ec512-5727-44fa-9578-00f97752e232` | **kind-prosperity** | EU West (Amsterdam) | Main AI Orchestration Layer | LIVE |
| `255581e2-52ee-46f0-b2d8-704154de79ba` | **merino-approval-webhook** | EU West | Notion approval handler (separate project) | LIVE |
| `d918af00-fc05-4a84-afed-77c6f885fde1` | tender-nurturing | EU West | Decommissioned 2026-04-29 | DELETED |

### kind-prosperity services (UI italianizzata: "gentilezza-prosperità", environment "produzione")
- **albeni-ai-orchestration** (service ID `98804cf8-accc-41ee-801a-0799074894be`) — Python FastAPI ml-worker, internal `albeni-ai-orchestration.railway.internal:8080`
- **creative-perfection** (service ID `a7a750b2-e5ff-48c4-8ae1-71a1ec9f8c00`) — Node.js Express ai-router, public domain `creative-perfection-production-57b5.up.railway.app`
- **Postgres** (service ID `2f9c457c-6c91-4056-81c4-ea66bf5fb8d3`) — DATABASE_URL internal + DATABASE_PUBLIC_URL on `maglev.proxy.rlwy.net:39244`
- **Redis** (service ID `b3580a75-5678-4134-a606-dada5a75cb5e`) — REDIS_URL internal
- **zooming-dedication** (service ID `191c5bf3-1891-4c40-9869-183ef1902649`) — additional service (verify role with `railway service`)
- **albeni-ga4-sync** — Cron job, schedule `0 3 * * *` (03:00 UTC). Pulls GA4 daily metrics + geo breakdown into `ga4_daily` / `ga4_geo_daily` tables. GitHub repo: `robigiannino-sys/albeni-ga4-sync`. Aggiunto 2026-04-29 (vedi Pattern 11 e Bug 5).
- **editorial-approval-agent** — Service per gestione approvazioni editoriali (verifica role con `railway service`). Aggiunto post 2026-04-28, da documentare.

**Nota nomenclatura**: la UI Railway italianizza i nomi quando il browser è in italiano. Mappature osservate:
- `kind-prosperity` ↔ "gentilezza-prosperità"
- `creative-perfection` ↔ "perfezione creativa"
- `zooming-dedication` ↔ "dedizione allo zoom"
- `editorial-approval-agent` ↔ "agente di approvazione editoriale"
Sui comandi CLI usa SEMPRE i nomi inglesi reali (quelli sopra elencati).

### GitHub auto-deploy
Repo: `robigiannino-sys/albeni-ai-orchestration` (public). Every push to `main` triggers a redeploy of services that follow the repo. Verify with `railway logs --service <service>` after push.

---

## Critical Rules (Learned the Hard Way)

### Rule 1 — DATABASE_PUBLIC_URL vs DATABASE_URL: never confuse them

`railway run --service Postgres` injects the **internal** Railway URL (`postgres.railway.internal`) into the env vars. This works ONLY from another Railway service in the same project. From a Mac terminal, that hostname doesn't resolve.

For external connections (Mac terminal, local script, debug):
```python
url = os.environ.get('DATABASE_PUBLIC_URL') or os.environ['DATABASE_URL']
```
Always prefer `DATABASE_PUBLIC_URL`. If it's missing: Railway dashboard → Postgres → Settings → Networking → "Generate Domain" to enable Public Networking. The variable will appear after a few seconds.

**Never** hardcode either URL: read from env at runtime.

### Rule 2 — `railway run` from the linked directory only

`railway run` injects env vars and proxies the command, but requires **the current directory to be linked to a project** (the link is per-directory, stored in `~/.railway/`).

```bash
# Always cd FIRST
cd "/Users/roberto/Desktop/ALBENI/albeni.com/STEFANO/AI STACK APP/ai-orchestration-layer"
railway link -p kind-prosperity   # if not already linked
railway run --service Postgres bash -c '...'
```

If `railway run` answers "No linked project found", you're in the wrong directory. The MAIN Albeni project is linked at `ai-orchestration-layer/`, NOT at the parent `AI STACK APP/`.

### Rule 3 — psycopg2 must be installed for the Python that `bash -c` uses

`railway run --service Postgres python3 ...` inherits the system Python which usually doesn't have psycopg2. The reliable pattern is:

```bash
# Once on Mac (user-install)
pip3 install --user --break-system-packages psycopg2-binary

# Then always use bash -c so user-install path is in PYTHONPATH
railway run --service Postgres bash -c 'python3 /tmp/script.py'
```

`/tmp/script.py` works because it's a clean path with no spaces. **Never pass scripts with spaces in their absolute paths to `railway run` directly** — the quoting under macOS's osascript adds another layer of escaping that breaks the command. Copy to `/tmp/` first.

### Rule 4 — The "ghost Railway" pattern (most dangerous)

A Railway service container can stay UP and respond 200 on `/health` even after its **PostgreSQL and Redis plugins have been removed**. The `/health` body says `degraded` and lists `database: unhealthy`, but a casual ping looks "alive".

```bash
# Real check, not just status code
curl -s https://YOUR-DEPLOY.up.railway.app/health | python3 -m json.tool
# Look for status=="healthy" AND services.database=="healthy"
```

Symptoms of a ghost Railway: container responds, but `/v1/dashboard/metrics` returns 500 "Failed to aggregate metrics", and any client that posts events sees 202 OK without anything ever appearing in your DB.

**Always** retire old Railway projects deliberately with `railway delete -p <project_id>`. Don't leave them as ghosts. A ghost Railway dropped 20 days of real WoM/MU visitor events on this project (see `feedback_railway_silent_drift` memory).

### Rule 5 — Snippet endpoint sync after migration

When migrating from Railway project A to Railway project B, **EVERY hardcoded reference to A** must be updated. On Albeni 1905 these live in:

1. WPCode snippets in WP admin: `merinouniversity.com` snippet **2943** (MU - Albeni AI Tracker), `worldofmerino.com` snippet **1181** (Albeni AI Tracker). Update via `albeni-wp-operator` skill (CodeMirror + click "Aggiorna").
2. Repo snippet files: `ai-orchestration-layer/snippets/wordpress/snippet-*-{TOFU,MOFU,BOFU}.html`.
3. Hostinger Horizons SPA `perfectmerinoshirt.com`: edit via Horizons editor, no API.
4. Vercel `albeni1905.com`: TrackingProvider component in the Next.js repo (commit + push).
5. Dashboard frontend `ai-router/dashboard/index.html` and `dashboard/index.html`: `ML_API` and `ROUTER_API` constants at lines 117-118 (use same-origin `''` in production, query string override for local dev).

Use `grep -rE "old-project-host" .` BEFORE the migration to find all references. Don't rely on memory.

### Rule 6 — public networking for psql access

Before connecting from a Mac terminal:
1. Railway dashboard → Postgres service → Settings → Networking → click "Generate Domain"
2. A `*.proxy.rlwy.net:NNNNN` host is created
3. `DATABASE_PUBLIC_URL` env var is auto-populated
4. Re-run `railway variables --service Postgres --kv` to verify it's there

Without public networking enabled, you must use `railway run --service Postgres bash -c 'psql "$DATABASE_URL" ...'` which proxies through Railway's internal network (slower but works).

---

## Standard Operations (Cookbook)

### 1. Check status of all projects

```bash
cd ~/Desktop/ALBENI/albeni.com/STEFANO/AI\ STACK\ APP/ai-orchestration-layer
railway whoami
railway list
railway list --json | python3 -m json.tool   # full structure with services
```

### 2. Deploy a code change

```bash
# Auto-deploy via Git
git add <changed-files>
git commit -m "fix(scope): summary"
git push origin main

# Watch Railway pick it up
railway logs --service creative-perfection   # for ai-router
railway logs --service albeni-ai-orchestration  # for ml-worker
# Look for "Listening on port 8080" or "Application startup complete"
```

### 3. Get DATABASE_PUBLIC_URL for external use

```bash
cd ai-orchestration-layer
railway variables --service Postgres --kv | grep '^DATABASE_PUBLIC_URL='
```

### 4. Run a one-off SQL query from Mac

```bash
# Copy script to /tmp first to avoid space-in-path issues
cp "/path with spaces/myquery.py" /tmp/q.py
cd ~/Desktop/ALBENI/albeni.com/STEFANO/AI\ STACK\ APP/ai-orchestration-layer
railway run --service Postgres bash -c 'python3 /tmp/q.py'
```

The script template:
```python
import os, psycopg2
url = os.environ.get('DATABASE_PUBLIC_URL') or os.environ['DATABASE_URL']
conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM users")
print(cur.fetchone())
cur.close(); conn.close()
```

### 5. Bulk-load a SQL seed/migration

```bash
# psql NOT installed on Mac → use psycopg2 instead
railway run --service Postgres bash -c 'python3 -c "
import os, psycopg2
url = os.environ[\"DATABASE_PUBLIC_URL\"]
conn = psycopg2.connect(url); cur = conn.cursor()
with open(\"/tmp/seed.sql\") as f:
    cur.execute(f.read())
conn.commit(); cur.close(); conn.close()
print(\"OK\")
"'
```

For files >200 KB or with complex transactions, prefer the dedicated script `update_wp_snippets.py` style with proper error handling.

### 6. Delete an old project (CAUTION — irreversible)

```bash
# 1. Verify which project you're about to nuke
railway list --json | python3 -c '
import json, sys
for p in json.load(sys.stdin):
    print(p["id"], p["name"], "deleted=" + str(p.get("deletedAt")))
'

# 2. Run delete with explicit project ID (safer than name)
railway delete -p <PROJECT_ID>
# Railway will prompt to type the project name to confirm

# 3. Verify
railway list --json | python3 -m json.tool | grep -E '(name|deletedAt)'
# The deleted project shows deletedAt: timestamp; it's tombstoned in `list` for ~7 days
```

**Never** delete a project that has active traffic without first verifying that ALL clients (snippets, JS bundles, webhooks) have been migrated. Use grep to find references.

### 7. Custom domain setup (when ready)

```bash
# Pick a service to expose
railway domain --service creative-perfection --add ai.albeni.com
# Railway provides a CNAME record value; add it on the Hostinger DNS
# Wait ~5-10 min for DNS propagation, then test
```

### 8. View build/runtime logs

```bash
railway logs --service creative-perfection   # default = build + runtime
railway logs --service creative-perfection --filter runtime
railway logs --service creative-perfection --filter build
# Ctrl+C to exit
```

### 9. Smoke test a deploy end-to-end

After any deploy, run this from Mac terminal (NOT the Railway internal env):

```bash
# Step 1: health
curl -s https://creative-perfection-production-57b5.up.railway.app/health | python3 -m json.tool
# Look for status=="healthy", redis=="healthy"

# Step 2: API
curl -s https://creative-perfection-production-57b5.up.railway.app/v1/dashboard/metrics | python3 -m json.tool
# Look for total_users count growing over time

# Step 3: write path (track event)
curl -s -X POST https://creative-perfection-production-57b5.up.railway.app/v1/track/event \
  -H "Content-Type: application/json" \
  -d '{"user_id":"smoke_test_'$(date +%s)'","session_id":"smoke","domain":"worldofmerino.com","event_type":"page_view","event_value":{"test":true},"language":"it"}' \
  | python3 -m json.tool
# Status 202 + event_id

# Step 4 (CRITICAL — what was missing in earlier sessions):
# Verify the event ACTUALLY landed in the DB
cd ai-orchestration-layer
railway run --service Postgres bash -c 'python3 -c "
import os, psycopg2
url = os.environ[\"DATABASE_PUBLIC_URL\"]
c = psycopg2.connect(url).cursor()
c.execute(\"SELECT COUNT(*) FROM behavioral_signals WHERE created_at >= NOW() - INTERVAL %s\", (\"5 minutes\",))
print(\"events last 5min:\", c.fetchone()[0])
"'
```

If step 3 returns 202 but step 4 says 0 events, the **write pipeline has a hole** — accept the 202 from the endpoint but don't trust it. This was the second bug found on 2026-04-27 in `/v1/track/event` (see Known Issues below).

---

## Known Issues / Resolved Bugs

### Bug 1 — `/v1/track/event` returns 202 but doesn't persist  →  **RESOLVED 2026-04-27 evening**

**Symptom (was)**: POST to `/v1/track/event` returned `{"status":"event_logged","event_id":"<uuid>","latency_ms":N}` with HTTP 202, but the event never appeared in `behavioral_signals`, `user_intent_logs`, `sessions`, or any other Postgres table. Latency stayed at ~6ms (way too fast for a real SQL INSERT chain). For 20 days, every real visitor event from MU/WoM was silently dropped.

**Root cause — 3 layers of bugs piled on each other:**

1. **`ML_WORKER_URL` not set on `creative-perfection` service.**
   The ai-router code (`tracking.js`) reads `process.env.ML_WORKER_URL || 'http://ml-worker:8000'`. On Railway the env var was not set, so the fallback `http://ml-worker:8000` was used. That hostname doesn't resolve in Railway's network. **Every forward call to ml-worker failed with ECONNREFUSED / DNS error.**

2. **Forward to ml-worker was fire-and-forget with errors swallowed.**
   The original code wrapped `axios.post(...)` in `.catch(err => console.error(err.message))` — meaning the response to the client was always 202 regardless of whether ml-worker actually received the event. The 6ms latency came from finishing the sync Redis writes and returning before the failed forward could throw.

3. **Schema mismatch ai-router ↔ JS snippet ↔ ml-worker Pydantic model.**
   - JS snippet sends `visitor_id` (not `user_id`), with signal fields at top-level (`dwell_time_ms`, `scroll_depth_pct`, `mouse_events`, `device`, `campaign`, ...) — not wrapped in `metadata`.
   - ai-router expected `user_id` and would 400-reject if missing.
   - JS snippet sends `timestamp` as ISO 8601 string `"2026-04-27T22:30:00Z"`. ml-worker `TrackEventRequest` Pydantic schema declares `timestamp: Optional[int]`. Pydantic 2 raises 422 Unprocessable Entity on string-for-int.
   - Even if ai-router accepted the body, the forward to ml-worker would fail Pydantic validation.

**The fix — apply ALL three:**

```bash
# Layer 1 — set the env var
cd ai-orchestration-layer
railway variables --service creative-perfection --set ML_WORKER_URL=http://albeni-ai-orchestration.railway.internal:8080
# Railway auto-redeploys creative-perfection after env var change
```

```javascript
// Layer 2+3 — patch ai-router/routes/tracking.js
// Schema-tolerant body parsing
const user_id = body.user_id || body.visitor_id;
const lang = body.lang || body.language || 'it';
const metadata = {
    ...(body.metadata || body.event_value || {}),
    // Surface legacy top-level signal fields
    ...(body.dwell_time_ms !== undefined && { dwell_time_ms: body.dwell_time_ms }),
    ...(body.scroll_depth_pct !== undefined && { scroll_depth_pct: body.scroll_depth_pct }),
    ...(body.mouse_events !== undefined && { mouse_events: body.mouse_events }),
    ...(body.device !== undefined && { device: body.device }),
    ...(body.campaign !== undefined && { campaign: body.campaign }),
};

// Coerce timestamp ISO string → int millis (Pydantic Optional[int])
let timestamp = body.timestamp;
if (typeof timestamp === 'string') {
    const parsed = Date.parse(timestamp);
    timestamp = isNaN(parsed) ? Date.now() : parsed;
} else if (typeof timestamp !== 'number') {
    timestamp = Date.now();
}

// AWAIT forward with timeout (was fire-and-forget)
let forwardOk = false, forwardError = null;
try {
    await axios.post(`${ML_WORKER_URL}/v1/track/event`, forwardPayload, { timeout: 4000 });
    forwardOk = true;
} catch (err) {
    forwardError = err.message;
    console.error('ML Worker forward failed:', forwardError, '— url:', `${ML_WORKER_URL}/v1/track/event`);
}

// Differentiated status codes — clients/monitoring can finally tell whether
// the event was actually persisted (202) vs only cached in Redis (502).
if (!forwardOk) {
    return res.status(502).json({
        status: 'cached_only', event_id: eventId, latency_ms: latency,
        error: 'ml_worker_unreachable', detail: forwardError
    });
}
res.status(202).json({ status: 'event_logged', event_id: eventId, latency_ms: latency, persisted: true });
```

Commits applied: `d8ded3d` (schema-tolerant + sync forward + status codes), `3d9315b` (timestamp coercion).

**Verified post-fix**:
- Smoke test with **legacy snippet payload** (visitor_id, ISO timestamp, top-level fields): 202 + `persisted: true` + 395ms latency.
- DB check: `SELECT COUNT(*) FROM behavioral_signals WHERE created_at >= NOW() - INTERVAL '5 minutes'` returns N>0 with the expected event_value JSONB containing all top-level fields merged.

---

## Pattern 7 — Write-path verification post-deploy (CRITICAL)

After ANY deploy that touches tracking, ai-router, ml-worker, or env vars, run this **complete** smoke test. Don't trust HTTP 202.

```bash
# Step 1 — health
curl -s https://creative-perfection-production-57b5.up.railway.app/health | python3 -m json.tool
# REQUIRE: status=="healthy" AND services.redis=="healthy"
# If status=="degraded" or any service is unhealthy → stop, fix infra first.

# Step 2 — write event (simulate the legacy snippet payload precisely)
curl -s -X POST https://creative-perfection-production-57b5.up.railway.app/v1/track/event \
  -H "Content-Type: application/json" \
  -d '{
    "event_type":"page_view",
    "visitor_id":"smoke_'$(date +%s)'",
    "timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "page_url":"https://worldofmerino.com/it/test/",
    "domain":"worldofmerino.com",
    "dwell_time_ms":5000,
    "scroll_depth_pct":50,
    "mouse_events":15,
    "device":"desktop"
  }' | python3 -m json.tool
# REQUIRE: status=="event_logged" AND persisted: true AND latency_ms > 100
# A latency < 50ms is suspicious — the forward to ml-worker may have failed.
# A 502 with cached_only means ml-worker is unreachable: check ML_WORKER_URL env var.

# Step 3 — verify in Postgres (the only true confirmation)
cd ai-orchestration-layer
railway run --service Postgres bash -c 'python3 -c "
import os, psycopg2
c = psycopg2.connect(os.environ[\"DATABASE_PUBLIC_URL\"]).cursor()
c.execute(\"SELECT COUNT(*) FROM behavioral_signals WHERE created_at >= NOW() - INTERVAL %s\", (\"2 minutes\",))
print(\"signals last 2min:\", c.fetchone()[0])
c.execute(\"SELECT user_id, domain, event_type, event_value, created_at FROM behavioral_signals ORDER BY created_at DESC LIMIT 1\")
print(\"latest:\", c.fetchone())
"'
# REQUIRE: signals last 2min >= 1 AND event_value contains the top-level fields you sent.
```

If any of the three steps fails, the write path is broken **even if the dashboard looks fine** (the dashboard reads the seed). Don't claim "deploy successful" without all three passing.

### Bug 3 — Terminal AI returns "Invalid HTTP request received." → RESOLVED 2026-04-28

**Symptom**: dashboard pagina "Terminale AI" mostrava errore `Connessione fallita: Unexpected token 'I', "Invalid HT"... is not valid JSON. Verifica che i container Docker siano attivi.`

**Root cause**: la `fetch()` del frontend faceva POST a `/v1/terminal/execute?command=help` con `Content-Type: application/json` ma **senza body**. uvicorn/FastAPI rifiuta con 400 status text `"Invalid HTTP request received."` (plain text, non JSON). Il frontend tentava `JSON.parse(text)` → `SyntaxError: Unexpected token 'I'`.

**Fix commit `5ad49d1`**: due cose insieme:
```javascript
// Aggiunto body: '{}' (uvicorn lo accetta come oggetto vuoto valido)
const res = await fetch(`${ML_API}/v1/terminal/execute?command=${encodeURIComponent(cmd)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
});
// Defensive parse: se l'upstream non torna JSON, surface il testo grezzo + status
const raw = await res.text();
let data;
try {
    data = JSON.parse(raw);
} catch (e) {
    throw new Error(`Backend returned non-JSON (HTTP ${res.status}): ${raw.substring(0, 200)}`);
}
```

**Generalizzazione**: ogni volta che il frontend fa `POST` con `Content-Type: application/json` ma il body è vuoto, FastAPI/uvicorn restituisce 400 con plain text. Vale per tutti gli endpoint che richiedono solo query parameters. Pattern raccomandato per sicurezza: `body: '{}'` esplicito + defensive `JSON.parse` con fallback sul testo grezzo.

### Bug 4 — Tracker script "non caricato" è falso allarme → DOCUMENTATO 2026-04-28

**Symptom (era)**: durante il debug del tracking pipeline, `document.querySelectorAll('script')` filtrato per `s.src.includes('albeni-')` ritornava 0 risultati. Sembrava che il tracker non si caricasse.

**Spiegazione**: lo snippet inline non usa `<script src="...">` esterni. Usa il pattern **fetch + appendChild dinamico** con `script.textContent = code`:

```javascript
// Nel snippet WP inline (loadScript)
function loadScript(url, cb) {
  fetch(url).then(r => r.text()).then(code => {
    const s = document.createElement('script');
    s.textContent = code;
    document.head.appendChild(s);
    cb && cb();
  }).catch(e => console.warn('[Albeni] load error:', e));
}
loadScript(base + '/albeni-ai-tracker.js', function() {
  loadScript(base + '/albeni-behavioral-engine.js');
});
```

Quindi gli script appaiono nel DOM come **`<script>` inline** con `textContent` ma `src=""`. Il check corretto:

```javascript
// SBAGLIATO — cerca solo <script src=...>
Array.from(document.querySelectorAll('script')).filter(s => s.src.includes('albeni-')).length
// → 0 (false negative)

// CORRETTO — guarda anche inline scripts via textContent
Array.from(document.querySelectorAll('script')).filter(s =>
    !s.src && /AI Orchestration Layer Tracker|Behavioral Engine v2/i.test(s.textContent || '')
).length
// → 2 (tracker + behavioral engine)
```

**Verifica end-to-end (la sola affidabile)**: query DB direttamente dopo navigazione reale:
```sql
SELECT COUNT(*) FROM behavioral_signals
WHERE user_id IN (SELECT id FROM users WHERE external_id = 'v_<visitor_pattern>')
```
Se ci sono righe, il tracker funziona indipendentemente dal modo in cui appare in DOM.

**Anche `sendBeacon` non si vede in Chrome MCP `read_network_requests`**: il tracker usa `navigator.sendBeacon()` per reliability su page unload. È asincrono e non bloccante, e alcuni network monitor (incluso il Chrome MCP `read_network_requests`) **non li catturano**. Solo la query DB conferma che gli eventi arrivano.

---

## Pattern 8 — Custom Domain Setup (end-to-end procedure)

Pattern verificato il 28/04 con `tower.worldofmerino.com` (LIVE) e `tower.merinouniversity.com` (in attivazione).

### Step 1 — Aggiungi domain via Railway dashboard

`railway domain --service <name> <custom.domain.com>` da CLI ritorna **"Unauthorized. Please run `railway login` again"** anche se sei loggato. Non funziona da CLI per add. Usa la dashboard web:

1. Vai su `https://railway.com/project/<project_id>/service/<service_id>/settings`
2. Sezione **Networking** → click button "Custom Domain"
3. Input "example.com" → digita il dominio (es. `tower.worldofmerino.com`)
4. **Select port** → Railway offre "magic detection" (es. "8080 (node)") — selezionalo
5. Click "Add Domain"

Railway risponde con un dialog "Configure DNS Records" che mostra **2 record da aggiungere** sul DNS del dominio:
- **CNAME** `tower` → `<random>.up.railway.app` (dove `<random>` è il target Railway)
- **TXT** `_railway-verify.tower` → `railway-verify=<token>`

Estrai i valori esatti dal DOM con questo JavaScript (Railway li blocca al copy-paste se contengono "cookie data"):

```javascript
(() => {
  const all = document.body.innerText;
  const lines = all.split('\n').map(l => l.trim()).filter(l => l);
  return lines.filter(l =>
    /^[a-z0-9]{6,}\.up\.railway\.app$/.test(l) ||
    /^railway-verify=[0-9a-f]{50,}$/.test(l)
  );
})();
```

### Step 2 — Aggiungi DNS records su Hostinger

Per worldofmerino.com / merinouniversity.com / perfectmerinoshirt.com (tutti su Hostinger):
1. `https://hpanel.hostinger.com/external-domain/<domain>/dns`
2. Aggiungi prima il **CNAME**:
   - Type: CNAME (dropdown)
   - Name: `tower` (NON il FQDN completo, solo il subdomain)
   - Points to: `<random>.up.railway.app`
   - TTL: 14400 (default)
   - Click "Add Record" → toast "DNS Record created successfully"
3. Aggiungi il **TXT** (più verbose: cerca con `find` "TXT option in DNS type dropdown"):
   - Type: TXT
   - Name: `_railway-verify.tower` (con il dot)
   - Value: `railway-verify=<token>` (intero, incluso il prefix `railway-verify=`)
   - Click "Add Record"

### Step 3 — Verifica DNS propagation

Hostinger DNS è veloce: la risoluzione è **immediata**, non serve aspettare ore. Verifica con `dig`:

```bash
dig +short CNAME tower.worldofmerino.com
# Atteso: <random>.up.railway.app.
dig +short TXT _railway-verify.tower.worldofmerino.com
# Atteso: "railway-verify=<token>"
```

### Step 4 — Aspetta verifica Railway + SSL

Dopo che DNS propaga, **Railway fa polling periodico** per verificare il TXT record. Comportamento osservato:
- **Primo dominio aggiunto al service**: verifica quasi immediata (1-2 min)
- **Secondo dominio aggiunto allo stesso service**: polling più lento (5-10 min). È normale.

Lo stato in dashboard mostra:
- ⚠️ **"Waiting for DNS update"** (giallo) → Railway sta facendo polling, aspetta
- ✅ verde → verificato e attivo

Test endpoint una volta verde:
```bash
# HTTP redirect test
curl -sI http://tower.worldofmerino.com  # → 301 location: https://tower.worldofmerino.com/

# HTTPS con SSL (Let's Encrypt automatico)
curl -s https://tower.worldofmerino.com/health
# Atteso: {"status":"healthy","service":"ai-router","redis":"healthy"}

# Se SSL non ancora valido (cert in emissione, 1-5 min residui):
curl -s -k https://tower.worldofmerino.com/health  # con -k per skip cert verify
```

Durante il binding intermedio (dominio aggiunto, DNS propagato, ma TXT verifica non ancora completata) può rispondere `{"status":"error","code":404,"message":"Application not found"}`. È normale, non è un bug — significa che il proxy Railway riceve la request ma non sa ancora a quale service mapparla.

### Step 5 — Multi-domain per service: OK

Un singolo service Railway può avere multipli custom domain attivi insieme. tower.worldofmerino.com E tower.merinouniversity.com puntano allo stesso service `creative-perfection` senza conflitti. Il proxy Railway termina TLS per entrambi e routa internamente al container.

### Domini verificati al 28/04/2026

| Dominio | Service | Status |
|---|---|---|
| creative-perfection-production-57b5.up.railway.app | creative-perfection | LIVE (default Railway) |
| albeni-ai-orchestration-production.up.railway.app | albeni-ai-orchestration (ml-worker) | LIVE (default) — non esposto pubblicamente in produzione |
| postgres-production-4ce3.up.railway.app | Postgres | LIVE (per public networking) |
| tower.worldofmerino.com | creative-perfection | LIVE con SSL Let's Encrypt |
| tower.merinouniversity.com | creative-perfection | DNS configurato 28/04, Railway in verifica |

---

## Pattern 9 — Railway delete è soft-delete (tombstone ~7 giorni)

`railway delete -p <project_id>` non rimuove immediatamente il progetto dalla lista. Il progetto resta visibile in `railway list` per ~7 giorni come **tombstone** prima di essere eliminato definitivamente.

**Verifica con `--json`**: i progetti deleted hanno `deletedAt` valorizzato:
```bash
railway list --json | python3 -c '
import json, sys
for p in json.load(sys.stdin):
    print(p["id"], p["name"], "deletedAt=" + str(p.get("deletedAt")))
'
# Output:
# d918af00-...  tender-nurturing  deletedAt=2026-04-29T20:00:59.188Z
# e86ec512-...  kind-prosperity    deletedAt=None
```

I progetti con `deletedAt != None` sono in fase di tombstone — già scollegati dai service ma visibili. Dopo ~7 giorni vengono fisicamente rimossi.

**Caso d'uso 2026-04-27**: `tender-nurturing` cancellato. Il progetto resta in `list` ma:
- `/health` non risponde più (container terminato)
- DB+Redis plugin già rimossi prima del delete
- `deletedAt: 2026-04-29T20:00:59Z`

---

## Pattern 10 — Env variables auto-iniettate vs manuali

Railway auto-inietta alcune env vars sui service quando un plugin viene linkato:
- **DATABASE_URL** auto-iniettato sul service main quando linki Postgres plugin
- **REDIS_URL** auto-iniettato quando linki Redis plugin
- **PORT** auto-iniettato (Railway assegna dinamicamente)

**Ma cose manuali**:
- **ML_WORKER_URL** sull'ai-router — DEVI settarla manualmente. Default fallback `http://ml-worker:8000` non funziona su Railway. Causa **silent failures** del forward (vedi Bug 1).
- **DATABASE_PUBLIC_URL** — solo se hai abilitato Public Networking su Postgres plugin.

**Sanity check al deploy**:
```bash
railway variables --service creative-perfection --kv | grep -E '^(ML_WORKER_URL|DATABASE_URL|REDIS_URL)='
# Atteso:
# ML_WORKER_URL=http://albeni-ai-orchestration.railway.internal:8080
# REDIS_URL=redis://default:***@redis.railway.internal:6379
# (DATABASE_URL non serve sull'ai-router, va solo sul ml-worker che è quello che scrive)
```

Se manca `ML_WORKER_URL` su `creative-perfection`, **il forward fallisce silenziosamente** — è la root cause del Bug 1 da 20 giorni.

### Bug 5 — Service account JSON salvato come tab-separated invece che JSON → RESOLVED 2026-04-29

**Symptom**: cron job `albeni-ga4-sync` crashava con `json.decoder.JSONDecodeError: Expecting value: line 2 column 1 (char 2)` su `info = json.loads(inline)` dove `inline = os.environ.get("GA4_SERVICE_ACCOUNT_KEY")`.

**Root cause**: il valore della env var era stato incollato dalla Google Cloud Console in formato **tabella tab-separated** (es. quando si seleziona "Copy as table" o si copia dal pannello UI di GCP) invece che il file `service-account.json` puro. Esempio del valore rotto:

```
\t\n
type\t"service_account"
project_id\t"albeni-1905-ai-bridge"
private_key_id\t"d0daf..."
private_key\t"-----BEGIN PRIVATE KEY-----\n..."
client_email\t"...com"
```

`json.loads()` riceve una stringa che inizia con `\t\n` seguito da righe `key\tvalue` senza graffe né virgole — non è JSON valido.

**Fix automatico** (script salvato in `~/AI STACK APP/scripts/fix_ga4_env.py`):
```python
import os, json
raw = os.environ.get("GA4_SERVICE_ACCOUNT_KEY", "")
result = {}
for line in raw.splitlines():
    if "\t" not in line: continue
    key, val = line.split("\t", 1)
    val = val.strip()
    if val.startswith('"') and val.endswith('"'):
        val = val[1:-1]
    val = val.replace("\\n", "\n")  # decode literal \n in PEM
    if key.strip(): result[key.strip()] = val
# Add defaults if missing
for k, v in {
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "universe_domain": "googleapis.com",
}.items():
    result.setdefault(k, v)
# Save and re-set
with open("/tmp/ga4_fixed.json", "w") as f: f.write(json.dumps(result))
os.chmod("/tmp/ga4_fixed.json", 0o600)
# Then: railway variables --service <svc> --set "GA4_SERVICE_ACCOUNT_KEY=$(cat /tmp/ga4_fixed.json)"
```

**Generalizzazione**: per OGNI service account credential salvato come env var su qualsiasi service (Google, AWS, Stripe, ecc.), VERIFICARE SEMPRE con `json.loads(env_var)` prima del primo deploy. Se il copy-paste è stato fatto con "tab format" invece che "raw text", è da rifare.

**Pattern di prevenzione**:
- Quando salvi un service-account JSON come env var, fai sempre il paste del **contenuto raw del file `.json`** (cat service-account.json | pbcopy → paste)
- Non usare il "Copy as table" della Cloud Console
- Testa subito con `railway run --service <svc> python3 -c "import os, json; json.loads(os.environ['GA4_SERVICE_ACCOUNT_KEY']); print('OK')"`

---

### Bug 6 — Schema mismatch ai SIBLING endpoint (Bug 1bis) → RESOLVED 2026-05-05

**Symptom**: dopo aver fixato `/v1/track/event` (Bug 1, commit `d8ded3d`), per UNA SETTIMANA `intent_intelligence`, `users.assigned_cluster`, `bot_shield_exclusions` sono rimaste a 0 nuove righe nonostante 289 eventi reali catturati. La dashboard mostrava la pipeline ML "ferma".

**Diagnosi (5 mag mattina)**: `railway logs --service albeni-ai-orchestration | tail -200` rivelava il pattern:
```
POST /v1/track/event       → 200 OK   ✓
POST /v1/cluster/predict   → 422 Unprocessable Entity   ✗
POST /v1/adv/shield/analyze → 422 Unprocessable Entity   ✗
POST /v1/intent/calculate  → 422 Unprocessable Entity   ✗
```

**Root cause — schema mismatch sui 3 endpoint sibling**:
1. **`/v1/intent/calculate`**: Pydantic `IDSCalculationRequest` aspettava `{user_id: str, force_recalculate: bool}`. Il widget `albeni-behavioral-engine.js` mandava `{visitor_id, dwell_time_ms, scroll_depth_pct, return_visits, page_url, timestamp, ...}`. Pydantic 422 perché `user_id` mancante e campi extra in strict mode.
2. **`/v1/cluster/predict`**: Pydantic `ClusterPredictionRequest` aspettava `{user_id: str}`. Widget mandava `{visitor_id, domain_type, page_url, return_visits, device, language}`. Stesso problema.
3. **`/v1/adv/shield/analyze`**: l'endpoint usava **query parameters** (`async def adv_shield_analyze(visitor_id: str, ip_address: str, ...)`). Il widget `albeni-ai-tracker.js` faceva `fetch(POST, body: JSON.stringify(shieldData))` → FastAPI 422 perché aspettava query string ma riceveva JSON body.

**Fix unificato (commit `d212db2`)**: tutti e 3 gli endpoint accettano ora un `Dict = Body(...)` e mappano `user_id || visitor_id`:

```python
@app.post("/v1/intent/calculate", response_model=IDSCalculationResponse)
async def calculate_ids(payload: Dict = Body(...), db: DBSession = Depends(get_db)):
    user_id = payload.get("user_id") or payload.get("visitor_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id or visitor_id required")
    force_recalculate = bool(payload.get("force_recalculate", False))
    calculator = IDSCalculator(redis_client, db)
    return await calculator.calculate(user_id, force_recalculate)

@app.post("/v1/cluster/predict", response_model=ClusterPredictionResponse)
async def predict_cluster(payload: Dict = Body(...), db: DBSession = Depends(get_db)):
    user_id = payload.get("user_id") or payload.get("visitor_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id or visitor_id required")
    predictor = ClusterPredictor(redis_client, db)
    return await predictor.predict(user_id)

@app.post("/v1/adv/shield/analyze")
async def adv_shield_analyze(payload: Dict = Body(...), db: DBSession = Depends(get_db)):
    visitor_id = payload.get("visitor_id") or payload.get("user_id") or ""
    ip_address = payload.get("ip_address") or payload.get("ip") or "0.0.0.0"
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    # ... map all signal fields with sensible defaults
    shield = get_bot_shield()
    result = shield.analyze_visitor(visitor_id=visitor_id, ip_address=ip_address, ...)
    return result
```

**Verifica post-fix**:
```bash
# Smoke test: tutti e 3 ora 200 OK
curl -X POST $URL/v1/intent/calculate -d '{"visitor_id":"test","dwell_time_ms":15000}' → HTTP 200
curl -X POST $URL/v1/cluster/predict -d '{"visitor_id":"test","domain_type":"MOFU"}' → HTTP 200
curl -X POST $URL/v1/adv/shield/analyze -d '{"visitor_id":"test","ip_address":"1.2.3.4"}' → HTTP 200

# Real-time logs ml-worker: 422 spariti, tutto 200
railway logs --service albeni-ai-orchestration | tail -50
```

**Lezione critica — generalizzata**: quando si fixa **un endpoint** per Pydantic strict-mode mismatch (Bug 1 fu su `/v1/track/event`), **VERIFICARE SUBITO TUTTI I SIBLING ENDPOINT** chiamati dallo stesso widget JS. La probabilità che 1 endpoint abbia il mismatch e gli altri sibling no è bassissima — di solito il widget è stato scritto in un periodo + lo schema Pydantic in un altro, e il mismatch è sistematico su tutti.

**Procedura preventiva**:
1. Dopo aver fixato un endpoint, fare `railway logs --service <svc> | tail -200 | grep "422\|400"` per vedere se ci sono altri 4xx ricorrenti.
2. Per ogni endpoint POST nel widget JS, verificare che il body matchi il Pydantic model lato server.
3. Pattern raccomandato per endpoint chiamati da widget esterni: usare `Dict = Body(...)` invece di Pydantic strict models — più tollerante, accetta extra fields, mappa user_id||visitor_id, non rompe se il widget evolve schema in futuro.

**Effetto del bug**: per 7 giorni (28 apr → 5 mag), 289 behavioral_signals reali sono finiti in `behavioral_signals` (Bug 1 risolto) ma NON sono mai stati post-processed. Risultato:
- `intent_intelligence` 7d = 0 inserts
- `users.assigned_cluster` ferma a 100 (su 137 totali, 38 senza classificazione)
- `bot_shield_exclusions` ferma a 15 (solo seed)
- Dashboard "ML pipeline downstream" pareva ferma — in realtà era bloccata da 422 silenti.

**Anche pattern affine**: il batch-recalc storico ha avuto timeout (`curl -m 5` saltava) sul primo user con 195 eventi reali → il calcolo IDS sincrono blocca il single-thread async di FastAPI. Per ricalcoli storici di edge-case (user con >100 eventi), preferire un endpoint asincrono dedicato `/v1/intent/recalculate-batch` che usi BackgroundTask di FastAPI o un Celery worker.

---

## Pattern 11 — Cron job + DATABASE_URL internal: usa DATABASE_PUBLIC_URL per cold-start sicuro

**Sintomo**: il cron job `albeni-ga4-sync` (schedule 03:00 UTC, runtime <30s) crashava in 2 secondi con `psycopg2.OperationalError: could not translate host name "postgres.railway.internal" to address: nodename nor servname provided, or not known`.

**Root cause**: `postgres.railway.internal` è il DNS interno della rete privata Railway. Per i service "always-on" (es. ai-router, ml-worker) il DNS interno è risolvibile immediatamente perché il container è già nella rete. Per i **cron job che partono freschi a ogni esecuzione** (cold-start container), la risoluzione DNS interna può:
- Non essere ancora propagata in 2 secondi
- Fallire perché il container del cron job non ha tempo di registrarsi nella rete privata
- Crashare prima che il loop di retry possa aiutare

**Fix**: usare `DATABASE_PUBLIC_URL` (esposto via `*.proxy.rlwy.net:NNNNN`) invece dell'internal URL per cron job.

```bash
# Recupera il public URL del Postgres
DBPUB=$(railway variables --service Postgres --kv | grep '^DATABASE_PUBLIC_URL=' | cut -d= -f2-)

# Setta come DATABASE_URL del cron service - PREFERIRE reference dinamico
# (la stringa statica si rompe alla prima rotation password Postgres - vedi Pattern 12)
railway variables --service albeni-ga4-sync --set 'DATABASE_URL=${{Postgres.DATABASE_PUBLIC_URL}}'
```

**⚠️ "Public endpoint warning" sull'UI Railway**: dopo aver settato la variabile, la dashboard mostra un'icona arancione di warning con tooltip "Public endpoint warning" accanto a `DATABASE_URL`. È **cosmetico e va ignorato** — Railway segnala solo che stai usando il public endpoint invece dell'internal. Per i cron è esattamente quello che vuoi (vedi root cause sopra). Non è un errore di configurazione.

**Trade-off**:
- Public URL aggiunge ~50–100ms di latency vs internal (proxy passa per maglev)
- Per cron job che girano <30s qualche notte è trascurabile
- Non aggiunge costo (Railway non charge il public networking traffic)
- È PIÙ AFFIDABILE per cold-start

**Quando usare quale**:

| Tipo service | DATABASE_URL consigliato |
|---|---|
| Service always-on (ai-router, ml-worker, dashboard) | `${{Postgres.DATABASE_URL}}` (internal) |
| Cron job / scheduled task | `${{Postgres.DATABASE_PUBLIC_URL}}` (public) |
| Worker che si sveglia on-demand | `DATABASE_PUBLIC_URL` (più sicuro) |
| Local dev su Mac | `DATABASE_PUBLIC_URL` (necessario, internal non risolve fuori Railway) |

**Verifica del cold-start setup**:
```bash
# Smoke test del cron job dal Mac (simula cold-start)
cd <repo>
railway run --service <cron-service> python3 -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
print('OK')
"
# Se vedi 'could not translate host name' → cambia a DATABASE_PUBLIC_URL
```

**Caso storico 2026-04-29**: `albeni-ga4-sync` (cron 03:00 UTC) crashava ogni notte da 1+ giorno. Cambiato DATABASE_URL a public → run successiva: 170 ga4_daily rows + 57 ga4_geo_daily rows in 2.64s totale. Funziona.

---

## Pattern 12 — La CLI Railway espande i reference cross-service in stringa statica al `--set`

**Sintomo**: dopo aver eseguito da CLI

```bash
railway variables --service albeni-ga4-sync --set 'DATABASE_URL=${{Postgres.DATABASE_PUBLIC_URL}}'
```

la variabile `DATABASE_URL` su `albeni-ga4-sync` non contiene il template ma la **stringa già espansa** (`postgresql://postgres:fxV1...@maglev.proxy.rlwy.net:39244/railway`). Verificabile via tab Variables → reveal con icona occhio: il valore mostrato è la URL espansa, non il template.

**Conseguenza**: il setup sembra corretto ma è fragile come il valore statico. Alla **prossima rotation password Postgres**, il cron riprende a fallire con `FATAL: password authentication failed` (ricreando il pattern 11 sotto un'altra forma). Questo è esattamente il **silent drift** descritto in `feedback_railway_silent_drift.md`, applicato al livello dei reference invece che del codice.

**Root cause**: la CLI Railway (testato su v4.x, maggio 2026) effettua substitution dei template `${{...}}` al **momento del set**, non li salva come reference vivi. È un bug/feature della CLI, **non della UI**.

**Fix corretto — usare la UI Railway, non la CLI**:

1. Dashboard → progetto → service `albeni-ga4-sync` → tab **Variables**
2. Sui tre puntini `⋯` accanto alla variabile target → **Edit**
3. Cancella completamente il valore espanso
4. Inizia a digitare `${{` — l'editor mostra un autocomplete con i service del progetto
5. Seleziona `Postgres` → poi `DATABASE_PUBLIC_URL`
6. Il campo diventa una "pillola" colorata invece che testo libero
7. Salva con il ✓ verde

**Verifica post-save**: reveal con icona occhio. Il valore deve essere il template `${{Postgres.DATABASE_PUBLIC_URL}}`, non l'URL espansa. Se vedi ancora la URL → ripeti l'edit (a volte la pillola non si forma se l'autocomplete non è stato cliccato).

**"Public endpoint warning" persiste**: l'icona arancione accanto a `DATABASE_URL` rimane anche con il template salvato correttamente. È cosmetico (vedi nota Pattern 11). Non è indicatore di errore.

**Caso storico 2026-05-06**: dopo la fix del 29 apr (Pattern 11) il cron ha funzionato 1 settimana. Tra il 5 mag 16:41 (ultimo deploy del cron) e il 6 mag 05:03 UTC (run schedulato) Railway ha ruotato la password Postgres → run fallito con `FATAL: password authentication failed`. Diagnosi inizialmente puntava a drift di password ma al check le due URL coincidevano (Postgres aveva già aggiornato le sue env). Vero problema: la stringa statica salvata via CLI il 29 apr era stata esposta alla rotation. Ri-applicato il fix con reference dinamico **via UI Railway** il 6 mag 07:50 UTC + redeploy. Run manuale successivo: ✅ "Last run succeeded".

**Regola operativa**: per qualsiasi reference cross-service in Railway (`${{Service.VAR}}`), **usa SEMPRE la UI Railway** per il primo set. Solo modifiche successive di valori non-reference possono passare dalla CLI.

### Bug 2 — Application Passwords disabled on Hostinger WP

`/wp-json/wp/v2/users/me/application-passwords` returns 501 `application_passwords_disabled` on `merinouniversity.com` and `worldofmerino.com`. Cause: a security plugin or `WP_ENVIRONMENT_TYPE` override disables the feature.

**Workaround**: edit via the active session cookie — the user is already logged in to wp-admin. Use the `albeni-wp-operator` skill's CodeMirror pattern to modify WPCode snippets directly, no API key required.

---

## Decision Tree: "Where should this code change live?"

| Change type | Where | Why |
|---|---|---|
| Fix backend Python logic (IDS, cluster predictor, ML) | `ml-worker/services/*.py` → push to GitHub | Auto-deploys to `albeni-ai-orchestration` service |
| Fix routing logic, add new API endpoint | `ai-router/routes/*.js` → push | Auto-deploys to `creative-perfection` |
| Fix dashboard frontend | `ai-router/dashboard/index.html` AND `dashboard/index.html` (keep them in sync via `railway-prebuild.sh`) → push | Both copies needed; build script ships the right one |
| Add env var | Railway dashboard → service → Variables → New Variable | Don't put secrets in `.env` checked into Git |
| Migrate DB schema | Edit `ml-worker/db/init.sql`, then write a migration script and run via `railway run --service Postgres bash -c 'psql ... -f /tmp/migration.sql'` | init.sql only runs on first DB creation |
| Update WP snippet URL | `albeni-wp-operator` skill (CodeMirror in wp-admin) | Direct DB write to the WP_postmeta table where WPCode lives |
| Decommission old project | `railway delete -p <id>` from Mac terminal | Prevent ghost Railway pattern |

---

## Reference: variables expected in `.env` and Railway env

| Variable | Where set | Example |
|---|---|---|
| `DATABASE_URL` | Railway Postgres plugin auto-injected | `postgresql://postgres:***@postgres.railway.internal:5432/railway` |
| `DATABASE_PUBLIC_URL` | Railway Postgres → Networking → Generate Domain | `postgresql://postgres:***@maglev.proxy.rlwy.net:39244/railway` |
| `REDIS_URL` | Railway Redis plugin auto-injected | `redis://default:***@redis.railway.internal:6379` |
| `ML_WORKER_URL` | manual on `creative-perfection` service | `http://albeni-ai-orchestration.railway.internal:8080` |
| `RAILWAY_TOKEN`, `RAILWAY_PROJECT_ID` | local `.env` for scripted ops | from Railway → Account → Tokens |
| `KLAVIYO_API_KEY`, `SHOPIFY_ACCESS_TOKEN`, `SEMRUSH_API_KEY`, `NOTION_API_TOKEN` | per service env vars | from each service provider |
| `GEMINI_API_KEY`, `OPENAI_API_KEY` | ml-worker env | from Google AI Studio / OpenAI Platform |

---

## Reference Files

- `references/cli-cheatsheet.md` — All railway CLI commands grouped by frequency
- `references/troubleshooting.md` — Symptom → diagnosis → fix table
- `references/migration-checklist.md` — Step-by-step Railway project migration template
