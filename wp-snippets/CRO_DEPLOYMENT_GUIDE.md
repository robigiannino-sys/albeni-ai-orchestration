# CRO Engine · Deployment Guide WordPress

Step 7.3 — Roll-out del CRO Engine sui siti WP (MerinoUniversity, WorldOfMerino, PerfectMerinoShirt).

---

## Architettura del rollout

```
┌─────────────────────────────────────────────────────────────────┐
│ Browser visitor (Mac/iPhone)                                     │
│   1. Load pagina WP                                              │
│   2. cro_widget.js scopre tutti i [data-cro-slot]                │
│   3. Per ciascuno fa GET /v1/cro/microcopy?slot=... (no auth)    │
│      → ml-worker seleziona variant via MAB + logga exposure      │
│   4. Sostituisce textContent del DOM con la variant scelta       │
│   5. Su click di [data-cro-conversion-trigger] →                 │
│      POST /wp-json/albeni/v1/cro-conversion (proxy WP firmato)   │
└─────────────────────────────────────────────────────────────────┘
                ↑                                  │
                │                                  ▼
┌──────────────────────────┐         ┌────────────────────────────┐
│ WP server (Hostinger)    │  proxy  │ ml-worker Railway          │
│ - cro_widget.js          │ ──────► │ - GET /v1/cro/microcopy    │
│ - cro_conversion_proxy   │         │ - POST /v1/cro/conversion  │
│   (firma con API_KEY)    │         │ - MAB epsilon-greedy 10%   │
└──────────────────────────┘         └────────────────────────────┘
```

---

## Step 1 · Seed iniziale Postgres

Lancia il seed dopo che `feat(cro)` è deployato su Railway:

```bash
cd "/Users/roberto/Desktop/ALBENI/albeni.com/STEFANO/AI STACK APP/ai-orchestration-layer"
python3 scripts/seed_cro_initial.py --dry-run   # preview
python3 scripts/seed_cro_initial.py             # live
curl -s "https://albeni-ai-orchestration-production.up.railway.app/v1/cro/stats" | python3 -m json.tool
```

Atteso: 3 slot (`homepage_hero_cta`, `newsletter_signup_headline`, `product_card_cta`) con 10 variant totali. Ogni slot ha 1 generic + 1-2 cluster-specifici (heritage_mature, business_professional) + 1 EN per homepage.

---

## Step 2 · Snippet PHP proxy (1 sola volta per ogni dominio)

Su ognuno di **merinouniversity.com / worldofmerino.com / perfectmerinoshirt.com**:

1. WPCode → Add Snippet → PHP Snippet
2. Title: `Albeni CRO Conversion Proxy`
3. Location: `Run Everywhere`
4. Code: incolla `wp-snippets/cro_widget_conversion_proxy.php` (dal `<?php` in poi)
5. Save + Activate

**Constants required** in `wp-config.php` (Hostinger File Manager):

```php
define('ALBENI_API_KEY', 'albeni1905-internal-api-v1');
define('ALBENI_ML_WORKER_URL', 'https://albeni-ai-orchestration-production.up.railway.app');
```

Verifica live:

```bash
curl -X POST "https://merinouniversity.com/wp-json/albeni/v1/cro-conversion" \
  -H "Content-Type: application/json" \
  -d '{"exposure_id": 999999, "conversion_type": "test"}'
```

Atteso: HTTP 404 con body `{"detail":"Exposure not found"}` (proxy gira, ml-worker risponde — l'exposure_id 999999 non esiste, ma il pipeline funziona).

---

## Step 3 · Snippet JS widget (1 sola volta per ogni dominio)

Su ognuno dei 3 siti:

1. WPCode → Add Snippet → JavaScript Snippet
2. Title: `Albeni CRO Adaptive Microcopy Widget`
3. Location: `Site Wide Footer`
4. Auto Insert: enabled (✅)
5. Code: incolla `wp-snippets/cro_widget.js`
6. Save + Activate

**Verifica via console browser** su qualsiasi pagina del sito:

```javascript
sessionStorage.getItem('albeni_cro_session_id')
// Atteso: "cro_1715701234567_xyz123ab"
```

Se non hai cookie/session id, lo crea al primo pageload.

---

## Step 4 · Markup HTML lato editor (per ogni slot che vuoi A/B-testare)

Su **WoM homepage** (esempio):

1. Apri la homepage in Gutenberg
2. Sul blocco H1/heading dell'hero clicca → "Edit as HTML"
3. Aggiungi `data-cro-slot="homepage_hero_cta"`:

```html
<h1 data-cro-slot="homepage_hero_cta">Scopri l'invisible luxury merino</h1>
```

Il testo che hai messo come fallback è **quello che si vede se l'API è down** o se nessuna variant è ancora configurata per quello slot. Best practice: usa il testo della variant `generic_*` come default in HTML.

**Per il CTA di newsletter**:

```html
<form class="newsletter">
  <h3 data-cro-slot="newsletter_signup_headline">Iscriviti al Journal</h3>
  <input type="email" />
  <button data-cro-conversion-trigger="lead" data-cro-value-eur="5.0">Iscriviti</button>
</form>
```

Quando l'utente clicca il button, il widget JS:
1. Cerca l'elemento più vicino con `data-cro-exposure-id` (l'H3 sopra)
2. POSTa la conversion al proxy WP → ml-worker
3. Il MAB incrementa `win_count` della variant servita
4. La prossima volta che un visitor compatible chiede l'headline, il MAB sa che quella variant convertirebbe meglio

---

## Step 5 · Monitoring

Daily snapshot performance:

```bash
curl -s "https://albeni-ai-orchestration-production.up.railway.app/v1/cro/stats" \
  | python3 -m json.tool
```

Da leggere:
- `total_exposures` per slot — quante volte è stato chiamato
- `avg_cr_pct` — CR media dello slot (baseline)
- per ogni variant: `cr_pct` e `lift_vs_avg_pp` — se la differenza è > +3pp e `band: mature` → la variant è vincente

**Promozione manuale di una variant**: quando una raggiunge `band: mature` con `lift_vs_avg_pp > +5pp`, puoi disattivare le perdenti:

```bash
curl -X POST "https://albeni-ai-orchestration-production.up.railway.app/v1/cro/variant" \
  -H "x-api-key: albeni1905-internal-api-v1" \
  -H "Content-Type: application/json" \
  -d '{"slot_key":"homepage_hero_cta","variant_key":"generic_discover","active":false}'
```

L'MAB smetterà di servirla, tutto il traffico va alle attive.

---

## Slot prioritari del primo rollout

| Slot | Pagina | Test ipotesi |
|---|---|---|
| `homepage_hero_cta` | WoM/MU homepage | Tone (legacy vs efficienza vs neutral) influisce sul CTR? |
| `newsletter_signup_headline` | Tutte le pagine con form newsletter | Cluster-specific copy migliora opt-in rate? |
| `product_card_cta` | Collection grid | Investment vs functional language sposta click-through? |

Aggiungere nuovi slot al seed: edit `scripts/seed_cro_initial.py` → run.

---

## Troubleshooting

| Problema | Causa probabile | Fix |
|---|---|---|
| Testo non cambia mai (resta il default HTML) | Slot non esistente o nessuna variant attiva | `curl /v1/cro/stats?slot=X` per verificare |
| Tutti gli utenti vedono la stessa variant | Cold start (<30 esposizioni totali) | Aspetta che il traffico accumuli signal |
| Conversion non registrate | Proxy WP non attivo o constants mancanti | Verifica WPCode snippet active + wp-config.php constants |
| CORS error in console browser | Header CORS ml-worker non permissivo | Già aperto in FastAPI lifespan, verifica `allow_origins` in main.py |
