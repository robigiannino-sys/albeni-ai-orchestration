---
title: WoM Radar Validator — Rubric v1.1
purpose: Tabelle dettagliate, pattern semantici estesi, fingerprint per cluster, formule di scoring
status: v1.1 — 2026-05-12
upstream: voice-baseline-wom-radar.md v0.3, wom-radar-voice-config.md v1.0, findings-7-radar-pre-v1.1.md
supersedes: rubric.md v1.0 (mantenuta come storico per regression testing)
changelog_v1.1:
  - "NEW §1.6 — cta_assente come HARD_FAIL formale (era solo in esempio §4.3)"
  - "NEW §1.7 — lunghezza > 800 parole come HARD_FAIL con riclassifica Story"
  - "NEW §1.8 — registro apertura narrativo-letteraria come HARD_FAIL"
  - "EXT §1.2 — varianti 'Immagina un mondo in cui', 'Non è X: è Y', 'Non è utopia/fantascienza'"
  - "EXT §1.3 — regex semantica antitesi (corta, due punti, anafora tripartita, anafora metafisica)"
  - "EXT §1.4 — 6 nuove regex di chiusura morale/aforistica"
  - "EXT §2.2 — lessico C2 con brand heritage globali e lavorazioni tessili internazionali"
  - "EXT §3 — densità em-dash globale > 0.5/100w come penalità cumulativa"
  - "NEW §6 — pattern micro da loggare (personificazione mercato, ammicco lettore, ambiguità temporale, meta-spiegazione)"
---

# WoM Radar Validator — Rubric v1.1 (dettagliata)

Questo file estende e supera la rubric v1.0, basandosi sui findings dei 7 Radar pre-validator (file `findings-7-radar-pre-v1.1.md`). La v1.0 catturava 1/7 trigger letterale (14%); la v1.1 punta a ≥5/7 (71%).

---

## 1. HARD-FAIL pattern list (regex/string match)

### 1.1 Superlativi e parole-bandiera (invariato da v1.0)

```regex
\b(rivoluzionari[oae]|straordinari[oae]|incredibil[ei]|epocali?|iconic[oae])\b
\bmust[\s-]have\b
\bintramontabil[ei]\b
\b(deve|devono) avere\b
\bogni guardarob[ao]\b
```

### 1.2 Connettori retorici AI (ESTESO v1.1)

```regex
# v1.0 originali
\bnon è un caso che\b
\bnon a caso\b
\bin un'epoca in cui\b
\bin un mondo (in cui|dove)\b
\bnel cuore di\b

# v1.1 nuovi (da test case 005)
\bImmagina (un mondo|un'epoca|un futuro|un guardaroba) in cui\b
\b[Nn]on è (utopia|fantascienza|magia|fantasia)[:.]\s*(è|è solo|è soltanto)\b
\b(C'era una volta|Per un momento|Un tempo) .{1,40}? (oggi|adesso|ora|adesso[,.])\b
\bin queste settimane,?\s+\w+\s+(pronuncia|dice|si chiede|sussurra|ritorna)\b
```

### 1.3 Costrutti antitetici cliché (ESTESO v1.1)

La v1.0 catturava solo "non si tratta solo X si tratta Y" e "non è solo X è anche/piuttosto Y" — il 100% dei Radar pre-validator usa forme alternative. La v1.1 generalizza:

```regex
# v1.0 originali (mantenuti)
non si tratta solo di .{1,40}? si tratta di
non è (solo|soltanto) .{1,40}? è (anche|piuttosto)

# v1.1 — antitesi corta "non X, ma/è Y"
\b[Nn]on (è|sono|fa|si tratta|porta|si celebra|c'è|riguarda)\s+.{1,80}?,\s+(ma|è|porta|si rende|si tratta)\s+

# v1.1 — antitesi con due punti "non è X: è Y" (anche maiuscola)
\b[Nn]on (è|sono|si tratta)( solo| soltanto)?\s+.{1,80}?[:.]\s*[ÈE]\b

# v1.1 — anafora antitetica tripartita "non è X, non è Y, non è Z. È W"
(?:\b(?:non|né)\s+\w+(?:\s+\w+){0,4}?,\s+){2,}\b(?:non|né)\s+\w+(?:\s+\w+){0,4}?\.\s+[ÈE]\b

# v1.1 — quartina anaforica metafisica "X è precedente a Y. Y è precedente a Z..."
(?:\b(?:Il|La|Lo|Le|L'|Gli|I)\s+\w+\s+(?:è|sono)\s+\w+\s+(?:a|al|alla|alle|allo|ai|agli|alle)\s+\w+\.\s+){3,}
```

**Soglia trigger**: anche UNA singola occorrenza di "antitesi corta" o "antitesi con due punti" è SOFT_FAIL (-8 cad.). **TRE o più antitesi nel pezzo → HARD_FAIL** (pattern cascata).

### 1.4 Chiusure morali (ESTESO v1.1)

```regex
# v1.0 originali
\buna lezione (che|da)\b
\bvale la pena ricordare (che|quanto)\b
\bil segreto (è|sta in)\b
\bin fondo,? .{1,30}?$
\balla fine,? .{1,30}? è quel che conta\b

# v1.1 — varianti "in fondo + valore"
\bin fondo,?\s+.{1,40}?\b(valga|merita|vale|si rivela)\b

# v1.1 — "forse la X più Y" (vista in 004, 006)
\b[Ff]orse (la|è|sembra)\s+.{1,30}?(\b(lezione|verità|lettura|chiave|cosa)\b|\bpi[ùu]\s+\w+\b)

# v1.1 — chiusura tautologica "Era solo bastato dirlo"
\b(era|è stato) solo bastato (dirlo|capirlo|notarlo|nominarlo|guardarlo|chiamarlo)\b

# v1.1 — chiusura "È, di nuovo/davvero/finalmente, una X razionale"
\b[Èè] (di nuovo|davvero|finalmente|semplicemente)( ,)? una?\s+\w+\s+(razionale|necessari[ao]|inevitabil[ei]|onest[ao])\b

# v1.1 — formula identitaria "comincia da [pronome] [sost]"
\b(comincia|inizia|nasce) da (questa|questo|quella|quello)\s+(domanda|gesto|capo|silenzio|scelta|tessuto)\b

# v1.1 — "porta in sé l'impronta di"
\b(porta|reca|conserva) (in sé)?\s*.{1,30}?\s+(impronta|traccia|memoria|silenzio|eco) di\b

# v1.1 — "vale la pena" qualsiasi forma con verbo cognitivo
\bvale la pena\s+(fissare|sottolineare|notare|ricordare|considerare|pensare|chiedersi)\b
```

### 1.5 Aperture problematiche (invariato letterale + integrato da §1.8)

- Prima frase termina con "?" → HARD_FAIL
- Prime 25 parole non contengono NESSUNO dei seguenti:
  - Una data esplicita
  - Un nome proprio
  - Un numero o percentuale
  - Una fonte nominata
  → HARD_FAIL

**Integrazione v1.1**: anche se §1.5 PASSA, verificare §1.8 (registro apertura). Una prima frase può contenere toponimo/numero ma essere registro magazine-cover.

### 1.6 NEW v1.1 — CTA Lead Magnet assente

```yaml
check: cta_lead_magnet_assente
trigger:
  Nessun paragrafo del testo contiene un riferimento esplicito al Lead Magnet
  del cluster bersaglio (dichiarato o inferito). Lead Magnet attesi:
    - C1 → "Business Layering Guide"
    - C2 → "La Guida Definitiva ai Tessuti Nobili"
    - C3 → "Filiera Reda" / "Tracciabilità filiera lana"
    - C4 → "Wardrobe Essentials — Minimalist Edition"
    - C5 → "Guida all'uso quotidiano (150/190)"
  Sono accettate varianti morfologiche e CTA implicite chiare ("Per approfondire
  X, leggi la nostra guida Y"). NON sono accettate CTA comportamentali
  generiche ("aprire l'armadio", "guardare i propri capi", "pensare in capsule").
verdict: HARD_FAIL
motivazione_standard: |
  Lead Magnet del cluster bersaglio non identificato in alcun paragrafo
  dell'articolo. Pattern strutturale rilevato nel 100% dei Radar
  pre-validator (7/7). Conferma necessità di CTA cluster-specifica come
  trigger formale.
```

### 1.7 NEW v1.1 — Lunghezza > 800 parole

```yaml
check: lunghezza_riclassifica_story
trigger:
  word_count > 800
verdict: HARD_FAIL_RECLASSIFY
motivazione_standard: |
  Il pezzo supera il target Radar (300-550 parole, soft 550-800). > 800
  parole è di pertinenza WoM Story, non Radar. La routing è errata.
  Riclassificare come Story OPPURE tagliare a 400-500 parole.
azione_richiesta:
  - "RECLASSIFY: pubblicare come WoM Story (richiede voice baseline Story diverso)"
  - "TAGLIARE: ridurre a 400-500 parole rimuovendo paragrafi laterali, mantenendo solo l'evento + i numeri + l'analisi + CTA"
```

### 1.8 NEW v1.1 — Registro apertura narrativo-letteraria

Anche se §1.5 PASSA (entità presenti nei primi 25 parole), la prima frase può essere registro magazine-cover invece di journalistico. Controllare:

```regex
# Apertura "C'è/c'era una/un X che Y" — narrativa
^[Cc]'(?:è|era) (?:un|una|un')\s+\w+(?:\s+\w+){0,3}\s+che\b

# Apertura "Immagina un mondo/futuro/capo in cui"
^Immagina\s+(?:un|una|un')\s+(?:mondo|epoca|futuro|capo|guardaroba|tessuto)

# Apertura "Per X giorni/anni/settimane, Y ha smesso/cominciato"
^Per\s+\w+\s+\w+,?\s+[A-Z]\w+\s+(?:ha|è|si è)\s+(?:smesso|tornato|chiuso|aperto|cominciato|cambiato)

# Apertura "Quando il/la X incontra/si chiude/comincia"
^Quando\s+(?:il|la|lo|i|le|gli|un|una)\s+\w+\s+(?:incontra|si chiude|comincia|si apre|ha smesso|prende)

# Apertura "In/Dentro un mondo X..."
^(?:In|Dentro|Sopra|Sotto)\s+(?:un|una|un')\s+\w+\s+(?:in cui|dove|che)
```

**Verdetto**: se la prima frase matcha uno di questi pattern E §1.5 PASSA (apertura formalmente valida ma registro letterario), → **HARD_FAIL**.
**Eccezione**: se la prima frase matcha §1.8 MA contiene una data assoluta (es. "Il 19 luglio 2026, Milano ha smesso..."), declassare a SOFT_FAIL -10.

---

## 2. Cluster fingerprint — i 5 profili

### 2.1 C1 — Business Professional (invariato da v1.0)

[Lessico, registro, CTA, lessico non atteso — invariati]

### 2.2 C2 — Heritage Mature (ESTESO v1.1)

**Lessico cluster atteso v1.1** (≥ 3 termini nel testo):

*v1.0 strict (italiano-specifico)*:
- filiera, distretto, Biella, biellese
- tradizione, generazioni, pratica continuativa, eredità
- pettinato, cardato, filato, tessitura
- Reda, Cerruti, Vitale Barberis Canonico, lanificio
- Made in Italy, Camera della Moda, Confartigianato, CNA
- nobile, raffinato, custodire, tramandare

*v1.1 estensione — brand heritage globali*:
- Loro Piana, Brunello Cucinelli, Caccioppoli, Ermenegildo Zegna
- Kvadrat, Aptitude Objects, Margiela (per heritage design tessile)
- Lanificio + nome specifico (es. "Lanificio Maurizio Sella", "Lanificio Ermenegildo Zegna")

*v1.1 estensione — lavorazioni tessili internazionali*:
- vello, tosatura, pastore, fattoria, micron, finezza
- feltro, telaio, tessitore, lavorazione manuale, artigiano
- pettinatura, cardatura, filatura, finissaggio
- mostra, fiera, edizione (per eventi heritage)
- Record Bale Award, The Gift of Kings, Pitti Filati, Salone del Mobile

**Conta lessico v1.1**: serve match di ≥3 termini totali tra v1.0 strict + v1.1 estensione. Privilegiare comunque i v1.0 strict (italiano-specifico) per cluster C2 ad alta intensità.

**Registro atteso**: invariato (frasi articolate, subordinate, lessico colto, ritmo lento).

**Lead Magnet CTA atteso**: "La Guida Definitiva ai Tessuti Nobili" + varianti accettate.

**Lessico NON atteso (penalità)**: invariato.

### 2.3 C3 — Conscious Premium (invariato da v1.0)

### 2.4 C4 — Modern Minimalist (invariato da v1.0)

### 2.5 C5 — Italian Authentic (invariato da v1.0)

---

## 3. Formula di scoring (ESTESA v1.1)

```
score_iniziale = 100

per ogni hard_fail_trigger (§1.1, §1.2, §1.3 cascata, §1.4, §1.5, §1.6, §1.7, §1.8) trovato:
    return HARD_FAIL (score non viene calcolato)

per ogni soft_fail_penalty:
    score -= penalty

per ogni occorrenza in:
    em_dash_eccesso (>1 per paragrafo): -5 cad.
    triade_enfatica: -5 cad.
    quartina_enfatica: -8 cad.
    paragrafo_senza_entita: -8 cad.
    paragrafo_senza_numeri: -8 cad.
    aggettivo_superlativo_soft: -3 cad.
    cadenza_uniforme: -5
    antitesi_singola (§1.3 v1.1, max 2 occorrenze): -8 cad.
        # alla 3a occorrenza scatta HARD_FAIL cascata

# v1.1 — Densità em-dash globale
densita_em_dash_globale (NEW v1.1):
    em_dash_totali / (word_count / 100)
    se densità > 0.5 e ≤ 0.8: -8
    se densità > 0.8 e ≤ 1.0: -12
    se densità > 1.0: -15

penalità_lunghezza:
    se word_count < 250: -10
    se word_count > 800: HARD_FAIL §1.7
    se 550 < word_count ≤ 800: -10  # zona Story-creep
    se 250 ≤ word_count ≤ 299: -5
    se 501 ≤ word_count ≤ 550: -5

penalità_cluster_fingerprint:
    se lessico_cluster_match < 3 (anche con estensione v1.1): -15
    se registro_cluster_fail: -10
    se cta_lead_magnet_assente: HARD_FAIL §1.6
    se cta_lead_magnet_wrong_cluster: HARD_FAIL

penalità_pattern_micro (v1.1 §6):
    personificazione_mercato_sistema: -5
    ammicco_lettore_consapevole: -3
    ambiguita_temporale_evita_data: -3
    meta_spiegazione_lessicale: -3
    disclaimer_retorico_post_apertura: -5

VERDETTO:
    se hard_fail_trigger: HARD_FAIL
    se score ≥ 80: PASS  # v1.1 abbassata da 85 a 80 per recovery zone
    se 65 ≤ score < 80: SOFT_FAIL  # v1.1 range esteso 65-79
    se score < 65: HARD_FAIL  # v1.1 abbassata da 70 a 65
```

**Razionale soglie v1.1**: la distribuzione score dei 7 Radar pre-validator era 0–79 (mediana 59). Una soglia PASS ≥ 85 era irraggiungibile con i pattern reali. Abbassando a 80 PASS / 65 HARD_FAIL si crea una **zona SOFT_FAIL editabile** più ampia (65-79) che consente recovery con 3-5 edit invece di rigenerazione.

---

## 4. Esempi pratici di output (invariati da v1.0 con esempi aggiuntivi)

[I 3 esempi PASS / SOFT_FAIL / HARD_FAIL di v1.0 restano validi. Aggiungere il caso "HARD_FAIL via §1.6 CTA assente singolo trigger" come quarto esempio — vedi test case 003.]

---

## 5. Lista pattern AI-tell secondari da monitorare (estesa v1.1)

Pattern che non sono hard-fail ma da loggare:

*v1.0 originali*:
- "in qualche modo", "in un certo senso" — riempitivi
- "vale la pena considerare" — preambolo ridondante
- "ciò che è interessante", "quello che colpisce" — meta-commento editoriale
- "non sorprende che", "come prevedibile" — riempitivo
- "in altre parole", "tradotto" (oltre la prima occorrenza) — ridondanza
- "una traiettoria che", "un cambiamento che" — riempitivo astratto
- Sequenze di tre virgole in una frase singola — sovraccarico

*v1.1 aggiunte (sub-pattern da loggare per evoluzione v1.2)*:
- "il dettaglio che [verbo cognitivo]" come connettore introduttivo
- Anaphora retorica ("Non c'era... Non c'erano... Non c'era") con < 3 occorrenze
- "(in queste settimane|in questi giorni|nelle ultime ore)" che evita la data assoluta
- Personificazione astratta del soggetto ("Il mercato ha preso parola", "L'industria ha smesso di")
- Ammicco al lettore ("di nuovo", "come sapevamo", "finalmente", "per chi vuole ascoltare")
- Meta-spiegazione del proprio lessico ("La parola corretta è X: a volte letterale, più spesso metaforica")
- Disclaimer retorico immediato post-apertura ("Non è X: è Y" come secondo periodo)
- Verbo cognitivo seguito da formula identitaria brand ("sa cosa ha addosso", "ha imparato a")

---

## 6. NEW v1.1 — Pattern micro da loggare con penalità formali

I sub-pattern raccolti durante la validazione dei 7 Radar entrano nello scoring soft con penalità definite:

### 6.1 Personificazione mercato/sistema/industria
```regex
\b(Il mercato|L'industria|La filiera|Il sistema|La moda) (ha|è) (preso parola|smesso di|tornato a|cominciato a|imparato a|deciso di)\b
\b(Il mercato|L'industria) (sta dicendo|dice|sussurra|ammette|riconosce)\b
```
Penalty: -5 cad.

### 6.2 Ammicco al lettore consapevole
```regex
\b(di nuovo|come sapevamo|finalmente|per chi vuole ascoltare|chi conosce il distretto|chi ha imparato a)\b
```
Penalty: -3 cad. (max -9 cumulativo).

### 6.3 Ambiguità temporale (evita data assoluta)
```regex
\b(in queste settimane|in questi giorni|nelle ultime ore|da qualche tempo|negli ultimi mesi)\b
# Sostituire con: data assoluta o intervallo specifico ("dal 9 al 19 aprile")
```
Penalty: -3 cad. SE non c'è anche una data assoluta nello stesso paragrafo.

### 6.4 Meta-spiegazione lessicale
```regex
\bLa parola corretta è\s+\w+[:.]\s*(a volte|più spesso|sempre|talvolta)\b
\bIl termine giusto sarebbe\b
\b[Cc]hiamarl[oa] (così|in questo modo|in altro modo)\b
```
Penalty: -3 cad.

### 6.5 Disclaimer retorico post-apertura
```regex
# Seconda frase del pezzo che è "Non è X: è Y" o "Non è una Y, è Z"
^.{30,200}?\.\s*[Nn]on è (utopia|fantascienza|magia|stile|tendenza|moratoria|opinione|coincidenza)[:.]\s*(è|è solo|è soltanto)\b
```
Penalty: -5 (solo se in posizione "seconda frase").

---

## 7. Note di calibrazione (aggiornate v1.1)

- I valori delle penalità (3, 5, 8, 10, 15) sono iniziali — da tarare su 20+ Radar nei prossimi 4-6 mesi.
- Le soglie v1.1 (80 PASS, 65 HARD_FAIL) sono state abbassate dalla v1.0 (85 PASS, 70 HARD_FAIL) sulla base della distribuzione effettiva dei 7 Radar pre-validator (mediana 59, range 0-79).
- Densità em-dash globale è un soft metric — la regola "non più di 1 per paragrafo" resta primaria.
- I pattern §1.3 v1.1 "antitesi semantica" sono volontariamente broad: il rischio è il falso positivo (un Radar journalistico legittimo che dica "non è X, è Y" una volta). Per questo motivo la soglia HARD_FAIL scatta solo a 3+ occorrenze cascata, non alla prima.
- Il pattern §1.8 "registro apertura narrativo-letteraria" è il più sperimentale: monitorare nei primi 10-20 Radar v1.1 quanti falsi positivi genera.

---

## 8. Compatibilità con voice config scanner

La rubric v1.1 è compatibile retroattivamente con `wom-radar-voice-config.md` v1.0:
- I 5 cluster (C1-C5) sono invariati.
- I 5 Lead Magnet target sono invariati.
- Gli exemplar di cluster sono invariati.

Per attivare il sistema "creator-side" anti-AI-tell, il voice config v1.1 (separato) dovrà aggiungere:
- Lista 7 anti-exemplar consolidati dai test case (vedi findings).
- Few-shot blacklist con i pattern §1.2 v1.1 estesi.
- Routine di "auto-validation pre-output" che applica almeno i trigger HARD_FAIL §1.1, §1.2, §1.6, §1.7, §1.8 prima di emettere il Radar.

Vedi il file `wom-radar-voice-config-v1.1.md` (TODO separato) per i dettagli.
