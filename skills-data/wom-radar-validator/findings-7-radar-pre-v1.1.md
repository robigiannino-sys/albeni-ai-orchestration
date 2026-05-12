---
title: Findings consolidati — 7 Radar pre-validator (2 + 5 nuovi)
status: input per Rubric v1.1
validated: 2026-05-12
test_cases_inclusi:
  - 2026-04-28-10-4-micron.md (001)
  - 2026-04-28-bleisure-genz.md (002)
  - 2026-04-23-divieto-ue-invenduto.md (003)
  - 2026-04-28-salone-materia.md (004)
  - 2026-04-28-fine-usa-getta.md (005)
  - 2026-04-28-anima-acqua-biella.md (006)
  - 2026-04-28-guardaroba-che-dura.md (007)
---

# Findings consolidati — 7 Radar pre-validator

## Risultati aggregati

| ID | Slug | Cluster | Word count | Verdict | Score | Trigger principale |
|----|------|---------|------------|---------|-------|--------------------|
| 001 | 10-4-micron | C2 | 950 | HARD_FAIL | 45 | Story length + antitesi cascata + chiusura morale + CTA assente |
| 002 | bleisure-genz | C1 | ~900 | HARD_FAIL | 36 | CTA assente + em-dash + triadi enfatiche + Story length |
| 003 | divieto-ue-invenduto | C3 | 410 | HARD_FAIL | 79 | CTA assente (singolo trigger) |
| 004 | salone-materia | C2 | 916 | HARD_FAIL | 0 | Story length + antitesi cascata × 5 + CTA assente |
| 005 | fine-usa-getta | C3 | 494 | HARD_FAIL | 74 | Apertura magazine-cover + CTA assente |
| 006 | anima-acqua-biella | C2 | 372 | HARD_FAIL | 59 | CTA assente + score < 70 (multipli soft-fail) |
| 007 | guardaroba-che-dura | C3 | 393 | HARD_FAIL | 61 | Regex §1.2 letterale + CTA assente + score < 70 |

**Distribuzione verdetti: 7/7 HARD_FAIL (100%)**.
Score medio: 50.6. Range: 0–79. Mediana: 59.

## Pattern strutturali al 100% (7/7 Radar)

### P1 — CTA Lead Magnet assente
Frequenza: 7/7 (100%).
Pattern: chiusura sempre osservativa/aforistica/comportamentale, mai rimando esplicito al Lead Magnet di cluster.
**Implicazione**: il scanner pre-validator NON ha mai chiuso un Radar con CTA cluster. Pattern strutturale 100%, non difetto sporadico.
**Azione Rubric v1.1**: spostare `cta_assente` dai trigger di esempio §4.3 ai trigger formali §1.6 con motivazione "Lead Magnet del cluster bersaglio non identificato in alcun paragrafo dell'articolo".

### P2 — Em-dash come parentesi narrativa
Frequenza: 7/7 (100%).
Densità media: 0.7 em-dash per 100 parole (range 0.4–1.1).
Pattern: l'em-dash NON è usato come marcatore tecnico (elenco, range numerico, attribuzione), ma come "parentesi letteraria" che incastona considerazioni narrative.
Esempi cross-Radar:
- 001: "soglia tecnica, ma — più ancora — una soglia narrativa"
- 002: (multipli)
- 003: "che hanno retto cinque anni — sono la prova"
- 004: "lana merino — fibra naturale, rinnovabile, termoregolante, riparabile"
- 005: "claim ambientali generici e non verificabili — eco-friendly, sostenibile, verde —"
- 006: "E ce n'è uno nuovo — o forse antichissimo —"
- 007: "value-seeking — cercare valore, non sconto —"
**Azione Rubric v1.1**: mantenere §3 em-dash > 1/paragrafo come soft-fail, ma aggiungere check di **densità globale** (>0.5/100w = -10 cumulativo).

### P3 — Antitesi cascata semantica
Frequenza: 7/7 (100%) se si conta in forma generalizzata; 4/5 nei nuovi Radar (manca solo in 003, il più asciutto).
Pattern letterale: "non X, è Y" / "non è X. È Y" / "Non è X: è Y" / "non si tratta solo di X, si tratta di Y".
La regex v1.0 §1.3 cerca solo `non si tratta solo di .{1,40}? si tratta di` e `non è (solo|soltanto) .{1,40}? è (anche|piuttosto)` — fallisce nel 100% dei casi reali.

Esempi che fallirebbero la regex v1.0 ma SONO antitesi cliché:
- "il capo migliore non è quello che ci fa notare, ma quello che ci fa dimenticare di essere vestiti" (004)
- "Non è coincidenza, è convergenza" (004)
- "Non per una scelta culturale di chi legifera, ma per una pressione cumulativa" (005)
- "comprare meno, comprare bene non è una postura morale, è aritmetica" (007)
- "Non un manifesto promozionale: un omaggio" (006)

**Azione Rubric v1.1 — regex semantica estesa per §1.3**:
```regex
# Antitesi corta "non X, ma Y" / "non X, è Y"
\b[Nn]on (è|sono|fa|si tratta|porta|si celebra|c'è|riguarda) .{1,80}?,\s+(ma|è|porta|si rende|si tratta)\s+

# Antitesi con due punti "non è X: è Y"
\b[Nn]on (è|sono|si tratta) (solo|soltanto)?\s+.{1,80}?[:.]\s+È\b

# Anafora antitetica tripartita (nuovo, da 006)
(?:\b(?:non|né)\s+\w+(?:\s+\w+){0,4}?,\s+){2,}(?:\b(?:non|né)\s+\w+(?:\s+\w+){0,4}?)\.\s+[ÈE]\b
```

### P4 — Chiusura aforistica/morale meditativa
Frequenza: 7/7 (100%).
Pattern: l'ultimo paragrafo (o le ultime 2-3 frasi) chiude con formula sentenziale.
Esempi:
- 001: "Il modo in cui crediamo, in fondo, valga la pena pensarlo"
- 003: "Il lusso invisibile comincia da questa domanda"
- 004: "È la materia, lo era da sempre. Era solo bastato dirlo"
- 005: "La regola europea sta arrivando per i produttori. Conviene anticiparla nel proprio guardaroba"
- 006: "Non si celebra un brand. Si rende riconoscimento al paesaggio che lo ha permesso"
- 007: "il guardaroba che dura — e che invecchia bene — non è una nostalgia. È, di nuovo, una scelta razionale"

**Azione Rubric v1.1 — estensioni §1.4**:
```regex
\bin fondo,?\s+.{1,40}?\b(valga|merita|vale|si rivela)\b
\bforse (la|è|sembra) .{1,30}?(\b(lezione|verità|lettura|chiave)\b|\bpi[ùu]\s+\w+\b)
\b(era|è stato) solo bastato (dirlo|capirlo|notarlo|nominarlo)\b
\b[Èè] (di nuovo|davvero|finalmente) (una|un) .{1,30}? razionale\b
\bcomincia da (questa|questo) (domanda|gesto|capo)\b
\b(porta|reca) (in sé)? .{1,30}? (impronta|traccia|memoria) di
```

## Pattern strutturali a 80%+ (5-6 su 7)

### P5 — Apertura narrativo-letteraria invece di journalistica
Frequenza: 6/7 (86%) — manca solo in 003 ("Dal 19 luglio 2026 le grandi imprese europee...").
Pattern: la prima frase NON è il fatto + entità + numero, ma una scena/suspense/figura retorica.
Esempi:
- 001: "C'è una fattoria, tra le colline dei Victorian Pyrenees, dove ogni anno qualcuno conta i micron"
- 004: "Per sei giorni Milano ha smesso di parlare di oggetti per parlare di cosa li fa esistere"
- 005: "Immagina un mondo in cui ogni capo che viene prodotto deve trovare qualcuno che lo indossi"
- 006: "C'è un modo vecchio di dire 'Made in Italy' che suona come un timbro"
- 007: "C'è una parola che ritorna nelle aste di Sydney e Fremantle, in queste settimane"

Tutte queste **PASSANO §1.5** v1.0 perché contengono toponimi/nomi/numeri nei primi 25 parole — ma sono apertura magazine-cover, non Radar.

**Azione Rubric v1.1 — §1.8 nuovo "registro apertura"**:
Oltre al check di presenza entità §1.5, controllare il **tipo di apertura**. Trigger se la prima frase inizia con uno dei seguenti pattern:
```regex
^[Cc]'(?:è|era) (?:un|una|un') \w+ che\b
^Immagina (?:un|una|un') (?:mondo|epoca|futuro|capo)
^Per [a-z]+ \w+ [A-Z]\w+ (?:ha|è|si è) (?:smesso|tornato|chiuso)
^Quando (?:il|la|lo|i|le|gli) \w+ (?:incontra|si chiude|comincia|si apre)
```

### P6 — Triadi/quartine enfatiche
Frequenza: 6/7 (86%) — manca solo in 003.
Pattern: enumerazione triadica o quartinaria di sostantivi/aggettivi/frasi nominali in cadenza ritmica.
Esempi:
- 001: "il pastore, una pecora, un microclima, e ventinove anni"
- 002: (triadi enfatiche multiple in chiusura)
- 004: "Pietra, petalo, legno, spugna" (×2)
- 005: "Meno collezioni, più mirate. Meno taglie a copertura, meglio scelte. Meno stagionalità isteriche, più cicli lunghi"
- 006: "L'acqua è precedente al lanificio. Il lanificio è precedente al brand. Il brand è precedente al capo"
- 007: "di pascolo, di selezione, di tosatura, di lavaggio"

**Azione Rubric v1.1**: mantenere come SOFT_FAIL ma aggiungere sub-pattern:
- "triade di frasi nominali" (-5)
- "quartina con anafora" (-8)
- "triade in chiusura paragrafo concettuale" (-5)

## Pattern singoli da aggiungere (1-2 occorrenze)

- **Personificazione mercato/sistema**: "Il mercato ha preso parola" / "L'industria sta dicendo" (007) → -5
- **Ammicco al lettore consapevole**: "di nuovo", "finalmente", "come sapevamo" (007 + altri) → -3
- **Ambiguità temporale**: "(in queste settimane|in questi giorni|cinque giorni fa)" che evita la data → -3
- **Meta-spiegazione lessicale**: "La parola corretta è X: a volte letterale, più spesso metaforica" (005) → -3
- **Disclaimer retorico**: "Non è X: è Y" come secondo periodo dopo apertura magazine-cover ("Non è utopia: è il regolamento") (005) → -5

## Conclusioni per la Rubric v1.1

### Numeri-chiave da bilanciare
- **HARD_FAIL rate attuale stimato con v1.0 strict**: ~1/7 (solo 007 via regex letterale §1.2).
- **HARD_FAIL rate effettivo con convenzione CTA + score threshold**: 7/7 (100%).
- **Gap regex literal → semantic**: ~85% dei trigger sono semantici, non letterali. La rubric v1.0 è strutturalmente sotto-tarata.

### Soglie da rivedere
- **PASS ≥ 85**: troppo permissiva. Considerare ≥ 80 PASS → tener i Radar di confine come SOFT_FAIL editabile.
- **SOFT_FAIL 70-84**: regione di scrittura "salvabile con 3-5 edit".
- **HARD_FAIL < 70**: regione di scrittura "rigenerare da zero".

### Architettura proposta Rubric v1.1
1. **§1.6 nuovo**: `cta_assente` formale HARD_FAIL.
2. **§1.7 nuovo**: `lunghezza > 800` riclassifica Story.
3. **§1.3 esteso**: regex semantica antitesi (corta + due punti + anafora tripartita).
4. **§1.4 esteso**: 6 nuove regex chiusura morale.
5. **§1.8 nuovo**: registro apertura narrativo-letteraria.
6. **§1.2 esteso**: "Immagina un mondo in cui", "Non è X: è Y" come connettore.
7. **§2.x esteso**: lessico C2 con brand heritage globali (Loro Piana, Kvadrat, OMA, etc.).
8. **§3 esteso**: densità em-dash globale > 0.5/100w come penalità cumulativa.

### Calibrazione Rubric v1.1 — passo successivo
Una volta scritta v1.1, ri-applicarla ai 7 Radar e verificare:
- Tutti i 7 restino HARD_FAIL (la v1.1 non deve "addolcire").
- Lo score di confine (003 a 79, 007 a 61) sia ricalcolato correttamente.
- I trigger letterali catturino almeno 5/7 dei casi (vs 1/7 attuale).

Se 5/7 trigger letterali → v1.1 PASS. Se < 5/7 → v1.2 con ulteriore estensione regex.

## Anti-exemplar consolidati per il scanner

Lista degli anti-exemplar identificati per inserire nel prompt scanner come "esempi bocciati":

1. **Apertura magazine-cover** — esempio 005: "Immagina un mondo in cui ogni capo che viene prodotto deve trovare qualcuno che lo indossi. Non è utopia: è il regolamento europeo ESPR."
2. **Apertura meditativo-narrativa** — esempio 006: "C'è un modo vecchio di dire 'Made in Italy' che suona come un timbro."
3. **Antitesi cascata** — esempio 001: "Qui non si celebra il capo, ma la fibra. Non il designer, ma il pastore. Non la passerella, ma la tosatura."
4. **Quartina anaforica metafisica** — esempio 006: "L'acqua è precedente al lanificio. Il lanificio è precedente al brand. Il brand è precedente al capo."
5. **Quartina enfatica ripetuta** — esempio 004: "Pietra, petalo, legno, spugna. Origine, sensualità, funzione, reinvenzione."
6. **Chiusura aforistica meta-editoriale** — esempio 004: "È la materia, lo era da sempre. Era solo bastato dirlo."
7. **Personificazione del mercato** — esempio 007: "Il mercato ha smesso di essere un fondale: è entrato nella scena, e ha preso parola."

Da inserire in `merino-news-scanner/wom-radar-voice-config.md` come "blacklist few-shot anti-exemplar".
