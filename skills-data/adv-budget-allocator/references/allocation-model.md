# ADV Allocation Model — framework matematico

> Riscritto il **2026-07-27**. La versione precedente (10/04/2026) era ferma all'era Albeni:
> envelope €30K su 18 mesi, mercati DE/US/IT/UK/FR, `funnel_multiplier` che citava "Albeni CTA"
> — un termine oggi vietato nel copy. Il pivot micron-è di giugno 2026 l'aveva resa falsa in
> ogni sua riga di budget.

## Parametri di budget — capsula micron-è, lancio settembre 2026

| Parametro | Valore | Fonte |
|---|---|---|
| Envelope ADV totale | **€5.000 EU** | Piano lancio capsula 302 pz |
| Split mercati | **DE 50% · IT 30% · FR 20%** | Piano lancio |
| Fase pre-lancio (ramp) | seed indicizzazione pagine prioritarie | — |
| Fase lancio (set 2026) | picco su BOFU/conversione | — |
| Fase post-lancio (sustain) | tapering, redistribuzione ai gap residui | — |
| CR paid | 5,0% | validato |
| CR organico | 1,5% | validato |

Il phasing dell'envelope sui tre momenti **non è ancora stato deciso da Roberto**: assumerne uno
(es. ramp 20% / lancio 45% / sustain 35%) è legittimo, ma va **dichiarato nel report**, non
spacciato per dato. `monthly_budget` = quota della fase attiva; la matematica sotto è agnostica.

**Stato in produzione (allineato il 30/07/2026).** Fino a quella data `advBudgetAllocator.js`
girava sull'envelope pre-pivot — €30.000 su 18 mesi, cinque mercati con US 25% e UK 12% — e
`/v1/adv` rispondeva con quei numeri: il modello riscritto il 27/07 non era mai arrivato nel
codice. Ora total e split mercati sono quelli di questa tabella. Le tre fasi portano una
ripartizione **uniforme (€1.667 · €1.667 · €1.666)** marcata `TODO(phasing)`: è un segnaposto in
attesa della decisione, e va sostituita qui e nel codice nello stesso passaggio.

**US e UK non sono nell'envelope.** L'envelope è EU. Se un report li nomina, sta usando il
modello vecchio.

## Pesi keyword per cluster

**Uniformi dal 2026-07-30.** È una scelta dichiarata, non un dato mancante.

| Cluster | Tema KW | Peso |
|---|---|---|
| A: Scienza Materiali | merino wool, 17,6 micron, cheratina, termoregolazione | 0,1667 |
| B: Costruzione Design | taglio e cucito, vestibilità, confezione | 0,1667 |
| C: Origini Etiche | lana sostenibile, filiera tracciabile, RWS | 0,1667 |
| D: Innovazione | tecnologia merino, tessuto tecnico | 0,1667 |
| E: Lab Pratico | cura merino, grammatura, guardaroba capsula | 0,1667 |
| F: Governance Heritage | lana made in Italy, tessuti italiani | 0,1665 |

Con pesi uguali, `gap_score` si riduce al `non_indexed_ratio`: l'allocazione la decide il dato
misurato dalla crawl map GSC invece di una distribuzione di volume che sappiamo sbagliata. Sullo
scan 2026-07-08 la ripartizione diventa A 17,7% · B 9,1% · C 21,3% · D 10,7% · E 21,5% · F 19,7%
(prima: A 27,8% · B 6,1% · C 21,5% · D 4,8% · E 26,5% · F 13,2%).

### Perché i pesi precedenti sono stati ritirati

I pesi 0,28/0,12/0,18/0,08/0,22/0,12 derivavano dalle 62 head-term L1 su **cinque** mercati, e il
**69% di quel volume era US+UK** — mercati fuori dall'envelope EU. Pesavano una domanda che non
compriamo.

### Perché non sono stati sostituiti con pesi EU ricalcolati

Verificato il 2026-07-30 sulla `keyword-matrix.csv` (snapshot SEMrush 16/04/2026):

- 61 delle 150 KW hanno volume DE/IT/FR: **85.510/mese**.
- Ma solo **24** sono assegnate a `merinouniversity.com` o `worldofmerino.com` — i soli domini nella
  crawl map, quindi i soli che l'allocatore compensa — per **13.020/mese**. Il resto (84%) è
  assegnato ad `albeni1905.com` (dominio morto) e a PMS: domanda commerciale che oggi appartiene
  allo store, non a contenuti MU/WoM.
- Quelle 24 KW coprono **tre cluster su sei**: C, E, F. A, B e D restano a zero, e il 64% del
  sottoinsieme è una sola keyword (`capsule wardrobe`, 6.600 DE).
- Adottarli metterebbe **A a peso zero**, cioè zero budget al cluster con 29 pagine non indicizzate
  su 299 — il gap più grande dell'ecosistema.

Audit completo delle 61 KW con cluster, dominio assegnato e volumi per mercato:
`albeni-seo-agent/shared-resources/kw-cluster-weights-eu-2026-07-30.csv`.

### Come si torna a pesi differenziati

Serve un pull SEMrush su DE/IT/FR delle head-term dei cluster editoriali — quelle che la matrice
di aprile non copre. Il pull è già scritto e parametrizzato:

```
export SEMRUSH_API_KEY=...
python3 scripts/pull_cluster_weights_semrush.py            # dry-run: unità e costo
python3 scripts/pull_cluster_weights_semrush.py --confirm
```

69 righe su tre database, **~690 unità API**, e stampa la tabella pronta da incollare qui e in
`ai-router/middleware/advBudgetAllocator.js`. Al 30/07/2026 il piano SEMrush è a **zero unità**
(`ERROR 132`), quindi lo script si ferma da sé prima di consumare.

Il perimetro semantico autorevole su *quali* termini contano resta la memoria di progetto
`microne-termini-da-difendere` (27/07): brand defense, semantic moat, cluster C4>C2>C1, difesa
negativa.

> **I pesi vivono in due posti.** Questo documento e `CLUSTER_KW_WEIGHTS` in
> `ai-router/middleware/advBudgetAllocator.js`, che è la copia che gira in produzione: fino al
> 30/07/2026 le due erano divergenti e solo la seconda contava. Chi cambia i pesi cambia entrambe.

## Formula del gap score

```
Per ogni cluster c:
  non_indexed_ratio(c) = pagine_non_indicizzate(c) / pagine_totali(c)
  gap_score(c)         = non_indexed_ratio(c) × peso_kw(c)
  normalized_gap(c)    = gap_score(c) / Σ gap_score(tutti i cluster)
  allocazione(c)       = normalized_gap(c) × monthly_budget
```

Le pagine escluse dai guardrail non entrano nei totali (le toglie già `refresh_cluster_map.py`).

### Esempio numerico — dati reali scan 2026-07-08, budget ipotetico €1.000

| Cluster | Tot | Idx | Non-idx | Ratio | Peso | Gap | Norm. | €/mo |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 299 | 270 | 29 | 0,097 | 0,1667 | 0,0162 | 0,177 | €177 |
| B | 20 | 19 | 1 | 0,050 | 0,1667 | 0,0083 | 0,091 | €91 |
| C | 77 | 68 | 9 | 0,117 | 0,1667 | 0,0195 | 0,213 | €213 |
| D | 17 | 16 | 1 | 0,059 | 0,1667 | 0,0098 | 0,107 | €107 |
| E | 68 | 60 | 8 | 0,118 | 0,1667 | 0,0197 | 0,215 | €215 |
| F | 213 | 190 | 23 | 0,108 | 0,1665 | 0,0180 | 0,197 | €197 |
| **Tot** | **694** | **623** | **71** | | | **0,0915** | **1,000** | **€1.000** |

Ricalcolato il 30/07/2026 con i pesi uniformi. Il gap_score totale scende da 0,0977 a **0,0915**:
è il solo effetto del cambio di pesi, la copertura è la stessa dello scan 08/07.

Confronto con l'esempio della versione di aprile: allora il gap_score totale era **0,856**, contro
0,09 di oggi — un ordine di grandezza in meno. È la misura di quanto il problema si sia ridotto:
nell'aprile 2026 l'ecosistema era invisibile, oggi è coperto al ~90%. **Una run che produce numeri
simili a quelli di aprile sta leggendo dati stantii.**

## Curva di transizione a 30 giorni

Quando il verdict GSC passa NEUTRAL → PASS:

```
paid_budget = allocazione_iniziale × max(0, (30 - giorni_da_indicizzazione) / 30)
```

Giorno 0 → 100% · 10 → 67% · 15 → 50% · 20 → 33% · 30 → €0.

Il budget liberato si redistribuisce prima alle pagine non indicizzate dello stesso cluster,
poi agli altri cluster se il cluster d'origine è completo.

## Priorità a livello pagina

```
page_priority(p) = kw_volume(p) × funnel_multiplier(p) × urgency_multiplier(p)

funnel_multiplier:
  BOFU (CTA verso lo store micron-e.com)      = 1,5
  MOFU (MU didattico, checklist)              = 1,2
  TOFU (WoM editoriale, storie)               = 1,0

urgency_multiplier:
  non indicizzata da >30 giorni               = 1,3
  pubblicata da ≤30 giorni                    = 1,0
  in transizione (appena indicizzata)         = 0,5 decrescente
```

## Guardrail

| Regola | Valore | Perché |
|---|---|---|
| Allocazione minima | €5/mese | sotto questa soglia le piattaforme non ottimizzano |
| Allocazione massima | 15% del mensile | evita la concentrazione su una pagina sola |
| Pagine escluse | home, FAQ, contatti, cookie/privacy, manifesto, category, lead-magnet, legal | hanno già percorsi organici o non sono pagine di contenuto |
| Soglia zero | indicizzata da >30 giorni | nessun paid dove l'organico è stabile |
| **Soglia di apertura campagna** | **< €200/mese totali → non aprire** | il costo di setup e gestione supera il beneficio: meglio Request Indexing manuale + interlinking |

L'ultima regola è nuova (27/07). Nasce da un caso reale: la compensazione calcolata per l'intero
perimetro L1+L2 era **una pagina a €150/mese**. Aprire una campagna per quello non ripaga.
Quando il totale è sotto soglia, il report deve dirlo e raccomandare le leve organiche.

## Metriche da tracciare

1. **Paid coverage rate** — % di pagine non indicizzate che ricevono budget
2. **Transition velocity** — giorni medi da pubblicazione a indicizzazione, con e senza paid
3. **Budget efficiency** — € spesi per pagina-indicizzazione
4. **Organic takeover rate** — pagine/mese che completano il ciclo paid→organic
5. **Freed budget** — € cumulati liberati dall'organico, riallocabili

## Nota di rotta

L'obiettivo di lungo periodo di questa skill è **azzerarsi**: quando tutte le pagine sono
indicizzate e stabili, l'envelope si sposta su retargeting e difesa BOFU e l'allocator va in
letargo. Con l'89,6% di copertura, quel punto è vicino. Se una run futura produce un'allocazione
grande, il primo sospetto deve essere un dato vecchio, non un peggioramento reale.
