---
title: WoM Radar — Voice Configuration (drop-in per merino-news-scanner Phase 4)
purpose: Blocco di prompt da inserire in SKILL.md merino-news-scanner Phase 4 quando la routing gate ha classificato la news come destinata a WoM Radar
status: v1.1 — 2026-05-12 (pomeriggio)
upstream: voice-baseline-wom-radar.md v0.3 (5 exemplar validati), rubric-v1.1.md (validator), findings-7-radar-pre-v1.1.md (anti-exemplar)
supersedes: wom-radar-voice-config.md v1.0 (mattino)
changelog_v1.1:
  - "EXT §3 blacklist HARD_FAIL — pattern v1.1 estesi: antitesi semantica, anafora tripartita, chiusure aforistiche, CTA assente, lunghezza > 800, apertura narrativa"
  - "NEW §3.7 — Pattern micro da loggare (personificazione mercato, ammicco lettore, ambiguità temporale, meta-spiegazione)"
  - "NEW §6 — Anti-exemplar consolidati: 7 esempi bocciati dal validator con motivazione e correzione"
  - "RENUM §6 → §7 (Output format), §7 → §8 (Integration routing gate)"
---

# WoM Radar — Voice Configuration

Questo file estende `merino-news-scanner` SKILL.md Phase 4 (Generate Editorial Brief) per il caso in cui la routing gate (Phase 3) ha emesso verdetto:
- Classificazione: LIFESTYLE
- Destinazione primaria: WoM
- Formato: Radar (news article 300-500 parole)

Il blocco va integrato in coda alla Phase 4 esistente, come *override stilistico* per i Radar. Non si applica a Field Note pillar, a Story 800+, né a MU Osservatorio.

---

## 1. Routing TOV per cluster bersaglio

Quando la news Radar è clusterizzata, applica obbligatoriamente il TOV del cluster bersaglio. Se la news colpisce due cluster, scegli quello primario (più convertibile sul Lead Magnet).

| Cluster bersaglio | TOV obbligatorio | Lessico chiave | Verbi chiave | Lead Magnet di destinazione |
|---|---|---|---|---|
| **C1 Business Professional** | chiaro, solido, autorevole | viaggi, calendario, ore di portamento, focus, performance | misurare, reggere, dimostrare, ottimizzare | Business Layering Guide (150g/190g) |
| **C2 Heritage Mature** | culturale, profondo, elegante | filiera, distretto, tradizione, pettinato, generazioni | tramandare, custodire, lavorare, ricondurre | La Guida Definitiva ai Tessuti Nobili |
| **C3 Conscious Premium** | didattico, fattuale, non ideologico | LCA, ciclo vita, biodegradabilità, costo per utilizzo | misurare, durare, attestare, certificare | Filiera Reda: 270 anni di responsabilità |
| **C4 Modern Minimalist** | high signal / low noise, sintetico | capsule, silhouette, caduta, palette, ratio | scegliere, sostituire, sottrarre, semplificare | Wardrobe Essentials — Minimalist Edition |
| **C5 Italian Authentic** | quotidiano, concreto, FAQ-style | lavatrice, stagione, città italiana, "sì davvero" | provare, lavare, indossare, usare | Guida all'uso quotidiano (150/190) |

---

## 2. Regole di voce COMUNI a tutti i Radar

Applicare sempre, indipendentemente dal cluster:

1. **Apertura**: deve contenere un fatto concreto (data, nome, numero, fonte) nelle prime 25 parole. Vietate aperture generiche, domande retoriche, frasi di scenario.
2. **Attribuzione**: ogni claim deve avere una fonte nominata. No "secondo alcuni studi", no "è risaputo che".
3. **Variance frase**: alternare frasi brevi e lunghe. Mai tre frasi lunghe consecutive.
4. **Em-dash**: massimo 1 per paragrafo.
5. **Triadi**: niente liste enfatiche "X, Y e Z" come climax retorico.
6. **Chiusura**: CTA al Lead Magnet del cluster bersaglio, mai morale.
7. **Lunghezza target**: 300-500 parole per Radar Field Note.
8. **CTA format**: `→ **Approfondisci**: [Lead Magnet name] — [riga di posizionamento]`

---

## 3. Blacklist anti-AI-tell — HARD FAIL (esteso v1.1)

Se uno qualsiasi di questi appare nel testo generato, il drafter deve riscrivere prima di emettere output. **La rubric v1.1 ha calibrato questa blacklist sui 7 Radar pre-validator: 7/7 HARD_FAIL via trigger letterale.**

### 3.1 Superlativi e parole-bandiera (v1.0)
- "rivoluzionario", "straordinario", "incredibile", "epocale", "iconico"
- "must-have", "deve avere", "ogni guardaroba", "intramontabile"

### 3.2 Connettori retorici AI (v1.0 + v1.1 NEW)
- v1.0: "non è un caso che", "non a caso", "in un'epoca in cui", "in un mondo dove/in cui", "nel cuore di"
- **v1.1 NEW**: "Immagina un mondo/un'epoca/un futuro in cui", "Non è utopia/fantascienza/magia: è"
- **v1.1 NEW**: "In queste settimane/giorni, X pronuncia/dice/sussurra/ritorna"

### 3.3 Costrutti antitetici cliché (v1.0 + v1.1 NEW)
- v1.0: "non si tratta solo di X, si tratta di Y"
- **v1.1 NEW — antitesi corta**: "Non X, ma Y" / "Non X, è Y" (in qualsiasi forma)
- **v1.1 NEW — antitesi con due punti**: "Non è X: è Y" (in qualsiasi forma)
- **v1.1 NEW — anafora antitetica tripartita**: "non è X, non è Y, non è Z. È W" (3+ occorrenze in cascata)
- **v1.1 NEW — quartina anaforica metafisica**: "X è precedente a Y. Y è precedente a Z. Z è precedente a W." (3+ frasi consecutive con stessa struttura)

**Regola cascata**: una singola antitesi (es. "Non è cosmetica: è strutturale") è SOFT_FAIL. **3+ antitesi nello stesso pezzo** → HARD_FAIL.

### 3.4 Chiusure morali/aforistiche (v1.0 + v1.1 NEW)
- v1.0: "una lezione che", "vale la pena ricordare che", "il segreto è", "in fondo + verbo"
- **v1.1 NEW**: "Forse la X più Y" (lezione, verità, lettura, chiave) — variante di "una lezione che"
- **v1.1 NEW**: "Era solo bastato dirlo/capirlo/notarlo/nominarlo"
- **v1.1 NEW**: "È di nuovo/davvero/finalmente una X razionale/necessaria/onesta"
- **v1.1 NEW**: "comincia/inizia/nasce da questa/quella domanda/gesto/capo/scelta"
- **v1.1 NEW**: "porta/reca in sé l'impronta/traccia/memoria/eco di"
- **v1.1 NEW**: "vale la pena + verbo cognitivo" (fissare, sottolineare, notare, ricordare, considerare, pensare, chiedersi)

### 3.5 Aperture problematiche
- v1.0: domanda retorica come prima frase
- v1.0: prime 25 parole senza data/nome proprio/numero/fonte
- **v1.1 NEW — apertura narrativo-letteraria** (anche se §1.5 PASSA via entità):
  - "C'è/c'era un X che Y"
  - "Immagina un mondo/futuro/capo in cui"
  - "Per X giorni/anni, Y ha smesso/tornato/chiuso"
  - "Quando il/la X incontra/si chiude/comincia"
  - "In/Dentro un mondo X in cui/dove/che"

### 3.6 Strutturali (NEW v1.1)
- **§1.6 — CTA Lead Magnet assente**: il pezzo NON contiene riferimento al Lead Magnet del cluster bersaglio. CTA comportamentali generiche ("aprire l'armadio", "guardare i propri capi") NON valgono come CTA Lead Magnet.
- **§1.7 — Lunghezza > 800 parole**: il pezzo eccede il target Radar (300-550 parole). Riclassificare come Story OPPURE tagliare.

## 3.7 Pattern micro da loggare (NEW v1.1)

Pattern AI-tell minori che, presi singolarmente, non sono hard-fail ma erodono la qualità del Radar. Se ne compaiono ≥3 in un pezzo, il pezzo entra in SOFT_FAIL anche con score altrimenti accettabile.

### 3.7.1 Personificazione mercato/sistema/industria
- "Il mercato ha preso parola / sta dicendo / sussurra / ammette"
- "L'industria ha smesso di / sta cominciando a / riconosce"
- "La filiera ha imparato / decide / parla"

### 3.7.2 Ammicco al lettore consapevole
- "di nuovo", "come sapevamo", "finalmente", "per chi vuole ascoltare"
- "chi conosce il distretto / chi ha imparato a / chi compra in modo consapevole"

### 3.7.3 Ambiguità temporale (evita data assoluta)
- "in queste settimane", "in questi giorni", "nelle ultime ore", "da qualche tempo"
- **Correzione**: sostituire con data assoluta o intervallo specifico ("dal 9 al 19 aprile", "tra febbraio e maggio 2026")

### 3.7.4 Meta-spiegazione lessicale
- "La parola corretta è X: a volte letterale, più spesso metaforica"
- "Il termine giusto sarebbe Y"
- "Chiamarlo così / in altro modo"
- **Correzione**: scegliere la parola e usarla, senza spiegarla.

### 3.7.5 Disclaimer retorico post-apertura
- Seconda frase "Non è X: è Y" subito dopo apertura magazine-cover
- Es. "Immagina un mondo in cui... Non è utopia: è il regolamento ESPR."
- **Correzione**: rimuovere il disclaimer + ancorare l'apertura al fatto.

---

## 4. Blacklist anti-AI-tell — SOFT FAIL (rivedere ma non rigenerare)

- Più di 1 em-dash per paragrafo
- **NEW v1.1 — densità em-dash globale > 0.5 per 100 parole** (sui 7 Radar pre-validator era 0.4–1.1)
- Triadi enfatiche "X, Y e Z" o quartine "X, Y, Z, W"
- Paragrafo senza alcuna entità nominata
- Paragrafo senza alcun numero o data
- UNA SOLA antitesi semantica (vedi §3.3): conta come SOFT, non HARD

---

## 5. Few-shot exemplar — uno per cluster

Inserire questi 5 esempi come few-shot nel prompt prima della generazione. Sono ancore di voice verificate (fonti reali) e devono essere riprodotte nel registro corrispondente.

### Exemplar C1 (Business Professional)

> **Il trend dei "12-hour micro-trip" nel business travel: cosa cambia per il guardaroba**
>
> Il Deloitte Corporate Travel Study 2025 identifica un cambiamento netto nei comportamenti del business travel: il 53% dei frequent corporate travelers — chi fa più di 10 viaggi all'anno — pianifica 3 o più trip al mese, in calo dal 63% del 2024. Il volume scende, ma cambia anche la natura del viaggio: cresce il "12-hour micro-trip", la visita lampo concepita per concentrare interazioni e ritorno nello stesso giorno.
>
> Per chi vive questo modello, il guardaroba ragiona in modo diverso. Una giornata da dodici ore tra aeroporto, ufficio cliente, pranzo e meeting di chiusura mette in cima ai criteri tre cose: capi che reggono senza pieghe visibili, che funzionano sotto giacca quanto da soli, che non chiedono manutenzione complessa.
>
> La T-shirt rientra in questo perimetro più di quanto si pensi. Una superfine 17 micron distribuisce il calore in modo che lo strato sotto giacca non diventi una camicia di forza dopo otto ore. Lo confermano i dati di termoregolazione attiva pubblicati da AgResearch nel 2024.
>
> Quello che è cambiato negli ultimi tre anni è che il dress code di molte realtà — finance, consulting, tech — ha allentato la cravatta senza allentare lo standard estetico. La T-shirt sotto il blazer è entrata nel kit. Resta da capire quale T-shirt regge il giorno-tipo da dodici ore senza essere sostituita.
>
> → **Approfondisci**: Business Layering Guide — quando 150g e quando 190g

### Exemplar C2 (Heritage Mature)

> **Il Piano Strategico CNA Federmoda 2026-2030 rimette la filiera artigiana al centro**
>
> CNA Federmoda ha pubblicato il Piano Strategico 2026-2030, concepito come piattaforma operativa del Libro Bianco Made in Italy 2030 del Ministero delle Imprese. Il documento mette al centro il ruolo della filiera artigiana come tutela della qualità, dell'innovazione e della coesione territoriale del sistema moda italiano.
>
> È un passaggio che vale più di quanto la cronaca lasci intendere. Negli ultimi dieci anni "artigianale" è diventato un aggettivo elastico, usato anche da brand che svolgono in Italia solo le rifiniture o l'etichettatura. Il distretto biellese, dove la lavorazione della lana fine ha 250 anni di pratica continuativa, è uno dei pochi luoghi in cui la filiera completa resta misurabile passaggio per passaggio: dal pettinato al filato, dal filato al tessuto, dal tessuto al capo.
>
> Reda, che fornisce parte del filato alla T-shirt Albeni, opera con questa profondità di filiera dal 1865. La differenza tra un capo che attraversa Biella in tutti i suoi passaggi e un capo che ci passa solo per il finissaggio non è cosmetica: si vede nel modo in cui la maglia tiene la forma dopo dodici lavaggi, e nel peso reale del cartellino "Made in Italy".
>
> Il Piano CNA è una dichiarazione di intenti, non un cambio di mercato immediato. Ma è la prima riga di un discorso che vale la pena seguire, perché ricondurre il significato di "artigianale" a una filiera misurabile, in questo settore, vuol dire ricondurre il valore al posto giusto.
>
> → **Approfondisci**: La Guida Definitiva ai Tessuti Nobili — cosa rende un filato nobile davvero

### Exemplar C3 (Conscious Premium)

> **Bando UE invenduto da luglio 2026: cosa cambia leggendo i numeri della Commissione**
>
> Dal 19 luglio 2026 le grandi aziende del tessile europeo non potranno più distruggere prodotti invenduti. La misura, parte del regolamento ESPR (Ecodesign for Sustainable Products Regulation), si applicherà alle medie imprese dal 2030. Da febbraio 2027 le aziende dovranno anche dichiarare per categoria merceologica la quota di prodotti destinati a riuso, riciclo, recupero o smaltimento.
>
> I numeri che la Commissione Europea cita motivano la durezza della norma: ogni anno in Europa il 4-9% del tessile invenduto viene distrutto prima ancora di essere indossato, generando circa 5,6 milioni di tonnellate di CO2 — quasi quanto le emissioni nette totali della Svezia nel 2021.
>
> Per chi compra in modo consapevole il cambiamento è leggibile in modo specifico. Il problema dei brand che producono troppo non sparisce: si trasferisce a monte, dove sarà più costoso pianificare male i volumi e meno conveniente proporre stagioni rapide a basso prezzo. La conseguenza prevedibile è un riavvicinamento tra prezzo di listino e costo reale del capo.
>
> In questo quadro le fibre naturali con ciclo lungo si trovano in posizione più solida di quelle sintetiche con ciclo breve. La lana fine merino è biodegradabile in meno di 90 giorni in ambiente marino: il dato è pubblicato da AgResearch ed è ripetibile in laboratorio. Non è una superiorità totale, è una differenza misurabile su un asse preciso.
>
> Per chi sceglie meno e meglio, l'ESPR non aggiunge nulla di sorprendente. Mette per legge un comportamento che alcuni consumatori già praticano.
>
> → **Approfondisci**: Filiera Reda, 270 anni di responsabilità — cosa misurare quando si parla di tracciabilità

### Exemplar C4 (Modern Minimalist)

> **State of Fashion 2026: l'industria rallenta. Il consumatore si stringe (ma seleziona)**
>
> Lo State of Fashion 2026 pubblicato da McKinsey e Business of Fashion descrive un'industria che entrerà nel nuovo anno con crescita a singola cifra bassa, sotto pressione da dazi, AI e priorità del consumatore in evoluzione. Il 46% dei dirigenti del settore intervistati prevede un peggioramento delle condizioni di mercato nel 2026, in netto aumento dal 39% dell'anno precedente.
>
> Quello che il report descrive lato consumatore è una traiettoria che alcuni guardaroba premium già seguono: meno acquisti, scelti meglio, allocati su categorie che durano. Il valore non è abbandonato — è cercato in modo più diretto, lontano dal claim aspirazionale.
>
> Per chi compra in questo modo le implicazioni sul tipo di T-shirt che entra nel guardaroba sono concrete. Bianco. Grigio chiaro. Blu profondo. Caduta pulita sul corpo, niente loghi, niente stampe. Costruzione cut & sewn invece che maglieria, perché tiene meglio la forma. Materia che regge cinque anni invece di cinque mesi.
>
> Quello che dal piano marketing sembra una nicchia, dai numeri McKinsey sembra una traiettoria. I brand che si stanno adeguando vendono catalogo ristretto a prezzo intero, non collezioni gonfie scontate.
>
> Una T-shirt buona ne sostituisce tre mediocri: McKinsey non lo scrive in questi termini, ma i suoi numeri lo lasciano leggere.
>
> → **Approfondisci**: Wardrobe Essentials — Minimalist Edition

### Exemplar C5 (Italian Authentic)

> **Merino in primavera: l'adozione cresce nell'activewear e nei capi da viaggio**
>
> Una nota di Fibre2Fashion di inizio 2026 osserva un trend tecnico interessante: l'adozione del merino sta accelerando nelle categorie activewear e travel clothing — categorie tipicamente associate alla domanda da stagione calda, non al freddo. Il merino conserva il 45,3% del mercato globale della lana nel 2025, in crescita rispetto agli anni precedenti, trainato dal segmento premium.
>
> Il dato contraddice la convinzione domestica più radicata: che la lana sia roba da inverno.
>
> La lana superfine, quella sotto i 18 micron, non scalda come la lana classica. Funziona da regolatore: assorbe l'umidità del corpo e la rilascia. Per questo i ciclisti professionisti la usano in primavera e in autunno, e qualche corridore amatoriale anche d'estate.
>
> A casa il caso tipico è la T-shirt sotto la camicia, o sotto il pullover leggero di mezza stagione. A 17 micron non pizzica, si lava in lavatrice (sì davvero), non ha bisogno di stiratura.
>
> Chi l'ha provata di solito non torna indietro per due ragioni pratiche: regge tre giorni di portamento senza accumulare odore, non si deforma né sbianca. Le T-shirt buone in lana fine arrivano ai cinque-sette anni di uso reale.
>
> Per chi compra italiano vale meno come novità e più come conferma: la maglia non è un esperimento, è un capo da tutti i giorni.
>
> → **Approfondisci**: Guida all'uso quotidiano — quale peso per la tua città

---

## 6. Anti-exemplar consolidati (NEW v1.1) — 7 pattern bocciati dal validator

I seguenti 7 anti-exemplar sono stati estratti dalla validazione di **tutti** i 7 Radar pre-validator (file `findings-7-radar-pre-v1.1.md`, file `calibration-v1.1-results.md`). Vanno inseriti nel prompt few-shot **dopo** i 5 positive exemplar, con etichetta "BOCCIATI — NON RIPRODURRE QUESTO STILE".

Per ogni anti-exemplar è indicato: (1) il testo bocciato, (2) il pattern AI-tell coinvolto, (3) la correzione attesa.

### 6.1 Anti-exemplar — Apertura magazine-cover "Immagina un mondo in cui"

> **BOCCIATO** (Radar 005, La fine dell'usa e getta)
>
> "Immagina un mondo in cui ogni capo che viene prodotto deve trovare qualcuno che lo indossi. Non è utopia: è il regolamento europeo ESPR, e entra in vigore tra meno di novanta giorni."

**Pattern**: §3.2 connettore retorico v1.1 NEW ("Immagina un mondo in cui") + §3.7.5 disclaimer retorico post-apertura ("Non è utopia: è").

**Correzione attesa**:
> "Dal 19 luglio 2026 le grandi imprese tessili europee non potranno più distruggere capi invenduti. Lo stabilisce il regolamento ESPR, adottato il 9 febbraio 2026 dalla Commissione Europea."

---

### 6.2 Anti-exemplar — Apertura narrativo-meditativa "C'è un modo vecchio di dire"

> **BOCCIATO** (Radar 006, L'anima dell'acqua Biella)
>
> "C'è un modo vecchio di dire 'Made in Italy' che suona come un timbro. E ce n'è uno nuovo — o forse antichissimo — che lo pronuncia come si pronuncia il nome di un luogo: piano, per rispetto."

**Pattern**: §3.5 apertura narrativo-letteraria ("C'è un X che Y") + em-dash come parentesi narrativa (×2 nella prima frase).

**Correzione attesa**:
> "Dal 11 al 19 aprile la Settimana del Made in Italy 2026 ha scelto come tema 'L'anima dell'acqua'. A Biella, distretto storico del lanificio italiano, il Lanificio Maurizio Sella ha ospitato la mostra 'La Sovrana dell'Acqua': un'installazione collettiva di tessuti donati dalle eccellenze del distretto."

---

### 6.3 Anti-exemplar — Antitesi cascata semantica

> **BOCCIATO** (Radar 001, 10.4 micron)
>
> "Qui non si celebra il capo, ma la fibra. Non il designer, ma il pastore. Non la passerella, ma la tosatura. Non il marchio in vista, ma l'etichetta nascosta."

**Pattern**: §3.3 antitesi cascata (4 occorrenze consecutive con anafora "Non X, ma Y"). HARD_FAIL via cascata anche se ciascuna antitesi singola sarebbe SOFT.

**Correzione attesa**: scegliere UNA tesi e affermarla in forma positiva.
> "Il valore qui non sta nella passerella ma nel pascolo: la qualità nasce a monte del marchio, e l'etichetta nascosta racconta più di un logo esposto."

(Una sola antitesi conservata; le altre 3 riformulate in affermative.)

---

### 6.4 Anti-exemplar — Quartina anaforica metafisica

> **BOCCIATO** (Radar 006, L'anima dell'acqua Biella)
>
> "L'acqua è precedente al lanificio. Il lanificio è precedente al brand. Il brand è precedente al capo. Tutto questo, insieme, è precedente al guardaroba di chi quel capo lo indosserà."

**Pattern**: §3.3 quartina anaforica metafisica (4 frasi consecutive con stessa struttura "X è precedente a Y" + anafora del soggetto della precedente).

**Correzione attesa**: ridurre a singola frase sintetica.
> "L'acqua dei torrenti biellesi precede tutto: il lanificio, il brand, il capo finito."

---

### 6.5 Anti-exemplar — Quartina enfatica ripetuta come slogan

> **BOCCIATO** (Radar 004, Salone della materia)
>
> "Pietra, petalo, legno, spugna. Origine, sensualità, funzione, reinvenzione. [...] Pietra, petalo, legno, spugna — origine, sensualità, funzione, reinvenzione — possono essere tradotti in domande precise davanti a ogni acquisto."

**Pattern**: quartina enfatica RIPETUTA due volte nel pezzo come slogan + frasi nominali in cadenza. Vietato anche dalle "Regole comuni" §2 punto 5 (triadi enfatiche).

**Correzione attesa**: enumerare una sola volta, in forma operativa.
> "La campagna del Salone ha articolato il tema in quattro materie simboliche: pietra (origine), petalo (sensualità), legno (funzione), spugna (reinvenzione)."

---

### 6.6 Anti-exemplar — Chiusura aforistica meta-editoriale

> **BOCCIATO** (Radar 004, Salone della materia)
>
> "Forse la lezione più semplice che il Salone 2026 ci ha lasciato è questa: il lusso non è ciò che si vede da lontano. È ciò che resta, dopo che si è smesso di guardare. È la materia, lo era da sempre. Era solo bastato dirlo."

**Pattern**: §3.4 chiusura morale (5 trigger concentrati in 30 parole: "Forse la lezione più", antitesi cascata, "Era solo bastato dirlo", tono universale-aforistico, meta-commento "lo era da sempre").

**Correzione attesa**: rimuovere la chiusura morale + sostituire con osservazione fattuale + CTA Lead Magnet.
> "A 1.900 espositori e 32 paesi rappresentati, il Salone 2026 ha dato spazio strutturale al tessile (Kvadrat, Aptitude, artigiani uzbeki). Per chi vuole vedere come la materia tessile italiana entra in questa lettura, leggi la nostra Guida Definitiva ai Tessuti Nobili."

---

### 6.7 Anti-exemplar — Personificazione del mercato + ammicco al lettore

> **BOCCIATO** (Radar 007, Guardaroba che dura)
>
> "Il mercato ha smesso di essere un fondale: è entrato nella scena, e ha preso parola. Sta dicendo, per chi vuole ascoltare, che il guardaroba che dura — e che invecchia bene — non è una nostalgia. È, di nuovo, una scelta razionale."

**Pattern**: §3.7.1 personificazione del mercato ("ha preso parola", "Sta dicendo") + §3.7.2 ammicco al lettore consapevole ("per chi vuole ascoltare", "di nuovo") + §3.3 antitesi due punti ("non è X. È Y") + em-dash come parentesi narrativa.

**Correzione attesa**: rimuovere la personificazione + sostituire l'antitesi con affermazione + ancorare al numero.
> "A +40% in 12 mesi, il prezzo della lana australiana riallinea aritmeticamente il valore di un guardaroba che dura. Cinque capi merino indossati dieci stagioni costano meno (in cost-per-wear) di quindici capi sintetici. Per capire come una filiera certificata costruisce questa durata, leggi Filiera Reda: 270 anni di responsabilità."

---

### Sintesi anti-exemplar — 4 regole derivate

Distillati dai 7 anti-exemplar sopra, ecco i 4 principi-base che il drafter deve interiorizzare:

1. **L'apertura ancora al fatto, non alla scena.** Mai aprire con "C'è un X che", "Immagina", "Quando il X incontra", "Per N giorni Y ha". Sempre aprire con data + soggetto + verbo + numero.
2. **L'antitesi è UNA, non quattro.** Una contrapposizione punta una tesi; quattro la sviluppano in slogan. Se serve dire "non X, ma Y" più di una volta nel pezzo, riformulare almeno tre in forma affermativa.
3. **La chiusura è una CTA, non una lezione.** Ultima frase = rimando esplicito al Lead Magnet del cluster bersaglio. Mai "Forse la lezione più", "Era solo bastato", "comincia da questa domanda".
4. **Il mercato non parla, le persone parlano.** Vietate personificazioni di soggetti astratti ("il mercato dice", "l'industria sussurra"). Il soggetto narrante è il giornalista, le fonti sono enti concreti (McKinsey, Commissione UE, AgResearch).

---

## 7. Output format per Radar

Quando emetti un Radar in Phase 4, segui questo formato:

```yaml
radar_output:
  cluster_bersaglio: [C1|C2|C3|C4|C5]
  tov_applicato: [chiaro/solido/autorevole | culturale/profondo/elegante | didattico/fattuale | high signal low noise | quotidiano/FAQ]
  headline: "..."
  body: |
    Paragrafo 1 (apertura con fatto + fonte)
    Paragrafo 2 (sviluppo)
    Paragrafo 3 (dato tecnico/contestuale)
    Paragrafo 4 (osservazione finale)
  cta_lead_magnet: "[Lead Magnet name] — [tagline]"
  word_count: [intero, target 300-500]
  fonti_citate: [array di URL]
  pre_validator_self_check_v1_1:
    - blacklist_v11_hard_fail_clear: true   # §3.1-§3.6 estesi
    - opening_anchored_to_fact_NOT_scene: true   # §3.5 apertura narrativa esclusa
    - antitesi_max_1_in_pezzo: true   # §3.3 cascata vietata
    - chiusura_e_CTA_NOT_lezione: true   # §3.4 chiusura morale esclusa
    - cluster_tov_recognizable: true
    - cta_present_and_correct_lead_magnet: true   # §3.6 CTA assente vietata
    - word_count_target_300_550: true   # §3.6 lunghezza >800 vietata
    - no_personificazione_mercato: true   # §3.7.1
    - no_disclaimer_post_apertura: true   # §3.7.5
```

Prima di emettere, esegui mental self-check sulle 9 voci `pre_validator_self_check_v1_1`. Se anche solo una è `false`, riscrivi.

**Self-check post-output**: scansionare il pezzo prodotto contro i 7 anti-exemplar §6 e contro i 4 principi-base derivati. Se anche un solo pattern matcha, riscrivi senza emettere.

---

## 8. Integration con il routing gate (Phase 3)

Questa voice config si attiva **solo se** il routing gate emette:
- `Classificazione: LIFESTYLE` OR (`Classificazione: CROSSOVER` AND `Formato WoM: Radar`)
- `Destinazione primaria: WoM` OR `Destinazione secondaria: WoM Radar`

In tutti gli altri casi (TECHNICAL → MU Osservatorio, LIFESTYLE → WoM Field Note evergreen non-news), si applica una voice config diversa (TBD per Osservatorio, esistente per Field Note).
