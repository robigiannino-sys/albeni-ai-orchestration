---
title: Albeni 1905 — Voice Baseline Universale (Linee guida pubblicazione contenuti)
purpose: Single source of truth per il tone of voice, anti-AI-tell, cluster TOV e regole di chiusura applicabili a TUTTI i formati di contenuto Albeni (Radar, Story, Osservatorio, MU checklist/scorecard, customer care, drip email, ADV creative). Da consultare ogni volta che si produce contenuto pubblicabile.
status: v1.0 — 2026-05-12
upstream:
  - voice-baseline-wom-radar.md v0.3 (5 exemplar C1-C5 cluster-mapped)
  - wom-radar-validator/rubric-v1.1.md (8 estensioni regex hard-fail)
  - wom-radar-validator/findings-7-radar-pre-v1.1.md (7 anti-exemplar consolidati)
mandatory_reads_for_skills:
  - merino-news-scanner
  - mu-content-deployer
  - wom-page-deployer
  - albeni-mt-translator
  - albeni-mt-validator
  - albeni-wp-operator
mandatory_inject_for_ai_stack_agents:
  - Content AI Layer (via content_generator.py SYSTEM_PROMPT_BASE)
  - Content Validator (via content_validator.py hard-fail regex)
  - Customer Care AI (via DOMAIN_SYSTEM_PROMPTS)
---

# Albeni 1905 — Voice Baseline Universale

Questo documento è la **fonte unica** per le linee guida di voce applicabili a ogni contenuto Albeni pubblicato. Quando una skill o un agente produce contenuto (Radar, Story, Osservatorio, checklist, email, risposta customer care, ADV copy), DEVE leggere o avere iniettato questo file prima di emettere output.

Per dettagli format-specific, vedere i riferimenti in §4.

---

## 1. Cluster TOV (5 profili comportamentali) — UNIVERSALE

Albeni 1905 ha 5 cluster comportamentali. Ogni contenuto deve essere clusterizzato e applicare il TOV del cluster bersaglio.

| Cluster | Bersaglio | TOV | Lessico chiave | Verbi chiave | Lead Magnet |
|---------|-----------|-----|----------------|---------------|-------------|
| **C1 Business Professional** | Frequent corporate traveler, finance/consulting/tech | Chiaro, solido, autorevole. Frasi medio-corte. Tono affermativo, non riflessivo. | viaggi, calendario, ore, ufficio, blazer, dress code, performance, efficienza, focus | misurare, reggere, dimostrare, ottimizzare | Business Layering Guide (150g/190g) |
| **C2 Heritage Mature** | 45+, sensibile al Made in Italy, distretto biellese | Culturale, profondo, elegante. Frasi articolate, subordinate. Ritmo lento, meditato. Lessico colto non barocco. | filiera, distretto, Biella, tradizione, generazioni, pettinato, lanificio, Reda/Cerruti/VBC, Made in Italy | tramandare, custodire, lavorare, ricondurre | La Guida Definitiva ai Tessuti Nobili |
| **C3 Conscious Premium** | Consumatore sustainability-aware, evidence-driven | Didattico, fattuale, NON ideologico. Numeri ovunque. Verbi tecnici. Evita emotività. Logica didattica esplicita. | LCA, ciclo vita, biodegradabilità, certificazione, ESPR, Cost Per Wear, tracciabilità | misurare, durare, attestare, certificare, dichiarare | Filiera Reda — 270 anni di responsabilità |
| **C4 Modern Minimalist** | Capsule wardrobe, low-noise high-signal | High signal / low noise. Frasi corte, dense. Frasi nominali ammesse. Pochi aggettivi, molti sostantivi. Niente decorazione retorica. | capsule, silhouette, caduta, palette, ratio, signal, density, cut & sewn | scegliere, sostituire, sottrarre, semplificare | Wardrobe Essentials — Minimalist Edition |
| **C5 Italian Authentic** | Quotidiano italiano, pratico | Quotidiano, concreto, FAQ-style. Parentesi esplicative ("sì davvero"). Tono casalingo. Niente anglicismi non necessari. | lavatrice, programma lana, quotidiano, città italiane, "sì davvero", "vale la pena provare" | provare, lavare, indossare, usare | Guida all'uso quotidiano (150/190) |

**Regola d'oro**: se un contenuto colpisce due cluster, scegliere il primario (più convertibile sul Lead Magnet).

---

## 2. Anti-AI-tell — REGOLE UNIVERSALI HARD FAIL

Qualunque contenuto generato deve **NON contenere** i seguenti pattern. Questi sono trigger HARD FAIL: se compaiono, riscrivere prima di emettere.

### 2.1 Superlativi e parole-bandiera vietate
- rivoluzionario, straordinario, incredibile, epocale, iconico
- must-have, deve avere, ogni guardaroba, intramontabile

### 2.2 Connettori retorici AI-tell
- "non è un caso che", "non a caso"
- "in un'epoca in cui", "in un mondo dove/in cui", "nel cuore di"
- "Immagina un mondo/un'epoca/un futuro in cui"
- "Non è utopia/fantascienza/magia: è ..."

### 2.3 Antitesi cascata semantica (3+ occorrenze = HARD FAIL)
Pattern vietati in cascata (≥3 occorrenze nel pezzo):
- "Non X, ma Y" / "Non X, è Y"
- "Non è X: è Y" / "Non è X. È Y"
- "Non è X, non è Y, non è Z. È W" (anafora tripartita)
- "X è precedente a Y. Y è precedente a Z. Z è precedente a W." (quartina anaforica metafisica)

**Soglia**: UNA singola antitesi è SOFT (penalty), 3+ è HARD FAIL cascata.

### 2.4 Chiusure morali/aforistiche vietate
- "una lezione che" / "Forse la X più Y"
- "vale la pena ricordare / sottolineare / fissare / considerare"
- "in fondo + verbo cognitivo (valga, merita)"
- "Era solo bastato dirlo / capirlo / notarlo"
- "È di nuovo / davvero / finalmente una Y razionale / necessaria"
- "comincia / nasce da questa domanda / gesto / scelta"
- "porta in sé l'impronta / traccia / memoria di"

### 2.5 Aperture problematiche
- Prima frase termina con "?" (domanda retorica)
- Prime 25 parole senza data esplicita / nome proprio / numero / fonte nominata
- Apertura narrativo-letteraria invece di journalistica:
  - "C'è un X che Y"
  - "Immagina un mondo/futuro/capo in cui"
  - "Per N giorni/anni, Y ha smesso/cominciato"
  - "Quando il/la X incontra/si chiude"
  - "In/Dentro un mondo X che/in cui/dove"

### 2.6 Pattern micro da limitare (max 1 occorrenza, soft fail >3)
- Personificazione mercato/sistema/industria ("Il mercato ha preso parola")
- Ammicco al lettore consapevole ("di nuovo", "come sapevamo", "per chi vuole ascoltare")
- Ambiguità temporale ("in queste settimane", "in questi giorni") — preferire date assolute
- Meta-spiegazione lessicale ("La parola corretta è X: a volte letterale, più spesso metaforica")
- Disclaimer retorico post-apertura ("Non è X: è Y" come seconda frase)

---

## 3. 4 regole-base distillate (LEGGI SEMPRE PRIMA DI GENERARE)

1. **L'apertura ancora al fatto, non alla scena.** Mai aprire con "C'è un X che", "Immagina", "Quando il X incontra", "Per N giorni Y ha". Sempre aprire con: data + soggetto + verbo + numero/fonte.

2. **L'antitesi è UNA, non quattro.** Una contrapposizione punta una tesi; quattro la sviluppano in slogan. Se serve dire "non X, ma Y" più di una volta nel pezzo, riformulare almeno N-1 in forma affermativa.

3. **La chiusura è una CTA al Lead Magnet del cluster, non una lezione.** Ultima frase = rimando esplicito al Lead Magnet del cluster bersaglio (vedi §1). Mai "Forse la lezione più", "Era solo bastato", "comincia da questa domanda".

4. **Il mercato non parla, le persone parlano.** Vietate personificazioni di soggetti astratti ("il mercato dice", "l'industria sussurra"). Il soggetto narrante è il giornalista/autore, le fonti sono enti concreti (McKinsey, Commissione UE, AgResearch, Reda).

---

## 4. Format-specific overrides — quando consultare cosa

| Formato | Word count | Voice file format-specific | Validator skill |
|---------|------------|----------------------------|------------------|
| **Radar WoM** (news, lifestyle) | 300-550 | `merino-news-scanner/references/wom-radar-voice-config.md` v1.1 | `wom-radar-validator/rubric-v1.1.md` |
| **Story WoM** (long-form, narrative) | 800-1500 | TBD (voice-baseline-wom-story.md) | TBD |
| **Osservatorio MU** (technical analysis, news) | 800-1200 | TBD (voice-baseline-mu-osservatorio.md) | TBD |
| **MU Checklist/Scorecard** (structured) | 200-400 | TBD (voice-baseline-mu-structured.md) | TBD |
| **MU Guide** (pillar, evergreen) | 1500-3000 | TBD (voice-baseline-mu-guide.md) | TBD |
| **Customer Care** (chatbot reply) | 2-5 frasi | TBD (voice-baseline-customer-care.md) | inline check |
| **Email drip** (Klaviyo) | 50-150/email | TBD (voice-baseline-email.md) | inline check |
| **ADV creative** (Meta/Google ads) | 30-90 | TBD (voice-baseline-adv.md) | inline check |
| **Translated content** (DE/FR/EN) | varia | glossario Reda/Albeni + cluster TOV invariato | albeni-mt-validator |

**Per i formati TBD**: applicare comunque §1, §2, §3 di questo file come baseline universale. Specifiche format-specific verranno aggiunte progressivamente man mano che si validano case real-world.

---

## 5. CTA standard (per ogni cluster)

Formato CTA universale: `→ **Approfondisci**: [Lead Magnet name] — [tagline di posizionamento]`

| Cluster | Lead Magnet | Tagline esempio |
|---------|-------------|-----------------|
| C1 | Business Layering Guide | quando 150g e quando 190g |
| C2 | La Guida Definitiva ai Tessuti Nobili | cosa rende un filato nobile davvero |
| C3 | Filiera Reda — 270 anni di responsabilità | cosa misurare quando si parla di tracciabilità |
| C4 | Wardrobe Essentials — Minimalist Edition | la capsule che dura cinque anni |
| C5 | Guida all'uso quotidiano (150/190) | quale peso per la tua città |

---

## 6. 7 Anti-exemplar consolidati (case study bocciati dal validator)

Per ciascuno: testo bocciato (estratto reale da Radar pre-validator), pattern coinvolto, correzione attesa. Da consultare prima di scrivere per evitare di riprodurre questi pattern.

**Estratti dal file `wom-radar-validator/findings-7-radar-pre-v1.1.md`** — vedere lì per il dettaglio completo. Sintesi:

1. **Apertura magazine-cover** (Radar 005, "fine usa-e-getta"): "Immagina un mondo in cui ogni capo che viene prodotto deve trovare qualcuno che lo indossi. Non è utopia: è il regolamento europeo ESPR."

2. **Apertura narrativo-meditativa** (Radar 006, "anima dell'acqua Biella"): "C'è un modo vecchio di dire 'Made in Italy' che suona come un timbro."

3. **Antitesi cascata** (Radar 001, "10.4 micron"): "Qui non si celebra il capo, ma la fibra. Non il designer, ma il pastore. Non la passerella, ma la tosatura."

4. **Quartina anaforica metafisica** (Radar 006): "L'acqua è precedente al lanificio. Il lanificio è precedente al brand. Il brand è precedente al capo."

5. **Quartina enfatica ripetuta come slogan** (Radar 004, "salone della materia"): "Pietra, petalo, legno, spugna. Origine, sensualità, funzione, reinvenzione." (ripetuto 2 volte)

6. **Chiusura aforistica meta-editoriale** (Radar 004): "Forse la lezione più semplice che il Salone 2026 ci ha lasciato è questa: il lusso non è ciò che si vede da lontano. Era solo bastato dirlo."

7. **Personificazione del mercato + ammicco al lettore** (Radar 007, "guardaroba che dura"): "Il mercato ha smesso di essere un fondale: è entrato nella scena, e ha preso parola. Sta dicendo, per chi vuole ascoltare, che il guardaroba che dura non è una nostalgia. È, di nuovo, una scelta razionale."

---

## 7. Self-check pre-publish (9 voci)

Prima di emettere qualunque contenuto editoriale, eseguire mentalmente questo check:

```yaml
voice_pre_publish_check:
  - blacklist_v11_hard_fail_clear: true           # §2.1, 2.2, 2.4 puliti
  - apertura_ancora_al_fatto_NOT_scena: true      # §3 regola 1
  - antitesi_max_1_in_pezzo: true                 # §3 regola 2, §2.3
  - chiusura_e_CTA_NOT_lezione: true              # §3 regola 3, §2.4
  - cluster_TOV_riconoscibile: true               # §1 lessico+registro applicato
  - CTA_present_correct_lead_magnet: true         # §5 CTA cluster-specifica
  - word_count_target_format: true                # §4 entro target format
  - no_personificazione_mercato: true             # §2.6, §3 regola 4
  - no_disclaimer_post_apertura: true             # §2.6 "Non è X: è Y" seconda frase
```

Se anche UNA voce è `false`, riscrivere prima di emettere.

---

## 8. Versioning e maintenance

Questa baseline universale è la **versione corta** dei file più dettagliati. Quando un pattern AI-tell nuovo viene rilevato in produzione:
1. Aggiungerlo prima al file format-specific (es. wom-radar-voice-config v1.2)
2. Promuoverlo a baseline universale solo se confermato cross-format
3. Aggiornare anche il content_validator.py di ml-worker (AI Tower side)

Owner: Roberto Giannino. Validatore tecnico: wom-radar-validator skill (Claude side) + content_validator agent (Gemini side).
