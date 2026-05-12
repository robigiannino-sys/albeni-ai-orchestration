---
title: Test case 007 — "Quando il mercato dà ragione al guardaroba che dura"
url: https://worldofmerino.com/quando-il-mercato-da-ragione-al-guardaroba-che-dura/
published: 2026-04-28
validated: 2026-05-12
validator_version: wom-radar-validator v1.0 (rubric v1.0)
---

# Test case 007 — Rincaro lana australiana 40% / good spec lines

## Output validator

```yaml
verdetto: HARD_FAIL
score: 61  # calcolato per analisi; HARD_FAIL triplo: regex §1.2 + CTA assente + score < 70
cluster_bersaglio_dichiarato: non dichiarato
cluster_bersaglio_inferito: C3 (Conscious Premium)
cluster_match: true (lessico C3 forte, registro PASS)

hard_fail_triggers:
  - check: regex_blacklist_1_2
    pattern: '\bin un''epoca in cui\b'
    location: "par. 'Una notizia economica, letta culturalmente'"
    match_letterale: |
      "In un'epoca in cui ottanta consumatori su cento dichiarano
      comportamenti value-seeking — cercare valore, non sconto — il
      rincaro della materia prima naturale è la prova economica di una
      verità che il mondo del quiet luxury osserva da sempre"
    motivo: |
      PRIMO E UNICO match letterale della regex §1.2 nei 5 Radar analizzati.
      Conferma che la blacklist v1.0 funziona, ma è troppo stretta: la stessa
      cadenza retorica appare in forma alternativa in 005 ("Immagina un
      mondo in cui") e in modo semantico nei restanti 3 Radar.

  - check: cta_assente
    location: fine articolo
    motivo: |
      Chiusura osservativa-aforistica ("Sta dicendo, per chi vuole ascoltare,
      che il guardaroba che dura — e che invecchia bene — non è una nostalgia.
      È, di nuovo, una scelta razionale.") senza CTA Lead Magnet C3. Stesso
      pattern strutturale di tutti i precedenti 4 test case.

  - check: score_sotto_soglia
    location: globale
    score_calcolato: 61
    motivo: |
      Score 61 < 70 → HARD_FAIL anche per soglia. Triplo trigger.

soft_fail_penalties:
  - check: antitesi_cascata_semantica
    location: "globale (4 occorrenze)"
    penalty: -8
    instances:
      - "Non è un'opinione, è un fixing." (par. 1, post-apertura)
      - "comprare meno, comprare bene non è una postura morale, è aritmetica" (par. 'Una notizia economica')
      - "Il rincaro della lana, quindi, non è il trionfo del lusso ostentato. È la validazione del lusso invisibile." (par. 'La validazione')
      - "non è una nostalgia. È, di nuovo, una scelta razionale." (closer)
    note: |
      Quinto Radar consecutivo (su 5) con antitesi cascata semantica. Pattern
      al 100% sui 5 Radar analizzati. La cadenza "non X, è Y" / "non è X. È Y"
      è il marker AI-tell più costante della voce pre-validator. Rubric v1.1
      DEVE formalizzare questa cadenza come HARD_FAIL trigger, non SOFT_FAIL.

  - check: em_dash_eccesso
    location: "globale (3 em-dash, 2 paragrafi con >1)"
    penalty: -10
    instances:
      - "value-seeking — cercare valore, non sconto —" (doppio em-dash, par. 'Una notizia economica')
      - "Sa che quel capo costa di più — e durerà di più" (par. 'La validazione')
      - "il guardaroba che dura — e che invecchia bene —" (doppio em-dash, closer)
    note: |
      Densità em-dash 0.76 per 100 parole. Pattern di "incidentale narrativa".
      Quinto Radar consecutivo con questo pattern.

  - check: apertura_narrativo_meditativa
    location: prima frase
    penalty: -8
    note: |
      "C'è una parola che ritorna nelle aste di Sydney e Fremantle, in queste
      settimane. I buyer la pronunciano sottovoce: good spec lines." Apertura
      narrativa con suspense ("la pronunciano sottovoce") prima del fatto
      ancorante (rincaro 40%, 2019). Tecnicamente PASS §1.5 (toponimi Sydney/
      Fremantle nei primi 25 parole), ma stesso problema di registro visto
      in 001, 002, 004, 006.

  - check: chiusura_aforistica_concettuale
    location: ultime due frasi
    penalty: -5
    note: |
      "Il mercato ha smesso di essere un fondale: è entrato nella scena, e
      ha preso parola. Sta dicendo, per chi vuole ascoltare, che il guarda-
      roba che dura — e che invecchia bene — non è una nostalgia. È, di
      nuovo, una scelta razionale." Combinazione di personificazione del
      mercato ("ha preso parola") + antitesi finale + "di nuovo" come
      ammicco al lettore consapevole. Cadenza AI-typical.

  - check: quartina_enumerativa
    location: "par. 'Una notizia economica', tre/quattro chili + mesi"
    penalty: -5
    instances:
      - "Una pecora produce tre, quattro chili di vello all'anno"
      - "Ci vogliono mesi di pascolo, di selezione, di tosatura, di lavaggio"
    note: |
      Due enumerazioni quartinarie consecutive ("tre, quattro chili" è doppio
      numero retorico; "pascolo, selezione, tosatura, lavaggio" è quartina
      di sostantivi).

cluster_fingerprint:
  lessico_match: 8/min3
    # fixing, prezzi (+40%), 2019, cost-per-wear (×2), "comprare meno comprare
    # bene" (variante di "meno ma meglio"), durata implicita ("dieci stagioni",
    # "nove mesi"), value-seeking, merino — tutto C3.
  registro_match: PASS
    # Date e numeri presenti (40%, 12 mesi, 2019, 3-4 chili, 10 stagioni, 80%
    # consumatori, 9 mesi). Verbi C3 ("dimostrare", "misurare" via "misura
    # del valore"). Logica didattica con H2 espliciti.
  cta_correct: false (assente)

word_count: 393
length_verdict: PASS (target 300-500)

action_required:
  - "RIMUOVERE 'In un'epoca in cui ottanta consumatori su cento dichiarano comportamenti value-seeking' → riformulare in 'Otto consumatori su dieci dichiarano comportamenti value-seeking (cercare valore, non sconto): in questo contesto il rincaro della materia prima è prova economica di...'. Eliminare il connettore retorico §1.2."
  - "AGGIUNGERE CTA Lead Magnet C3: dopo la chiusura, rimando esplicito a 'Filiera Reda: 270 anni di responsabilità' come prosecuzione dell'argomento 'cost-per-wear' / 'lana di qualità'"
  - "RIDURRE antitesi cascata da 4 a max 1: la più forte ('comprare meno, comprare bene non è una postura morale, è aritmetica') può restare se è l'unica; le altre 3 vanno riformulate in forma affermativa"
  - "RIDURRE em-dash da 3 a max 2: convertire em-dash incidentali in virgole"
  - "RISCRIVERE l'apertura in registro journalistico: 'Sui mercati di Sydney e Fremantle i prezzi della lana australiana sono saliti del 40% in 12 mesi, ai livelli più alti dal 2019. I buyer parlano di good spec lines: lotti di qualità superiore, scarsi e cercati.'"
  - "RIFORMULARE chiusura: rimuovere personificazione del mercato ('ha preso parola') e antitesi finale. Sostituire con osservazione fattuale + CTA: 'A 40% in 12 mesi, il guardaroba che dura non è scelta culturale ma matematica. Per capire come una filiera certificata costruisce questa durata, leggi Filiera Reda: 270 anni di responsabilità.'"

deploy_clearance: false
```

## Note di calibrazione

### Forza del pezzo (da preservare)
- **Dato di apertura forte**: "good spec lines" + rincaro 40% in 12 mesi + livelli dal 2019. C'è la notizia, c'è il numero, c'è la fonte (aste di Sydney/Fremantle). Tesi forte.
- **Lessico C3 forte**: 8+ termini cluster, registro tecnico-economico.
- **Tesi falsificabile**: "comprare meno comprare bene è aritmetica, non postura morale" è una tesi quantificabile.
- **Lunghezza in target**: 393 parole.

### Importanza diagnostica del Radar 007
È l'**UNICO** dei 5 a fare scattare un trigger letterale della regex v1.0 (§1.2 "in un'epoca in cui"). Questo conferma che:
1. **La rubric v1.0 funziona** quando il pattern compare letteralmente.
2. **La rubric v1.0 è insufficiente** perché solo 1/5 Radar HARD_FAIL viene catturato da regex letterali — gli altri 4/5 sono identificati solo via convenzione "CTA assente" o via score threshold con penalità soft.

→ Senza l'estensione semantica della v1.0 in v1.1, il validator funziona come "gate CTA" più che come "detector AI-tell". L'80% del lavoro è fatto dalla regola CTA, non dai pattern di voce.

## Implicazioni FINALI per Rubric v1.1 (consolidato 5/5 test case)

### Pattern strutturali confermati al 100% (5/5 Radar)
1. **CTA Lead Magnet assente** — sempre.
2. **Em-dash usato come parentesi narrativa** — sempre, densità 0.4-1.1 per 100 parole.
3. **Antitesi cascata semantica** — 5/5 (con pattern "non X, è Y" / "non è X. È Y").
4. **Chiusura aforistica/morale meditativa** — sempre, in 5 varianti diverse.

### Pattern frequenti (4/5 Radar)
5. **Apertura narrativo-letteraria invece di journalistica** (manca solo in 003).
6. **Triadi/quartine enfatiche** (manca solo in 003).
7. **Score teorico nella fascia 59-79** (cluster tight: HARD_FAIL strutturale, non casuale).

### Pattern strutturale unico (1/5)
8. **Match letterale regex v1.0** (solo 007, §1.2 "in un'epoca in cui").

### Soglie di azione consigliate per Rubric v1.1
- §1.6 nuovo: `cta_assente` come HARD_FAIL formale (frequenza 100% lo conferma).
- §1.7 nuovo: `lunghezza > 800` come riclassifica Story automatica (3/5 violano, 100% di chi lo fa è erroneo).
- §1.3 esteso: regex semantica antitesi (frequenza 100%, in 4/5 forme diverse).
- §1.8 nuovo: regex "apertura narrativo-letteraria" (frequenza 80%, registro magazine-cover).
- §1.2 esteso con varianti: "Immagina un mondo in cui", "Non è X: è Y" come connettore.

### Pattern micro da aggiungere come soft-fail
- "Forse la [N] più [agg]" — variante chiusura morale (vista in 004 e 006)
- "ha preso parola" / "è entrato nella scena" — personificazione del mercato/sistema (007)
- "di nuovo" come ammicco al lettore consapevole (007, ma anche in altri)
- "(in queste settimane|in questi giorni)" come ambiguità temporale che evita la data (007)

## Anti-exemplar per il scanner

La frase "Il mercato ha smesso di essere un fondale: è entrato nella scena, e ha preso parola. Sta dicendo, per chi vuole ascoltare..." è un **anti-exemplar di personificazione del mercato + ammicco al lettore**. Da inserire nel prompt scanner come pattern bocciato — il mercato non parla, è la voce dell'AI che pretende di tradurre.
