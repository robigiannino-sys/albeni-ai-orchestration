# Albeni 1905 — Behavioral System Deployment Guide
## 3 Domini Attivi (senza accesso albeni1905.com)

**Data**: 20 Marzo 2026
**Versione**: 2.0 — Sistema Adattivo Completo

---

## Panoramica: Cosa è stato implementato

Il sistema adattivo è ora deployabile su **3 domini** senza bisogno di accesso al frontend di albeni1905.com. L'unico componente non attivabile è il checkout checkout nativo — ma il CRM sync (Klaviyo) funziona ugualmente, e la email sequence BOFU può puntare direttamente ad albeni1905.com/shop.

| Componente | Stato | Note |
|---|---|---|
| Behavioral Tracker (Layer 1) | ✅ Pronto | `albeni-ai-tracker.js` — già esistente |
| Behavioral Engine (Layer 2) | ✅ Nuovo | `albeni-behavioral-engine.js` — IDS + cluster + personalization |
| Content Variants per cluster | ✅ Incluso | Embedded nel Behavioral Engine |
| WordPress snippets (3 domini) | ✅ Pronti | Nella cartella `snippets/wordpress/` |
| Klaviyo CRM route (anonima) | ✅ Aggiornato | `crm.js` ora accetta visitor_id senza email |
| Klaviyo flows config | ✅ Documentato | `snippets/klaviyo-flows-config.json` |
| Control Tower dashboard | ✅ Aggiornato | Banner 3-domini + albeni1905 "pending" |

---

## STEP 1 — Deploy dei Container su Hosting Pubblico

Prima di installare gli snippet WordPress, i container devono essere raggiungibili via HTTPS da internet.

### Opzione A: Railway (consigliata, gratuita per progetti piccoli)

```bash
# Da terminale, nella cartella AI STACK APP/ai-orchestration-layer/
railway login
railway init
railway up
```

Dopo il deploy, Railway ti darà due URL pubblici:
- `https://albeni-ml-worker-xxxx.railway.app` → ML Worker (porta 8000)
- `https://albeni-ai-router-xxxx.railway.app` → AI Router (porta 3000)

### Opzione B: Render.com

1. Vai su render.com → New → Web Service
2. Collega la cartella `ai-orchestration-layer`
3. Crea due servizi separati: `ml-worker` e `ai-router`
4. Imposta le variabili d'ambiente dal file `.env`

### Opzione C: VPS (Hetzner, DigitalOcean)

```bash
# Sul VPS, con Docker installato
scp -r ai-orchestration-layer/ user@vps-ip:/home/albeni/
ssh user@vps-ip
cd /home/albeni/ai-orchestration-layer
docker-compose up -d
# Configura Nginx come reverse proxy per esporre le porte 8000 e 3000
```

---

## STEP 2 — Configura gli URL nei Snippet WordPress

Apri i 3 file snippet nella cartella `snippets/wordpress/` e sostituisci:

```
YOUR_ML_WORKER_URL  →  https://albeni-ml-worker-xxxx.railway.app
YOUR_AI_ROUTER_URL  →  https://albeni-ai-router-xxxx.railway.app
```

---

## STEP 3 — Installa lo Snippet su worldofmerino.com (TOFU)

### Metodo 1: Plugin "Insert Headers and Footers" (raccomandato)

1. WordPress Admin → Plugin → Cerca "Insert Headers and Footers" → Installa e attiva
2. Settings → Insert Headers and Footers
3. Sezione **"Scripts in Header"**: incolla il contenuto di `snippet-worldofmerino-TOFU.html`
4. Salva

### Metodo 2: Elementor Pro

1. Elementor → Site Settings → Custom Code
2. Aggiungi nuovo snippet → Location: "Head"
3. Incolla il contenuto di `snippet-worldofmerino-TOFU.html`

### Metodo 3: functions.php (sviluppatori)

```php
function albeni_add_tracking() {
    echo '<script>window.ALBENI_AI = { endpoint: "https://YOUR_ML_WORKER_URL", klaviyoEndpoint: "https://YOUR_AI_ROUTER_URL", domain_type: "tofu", debug: false };</script>';
    echo '<script src="https://YOUR_AI_ROUTER_URL/albeni-ai-tracker.js" defer></script>';
    echo '<script src="https://YOUR_AI_ROUTER_URL/albeni-behavioral-engine.js" defer></script>';
}
add_action('wp_head', 'albeni_add_tracking');
```

---

## STEP 4 — Installa lo Snippet su merinouniversity.com (MOFU)

Stessa procedura del TOFU, usando `snippet-merinouniversity-MOFU.html`.

**Azione aggiuntiva**: Aggiungi `data-albeni-article-end` all'ultimo elemento di ogni articolo/guida. In Elementor: Advanced → Custom Attributes → `data-albeni-article-end|`.

---

## STEP 5 — Installa lo Snippet su perfectmerinoshirt.com (BOFU)

Stessa procedura usando `snippet-perfectmerinoshirt-BOFU.html`.

**Azioni critiche per massimizzare IDS**:

### 5a — Selettore peso (WooCommerce)
Il selettore del peso (150g / 190g) dovrebbe avere `name="weight"`. Se usi variazioni WooCommerce, questo è già il comportamento default.

### 5b — Tabella di confronto 150g vs 190g
```html
<div class="comparison-table" data-albeni-comparison>
  <!-- Tabella esistente 150g vs 190g -->
</div>
```

### 5c — Sezione specifiche tecniche
```html
<section class="product-specs" data-albeni-tech-spec>
  <!-- 17 micron, Super 120's, certificazioni -->
</section>
```

### 5d — Contenuti personalizzati per cluster (headline)

Aggiungi questi attributi agli elementi che vuoi personalizzare automaticamente:

| Elemento | Attributo da aggiungere |
|---|---|
| H1 principale | `data-albeni-hero-title` |
| Sottotitolo / subheadline | `data-albeni-hero-sub` |
| Bottone CTA principale | `data-albeni-cta-primary` |
| Link secondario | `data-albeni-cta-secondary` |
| Paragrafo value prop | `data-albeni-value-prop` |
| Riga social proof | `data-albeni-trust` |

In **Elementor**: seleziona l'elemento → Advanced → Custom Attributes:
```
data-albeni-hero-title|
```
(il valore dopo il `|` può essere lasciato vuoto — il JS lo scrive lui)

---

## STEP 6 — Configura Klaviyo

### 6a — Crea le Custom Properties nel profilo Klaviyo

1. Klaviyo Dashboard → Audience → Properties
2. Aggiungi queste proprietà (vedi `klaviyo-flows-config.json` per dettagli):
   - `albeni_cluster` (string)
   - `albeni_ids_score` (number)
   - `albeni_ids_stage` (string)
   - `albeni_domain_path` (string)
   - `albeni_visitor_id` (string)
   - `albeni_return_visits` (number)

### 6b — Crea i Flow (da klaviyo-flows-config.json)

Crea questi 5 flow in Klaviyo → Flows → Create Flow:

1. **BOFU Conversion Flow** (priorità 1) — Trigger: Metric `BOFU_Intent_Threshold_Reached`
2. **MOFU Consideration Flow** — Trigger: Metric `MOFU_Consideration`
3. **TOFU Welcome Series** — Trigger: Metric `TOFU_Entry`
4. **Post-Purchase CX** — Trigger: WooCommerce Purchased (via albeni1905.com, attivabile quando disponibile)
5. **Win-Back** — Trigger: 60 giorni inattività

Per ogni flow, usa le subject line e i blocchi contenuto specificati in `klaviyo-flows-config.json`.

### 6c — Verifica variabile KLAVIYO_API_KEY

Nel file `.env` nella cartella `ai-orchestration-layer/`, assicurati che sia configurata:
```
KLAVIYO_API_KEY=pk_xxxxxxxxxxxxxxxxxxxx
```

---

## STEP 7 — Serve gli script JS da AI Router

Il Behavioral Engine deve essere servito dall'AI Router come file statici, così gli snippet WordPress possono caricarlo via `<script src="...">`.

### Nel docker-compose, il volume è già configurato:
```yaml
ai-router:
  volumes:
    - ./dashboard:/app/dashboard:ro
```

### Aggiungi la cartella tracking come static:
1. Copia i file JS nella cartella `dashboard/`:
```bash
cp ai-orchestration-layer/tracking/albeni-ai-tracker.js \
   ai-orchestration-layer/dashboard/
cp ai-orchestration-layer/tracking/albeni-behavioral-engine.js \
   ai-orchestration-layer/dashboard/
```

2. In `server.js`, aggiungi la route statica (già presente per `/dashboard`):
   Il file `server.js` serve già i file dalla cartella `/app/dashboard`.
   I file JS saranno disponibili a:
   - `https://YOUR_AI_ROUTER_URL/albeni-ai-tracker.js`
   - `https://YOUR_AI_ROUTER_URL/albeni-behavioral-engine.js`

---

## STEP 8 — Test di Verifica

### Test 1: Behavioral Engine attivo
Apri la console del browser (F12) su uno dei 3 domini con debug attivo:
```javascript
// Temporaneamente in config
window.ALBENI_AI = { ..., debug: true };
```
Dovresti vedere: `[Albeni BE] Behavioral Engine initialized`

### Test 2: IDS calculation
Dopo 15 secondi sulla pagina:
```javascript
window.albeniEngine.getIDS();  // Dovrebbe restituire un numero 0-100
window.albeniEngine.getCluster();  // Dovrebbe restituire un cluster name
```

### Test 3: Klaviyo sync (da perfectmerinoshirt.com)
```javascript
// Simula IDS sopra soglia
window.albeniEngine.forceSync();
// Controlla la console per "Klaviyo sync complete"
```

### Test 4: Content personalization
```javascript
// Verifica che gli elementi con data-albeni-* siano stati aggiornati
document.querySelector('[data-albeni-hero-title]').textContent
// Dovrebbe mostrare il testo del cluster rilevato
```

### Test 5: Control Tower
Apri `localhost:3000` — dovresti vedere il banner "3 DOMINI ATTIVI" nella Dashboard KPI.

---

## Checklist deployment

- [ ] Container deployati su hosting pubblico (Railway / Render / VPS)
- [ ] URL pubblici configurati nei 3 snippet WordPress
- [ ] Snippet installato su worldofmerino.com
- [ ] Snippet installato su merinouniversity.com
- [ ] Snippet installato su perfectmerinoshirt.com
- [ ] Attributi `data-albeni-*` aggiunti agli elementi chiave delle 3 pagine
- [ ] `data-albeni-article-end` aggiunto agli articoli di merinouniversity.com
- [ ] File JS copiati in `ai-orchestration-layer/dashboard/`
- [ ] KLAVIYO_API_KEY configurata nel `.env`
- [ ] Custom Properties create su Klaviyo
- [ ] 5 Flow creati su Klaviyo (da klaviyo-flows-config.json)
- [ ] Test di verifica completati sui 3 domini

---

## Note su albeni1905.com

Quando avrai accesso al frontend di albeni1905.com, l'attivazione richiede solo:
1. Installare lo stesso snippet con `domain_type: 'bofu_heritage'`
2. Attivare il trigger WooCommerce `Purchase_Completed` per il flow Post-Purchase
3. Il routing BOFU del sistema già indirizza verso albeni1905.com per Heritage Mature e Italian Authentic cluster

Tutto il resto del sistema è già funzionante e colleziona dati comportamentali dai 3 domini attivi.

---

*Generato da AI Control Tower · Albeni 1905 AI Orchestration Layer v2.0*
