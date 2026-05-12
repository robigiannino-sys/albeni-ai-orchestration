---
title: WoM Radar Validator — Rubric
purpose: Tabelle dettagliate, pattern, fingerprint per cluster, formule di scoring
status: v1.0 — 2026-05-12
upstream: voice-baseline-wom-radar.md v0.3, wom-radar-voice-config.md v1.0
---

# WoM Radar Validator — Rubric dettagliata

Questo file contiene tutti i dettagli operativi che la skill `wom-radar-validator` SKILL.md richiama.

---

## 1. HARD-FAIL pattern list (regex/string match)

### 1.1 Superlativi e parole-bandiera

```
\b(rivoluzionari[oae]|straordinari[oae]|incredibil[ei]|epocali?|iconic[oae])\b
\bmust[\s-]have\b
\bintramontabil[ei]\b
\b(deve|deveono) avere\b
\bogni guardarob[ao]\b
```

### 1.2 Connettori retorici AI

```
\bnon è un caso che\b
\bnon a caso\b
\bin un'epoca in cui\b
\bin un mondo (in cui|dove)\b
\bnel cuore di\b
```

### 1.3 Costrutti antitetici cliché

```
non si tratta solo di .{1,40}? si tratta di
non è (solo|soltanto) .{1,40}? è (anche|piuttosto)
```

### 1.4 Chiusure morali

```
\buna lezione (che|da)\b
\bvale la pena ricordare (che|quanto)\b
\bil segreto (è|sta in)\b
\bin fondo,? .{1,30}?$
\balla fine,? .{1,30}? è quel che conta\b
```

### 1.5 Aperture problematiche

- Prima frase termina con "?"  → HARD_FAIL
- Prime 25 parole non contengono NESSUNO dei seguenti:
  - Una data esplicita (es. "il 6 maggio", "nel 2026", "Q1 2026", "ad aprile")
  - Un nome proprio (azienda, persona, ente: McKinsey, Deloitte, Reda, Confartigianato, ESPR, AgResearch, ecc.)
  - Un numero o percentuale ("53%", "45,3%", "12 ore", "270 anni")
  - Una fonte nominata ("Il Deloitte Corporate Travel Study", "secondo McKinsey", "La nota di Fibre2Fashion")
  → HARD_FAIL

---

## 2. Cluster fingerprint — i 5 profili

Per ogni cluster, una "scheda di riconoscimento" che il validator usa per controllare il TOV.

### 2.1 C1 — Business Professional

**Lessico cluster atteso** (≥ 3 termini nel testo):
- viaggi, viaggio, business travel, micro-trip
- ore, giornata, calendario, agenda, ritmo
- ufficio, meeting, blazer, giacca, dress code
- performance, efficienza, focus, produttività
- portamento, comfort, traspirazione
- finance, consulting, tech, professionisti

**Registro atteso**:
- Frasi medio-corte, alternanza
- Verbi al presente indicativo, attivi
- Pochi avverbi modali
- Tono affermativo, non riflessivo

**Lead Magnet CTA atteso**:
- "Business Layering Guide"
- Varianti accettate: "Guida 150g vs 190g per uso business", "Layering Guide professionale"

**Lessico NON atteso (penalità)**:
- "Reda" come protagonista (è C2 territory)
- Termini emotivi ("emozione", "sogno", "passione")
- Termini eco-ideologici ("salvare", "responsabilità verso il pianeta")

### 2.2 C2 — Heritage Mature

**Lessico cluster atteso** (≥ 3 termini nel testo):
- filiera, distretto, Biella, biellese
- tradizione, generazioni, pratica continuativa, eredità
- pettinato, cardato, filato, tessitura
- Reda, Cerruti, Vitale Barberis Canonico, lanificio
- Made in Italy, Camera della Moda, Confartigianato, CNA
- nobile, raffinato, custodire, tramandare

**Registro atteso**:
- Frasi più articolate, più lunghe
- Subordinate frequenti
- Lessico colto, ma non barocco
- Ritmo lento e meditato

**Lead Magnet CTA atteso**:
- "La Guida Definitiva ai Tessuti Nobili"
- Varianti accettate: "Guida ai filati nobili", "Tradizione tessile italiana"

**Lessico NON atteso (penalità)**:
- "Performance", "ROI" (territorio C1)
- "Capsule", "essential" (territorio C4)
- Termini esplicitamente sostenibilità-driven (territorio C3)

### 2.3 C3 — Conscious Premium

**Lessico cluster atteso** (≥ 3 termini nel testo):
- LCA, ciclo di vita, biodegradabilità, biodegradabile
- emissioni, CO2, microplastiche, polimero
- durata, costo per utilizzo, lavaggi, anni di uso
- certificazione, tracciabilità, ZQ, RWS, ESPR
- impatto, normativa, direttiva, Commissione, EU
- "meno ma meglio", consapevole, durevole

**Registro atteso**:
- Numeri e dati ovunque
- Verbi "misurare", "attestare", "dimostrare", "certificare"
- Frasi che evitano emotività
- Logica didattica esplicita

**Lead Magnet CTA atteso**:
- "Filiera Reda: 270 anni di responsabilità"
- Varianti accettate: "Tracciabilità filiera lana", "Sostenibilità del Merino superfine"

**Lessico NON atteso (penalità)**:
- Termini emotivi/ideologici ("salvare il pianeta", "responsabilità etica")
- Slogan ambientalisti
- "Eco-friendly" generico

### 2.4 C4 — Modern Minimalist

**Lessico cluster atteso** (≥ 3 termini nel testo):
- capsule, essentials, wardrobe, guardaroba minimalista
- silhouette, caduta, drappeggio, taglio, fit
- palette, neutro, bianco, grigio, blu profondo
- ratio, signal, density, sottrarre
- cut & sewn, costruzione, sartoriale
- Sunspel, Asket, Outlier, Margiela (riferimenti brand minimalist)

**Registro atteso**:
- Frasi corte, dense
- Frasi nominali ammesse ("Bianco. Grigio chiaro.")
- Pochi aggettivi, molti sostantivi
- Niente decorazione retorica

**Lead Magnet CTA atteso**:
- "Wardrobe Essentials — Minimalist Edition"
- Varianti accettate: "Capsule Edition", "Wardrobe Minimal Guide"

**Lessico NON atteso (penalità)**:
- Storytelling lungo
- Aggettivi emotivi ("emozionante", "sorprendente")
- Tono colloquiale FAQ (territorio C5)

### 2.5 C5 — Italian Authentic

**Lessico cluster atteso** (≥ 3 termini nel testo):
- "sì davvero", "davvero", domande implicite
- lavatrice, programma lana, asciugatura, stiratura
- quotidiano, tutti i giorni, capo di tutti i giorni
- pizzicare, scaldare, pesare, deformarsi
- città italiane (Milano, Torino, Roma, Bologna)
- "non torna indietro", "ha provato", "vale la pena provare"

**Registro atteso**:
- Frasi più parlate
- Parentesi esplicative ("(sì davvero)")
- FAQ-style intermezzi
- Tono pratico, concreto, casalingo

**Lead Magnet CTA atteso**:
- "Guida all'uso quotidiano (150/190)"
- Varianti accettate: "Guida pratica quale peso", "150 vs 190 nel quotidiano"

**Lessico NON atteso (penalità)**:
- Anglicismi non necessari ("performance", "efficiency", "wardrobe")
- Lessico accademico/scientifico (territorio C3)
- Tono editoriale alto (territorio C2)

---

## 3. Formula di scoring

```
score_iniziale = 100

per ogni hard_fail_trigger trovato:
    return HARD_FAIL (score non viene calcolato)

per ogni soft_fail_penalty:
    score -= penalty

per ogni occorrenza in:
    em_dash_eccesso (>1 per paragrafo): -5 cad.
    triade_enfatica: -5 cad.
    paragrafo_senza_entita: -8 cad.
    paragrafo_senza_numeri: -8 cad.
    aggettivo_superlativo_soft: -3 cad.
    cadenza_uniforme: -5

penalità_lunghezza:
    se word_count < 250: -10
    se word_count > 550: -10
    se 250 ≤ word_count ≤ 299: -5
    se 501 ≤ word_count ≤ 550: -5

penalità_cluster_fingerprint:
    se lessico_cluster_match < 3: -15
    se registro_cluster_fail: -10
    se cta_lead_magnet_wrong_cluster: HARD_FAIL (vedi sopra)

VERDETTO:
    se score ≥ 85: PASS
    se 70 ≤ score < 85: SOFT_FAIL
    se score < 70: HARD_FAIL
```

---

## 4. Esempi pratici di output

### 4.1 PASS

```yaml
verdetto: PASS
score: 92
cluster_bersaglio_dichiarato: C1
cluster_match: true

hard_fail_triggers: []

soft_fail_penalties:
  - check: em_dash_eccesso
    location: "paragrafo 3"
    penalty: -5
    fix_suggerito: "Sostituire uno dei due em-dash con due punti o virgola"
  - check: aggettivo_superlativo_soft
    location: "paragrafo 2, frase 'risultato significativo'"
    penalty: -3
    fix_suggerito: "Sostituire 'significativo' con il dato concreto"

cluster_fingerprint:
  lessico_match: 5/min3
  registro_match: PASS
  cta_correct: true

action_required:
  - "Edit minore consigliato: ridurre em-dash in paragrafo 3"
  - "Edit minore consigliato: sostituire 'significativo' con dato"

deploy_clearance: true
```

### 4.2 SOFT_FAIL

```yaml
verdetto: SOFT_FAIL
score: 76
cluster_bersaglio_dichiarato: C3
cluster_match: true

hard_fail_triggers: []

soft_fail_penalties:
  - check: paragrafo_senza_entita
    location: "paragrafo 2"
    penalty: -8
    fix_suggerito: "Aggiungere nome di ente, brand o studio nel paragrafo (es. citare McKinsey o Textile Exchange)"
  - check: lessico_cluster_match
    location: "globale"
    penalty: -15
    fix_suggerito: "Lessico C3 atteso (LCA, biodegradabilità, costo per utilizzo). Solo 2 termini trovati su 3 richiesti. Aggiungere 1 termine specifico."
  - check: paragrafo_senza_numeri
    location: "paragrafo 4"
    penalty: -8
    fix_suggerito: "Aggiungere una cifra concreta (es. anni di durata, percentuale di riduzione)"

cluster_fingerprint:
  lessico_match: 2/min3
  registro_match: PASS
  cta_correct: true

action_required:
  - "Aggiungere ancoraggio fattuale al paragrafo 2"
  - "Aumentare lessico C3 (almeno 1 termine in più)"
  - "Aggiungere dato numerico al paragrafo 4"

deploy_clearance: false  # richiede correzione manuale prima del deploy
```

### 4.3 HARD_FAIL

```yaml
verdetto: HARD_FAIL
score: 0  # non calcolato
cluster_bersaglio_dichiarato: C4
cluster_match: false

hard_fail_triggers:
  - check: blacklist_parole
    location: "paragrafo 1, prima frase: 'In un'epoca in cui il guardaroba si rivoluziona...'"
    motivo: "Contiene sia 'in un'epoca in cui' (connettore retorico) che 'rivoluziona' (superlativo). Doppio AI-tell."
  - check: cluster_tov
    location: "globale"
    motivo: "Il testo è in tono editoriale lungo (territorio C2), ma cluster bersaglio dichiarato è C4 (high signal/low noise). Mismatch totale di registro."
  - check: cta_assente
    location: "fine articolo"
    motivo: "Nessuna CTA verso Lead Magnet identificata."

cluster_fingerprint:
  lessico_match: 1/min3
  registro_match: FAIL
  cta_correct: false

action_required:
  - "Rigenerare da zero con voice config C4 (high signal/low noise) attivata"
  - "Far girare di nuovo merino-news-scanner Phase 4 con few-shot C4 enforced"

deploy_clearance: false
```

---

## 5. Lista pattern AI-tell secondari da monitorare (non hard-fail ma da loggare)

Pattern che non sono hard-fail ma che, se compaiono frequentemente nei Radar passati dal validator, indicano drift della voce. Da monitorare e considerare per aggiunta al hard-fail in futuro:

- "in qualche modo", "in un certo senso" — riempitivi
- "vale la pena considerare" — preambolo ridondante
- "ciò che è interessante", "quello che colpisce" — meta-commento editoriale
- "non sorprende che", "come prevedibile" — riempitivo
- "in altre parole", "tradotto" (oltre la prima occorrenza) — ridondanza
- "una traiettoria che", "un cambiamento che" — riempitivo astratto
- Sequenze di tre virgole in una frase singola — sovraccarico

---

## 6. Note di calibrazione

- I valori delle penalità (5, 8, 10, 15) sono iniziali e vanno tarati su una ventina di Radar reali nelle prime 4 settimane.
- Le soglie (85 PASS, 70 SOFT_FAIL) sono iniziali — vanno strette o allargate sulla base della distribuzione effettiva.
- Se più del 30% dei Radar si concentra su un cluster solo, la pipeline di generazione va riequilibrata, non i pesi del validator.
