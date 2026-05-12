---
title: Test case 003 — "Comprare meno, comprare vero: divieto UE invenduto"
url: https://worldofmerino.com/comprare-meno-comprare-vero-divieto-ue-invenduto/
published: 2026-04-23
validated: 2026-05-12
validator_version: wom-radar-validator v1.0 (rubric v1.0)
---

# Test case 003 — Divieto UE distruzione invenduto (ESPR 19 luglio 2026)

## Output validator

```yaml
verdetto: HARD_FAIL
score: 79  # calcolato per analisi; HARD_FAIL via trigger esplicito (CTA assente)
cluster_bersaglio_dichiarato: non dichiarato
cluster_bersaglio_inferito: C3 (Conscious Premium)
cluster_match: true (lessico forte, registro corretto)

hard_fail_triggers:
  - check: cta_assente
    location: fine articolo
    motivo: |
      Sezione di chiusura "Cosa fare oggi" propone CTA comportamentale (tre
      gesti concreti) ma NON rimanda al Lead Magnet di cluster. C3 atteso:
      CTA verso "Filiera Reda: 270 anni di responsabilità" oppure "Tracciabilità
      filiera lana". La chiusura osservativa-aforistica ("Il lusso invisibile
      comincia da questa domanda") si limita a una formula identitaria.

soft_fail_penalties:
  - check: costrutto_antitetico_borderline
    location: "paragrafo 'L'Invisible Luxury anticipa la legge', ultima frase"
    penalty: -5
    note: |
      "Il 19 luglio non è solo una data: è il momento in cui la durata diventa
      un requisito, non un optional." Costrutto antitetico cliché (non solo X:
      è Y) + binomio enfatico (requisito, non optional). La regex v1.0 cerca
      "non è (solo|soltanto) ... è (anche|piuttosto)" — qui chiude con "è il
      momento", quindi non matcha letteralmente, ma il pattern semantico è lo
      stesso. → Candidato Rubric v1.1.

  - check: triade_enfatica
    location: "paragrafo 'L'Invisible Luxury anticipa la legge'"
    penalty: -5
    note: |
      "meno, meglio, più a lungo" — tre termini in cadenza ritmica come slogan.
      Tipico AI-tell di chiusura concettuale.

  - check: chiusura_aforistica
    location: ultima frase
    penalty: -5
    note: |
      "Il lusso invisibile comincia da questa domanda." Formula identitaria
      brand-statement come closer. Non è chiusura morale universale, ma è
      cadenza retorica AI-typical. Vicina al pattern "in fondo, X è quel che
      conta".

  - check: analogia_poetica_AI
    location: "paragrafo 'Cosa fare oggi', terzo gesto"
    penalty: -3
    note: |
      "chiedere tracciabilità al proprio guardaroba come la si chiede al proprio
      caffè" — analogia food-as-metaphor tipica del registro magazine. Per un
      C3 dovrebbe essere sostituita con un dato concreto (es. "chiedere il
      paese di origine della lana e il lanificio di tessitura").

  - check: meta_editoriale_titolo
    location: "H2 'Perché la notizia vale più di una notizia'"
    penalty: -3
    note: |
      Titolo di sezione meta-editoriale ("vale più di una notizia"). Pattern
      vicino al "vale la pena" già visto in test case 001. Per C3 il titolo
      dovrebbe ancorare al fatto/dato (es. "I numeri: 630 milioni in Francia,
      20 milioni di resi in Germania").

cluster_fingerprint:
  lessico_match: 8/min3
    # ESPR, Commissione Europea, UE, durata, tracciabilità, Cost Per Wear,
    # certificazione, regolamento — tutti termini C3 espliciti
  registro_match: PASS
    # Date precise (9 feb 2026, 19 lug 2026, 2030, feb 2027), numeri (250
    # dipendenti, 630M€, 20M resi, 200 utilizzi, 5 anni), verbi C3 ("dichiarare",
    # "produrre", "smaltito"), logica didattica con H2 espliciti.
  cta_correct: false (assente)

word_count: 410  # in target 300-500 per Radar
length_verdict: PASS

action_required:
  - "AGGIUNGERE CTA Lead Magnet C3 prima della chiusura: rimando a 'Filiera Reda: 270 anni di responsabilità' come prosecuzione del 'chiedere tracciabilità al proprio guardaroba'"
  - "RIMUOVERE costrutto antitetico 'non è solo una data: è il momento' → sostituire con frase fattuale ('Dal 19 luglio la durata è requisito di legge, non solo scelta culturale')"
  - "DEPOWERIZZARE triade 'meno, meglio, più a lungo' → mantenere ma riformulare come bullet logica, non slogan ('meno volumi, meno smaltimento, vita più lunga del capo')"
  - "SOSTITUIRE analogia 'come al caffè' con istruzione operativa concreta ('verificare il paese di origine della lana e il lanificio di tessitura')"
  - "RIFORMULARE H2 'Perché la notizia vale più di una notizia' → titolo fattuale ('I numeri: 630M€ di prodotti distrutti in Francia, 20M di resi smaltiti in Germania')"

deploy_clearance: false
```

## Note di calibrazione

### Punti forti (da preservare)
- **Densità fattuale C3 esemplare**: 8+ date precise, 5+ cifre concrete, fonti nominate (Commissione UE, Business of Fashion, CMS Law-Now, ESG Today) — registro tecnico molto vicino al target C3.
- **Lessico cluster**: 8 termini su min 3 — il pezzo è inequivocabilmente C3.
- **Lunghezza in target**: 410 parole, dentro al range Radar.
- **Apertura corretta**: prima frase ancora alla data esplicita "19 luglio 2026" senza nominalismi astratti.

### Differenza vs test case 001 (10.4 micron)
Il Radar 003 è meno hyperbole-saturo del 001 — non ha antitesi a cascata, non ha "vale la pena" multipli, non ha apertura narrativo-letteraria. La causa di HARD_FAIL è singola: **CTA Lead Magnet assente**. Se la CTA fosse stata aggiunta correttamente, il pezzo avrebbe chiuso a score 79 → SOFT_FAIL editabile, non HARD_FAIL ricreabile.

→ Conferma: il problema strutturale ricorrente sui Radar pre-validator è **l'omissione sistematica della CTA al Lead Magnet di cluster**. Pattern da elevare a HARD_FAIL formale in Rubric v1.1 (oggi è solo nel formato output di esempio in §4.3, non nei trigger §1.X).

### Implicazioni per Rubric v1.1
- **Formalizzare cta_assente come HARD_FAIL §1.6**: spostare il trigger dalla §4.3 esempio output ai trigger espliciti.
- **Aggiungere pattern antitetico semantico**: la regex v1.0 cattura solo "non è solo X è anche/piuttosto Y" — estendere a "non è solo/soltanto X: è Y" (con due punti) e a "non più X, ora Y".
- **Pattern triade-slogan**: aggiungere come soft-fail formale "tre termini in virgola che chiudono un paragrafo concettuale" (oggi è loggato come "triade_enfatica" ma non è specificato il match).

## Cosa salvare come anti-exemplar per il scanner

La chiusura "Cosa fare oggi" + "Il lusso invisibile comincia da questa domanda" può essere anti-exemplar di **closer C3 sbagliato**: didattico ma orfano del Lead Magnet. Da contrastare con un exemplar PASS che includa la CTA esplicita ("Per capire come una filiera certificata costruisce questa durata, leggi 'Filiera Reda: 270 anni di responsabilità'").
