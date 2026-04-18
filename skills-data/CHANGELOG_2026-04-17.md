# Albeni 1905 — AI Stack Skills Alignment Changelog

**Data deploy**: 2026-04-17
**Fonte del cambiamento**: `Albeni1905_KW_Cluster_Classification_2026-04-16.xlsx`
**Perché**: La KW Cluster Classification V1 ha rivelato 5 (non 6) cluster comportamentali, un mix BOFU reale 44/34/22 (vs dichiarato 50/22/28), e ha riformulato il piano C5 da MOFU puro a BOFU-first 78/22 per superare il blocco della lista trigger RhbEE3 (0 profili).

---

## P1 — Critical fixes

### albeni-mt-orchestrator/SKILL.md
- **Riga 116 (Batch Planning — Priority 2)**: mappatura cluster value corretta.
  - PRIMA: `C6 Technical > C2 Heritage > C5 Italian > C4 Minimalist > C1 Business > C3 Conscious` (mappatura shuffled, incoerente con definizioni canoniche)
  - DOPO: `C2 Business Professional > C1 Heritage Mature > C3 Conscious Premium > C5 Modern Minimalist > C4 Italian Authentic` (allineata a KW Cluster Classification V1 + mix reale 44/34/22)
- **Aggiunta Priority 5**: regola di attivazione C5 BOFU-first. Fintanto che RhbEE3 ha < 50 profili, batch C5 limitato a ≤2 pagine/settimana, paid spend 100% su BOFU LP prodotto.

### albeni-mt-translator/SKILL.md
- **Step "Identify the cluster"**: riferimento a "C1-C6" sostituito con "C1-C5" + definizioni esplicite dei 5 cluster + istruzione su bucket GENERIC-FUNCTIONAL / GENERIC-BRAND per KW senza signal esplicito.

### albeni-seo-agent/SKILL.md
- **Sezione "Your Role"**: il blocco "6 behavioral clusters + Semantic Defense" sostituito con la nuova tassonomia C1–C5 + 2 bucket generici (FUNCTIONAL 46 KW/117.490 vol, BRAND 28 KW/115.940 vol), priorità C4>C2>C3>C5>C1, nota che il precedente C6 Semantic Defense è stato assorbito in GENERIC-FUNCTIONAL.
- **Translation Brief Format**: cluster label aggiornata da `C1-C6 or Semantic Defense` a `C1-C5 or GENERIC-FUNCTIONAL / GENERIC-BRAND`.

---

## P2 — Alto (economics update)

### albeni-seo-agent/SKILL.md — sezioni nuove
1. **"BOFU Mix Reale — 44/34/22 (Aggiornamento 2026-04-16)"**
   - Nuovo mix C2 44% / C1 34% / C3 22% (vs dichiarato 50/22/28)
   - CR medio ponderato 2,45% (vs 2,8% uniforme)
   - Impatto modello v3: Conv 1.234→1.080, Revenue €160K→€141K, CPA €24,31→€27,78
   - Azione correttiva: ribilanciare ADV su C1 (luxury/premium head-terms CPC €1–€2,39)
2. **"PIANO C5 BOFU-first — 78/22 (Aggiornamento 2026-04-16)"**
   - Contesto: Welcome Flow XEDD2q LIVE dal 2026-04-05 ma RhbEE3 = 0 profili
   - Confronto 4 scenari a parità di budget €4.500/18M: A MOFU puro (ROAS 0,1×) → C BOFU-first 78/22 (ROAS 1,1–1,3× conservative) → D optimistic (ROAS 1,4–1,6×)
   - Regola operativa: batch C5 ≤2/settimana finché RhbEE3 < 50 profili; 100% paid su BOFU LP prodotto; 22% retargeting si attiva dopo ≥500 clic cold
3. **"Critical Constraints"** — aggiunti 3 nuovi vincoli (mix 44/34/22, C5 flow bloccato, KW universe 150 KW/278.640 vol con 84% nei bucket generici)

### semrush-specialist/SKILL.md
1. **Cluster Mapping (sezione 2 — Keyword Research)**: aggiornata a C1–C5 + 2 bucket generici, con priorità C4>C2>C3>C5>C1 e nota sull'assorbimento del precedente C6.
2. **ROI Analysis (sezione 4 — Monitoraggio e Reporting)**: aggiunti benchmark post-audit 2026-04-16 — Organic CR 1,5%, Paid CR 5,0%, **BOFU CR ponderato 2,45% sul mix 44/34/22**, multiplier 2,0×, AOV €130. Nota esplicita su modello BOFU-only: Revenue €141K, CPA €27,78 > target €15 → flag al SEO agent.
3. **keyword-matrix.csv description**: aggiornata da "55 keywords, 5 markets, 6 clusters" → "150 KW validate × 5 mercati × 5 cluster + 2 bucket generici, 278.640 vol/mese". Indicato file sorgente.

---

## P3 — Medio (dataset deploy)

### keyword-matrix.csv
- Rigenerata da `MASTER CLASSIFIED` sheet del file 2026-04-16.
- **150 righe KW** (vs 55 precedenti).
- Colonne invariate per retrocompatibilità: `Keyword,Volume US,Volume UK,Volume DE,Volume IT,Volume FR,Difficulty,Intent,Cluster,Dominio Assegnato,Funnel Stage,Priorità,Rischio Cannibalizzazione,Note,Source,Data Aggiornamento`.
- **Domain routing**: C1/C4/C5 → WoM; C2 → Albeni1905; C3 → MU; GENERIC-FUNCTIONAL → PMS; GENERIC-BRAND → Albeni1905.
- **Funnel assignment**: C1/C2/C3 → BOFU; C4 → MOFU; C5 → TOFU; GENERIC (vol≥500) → BOFU, altrimenti MOFU.
- **Priority**: P1 se vol_tot ≥ 5K; P2 se ≥ 500; P3 altrimenti.
- **Note field**: contiene rule + confidence + CPC_max per ogni KW.
- Backup precedente: `keyword-matrix.csv.bak-2026-04-16` in entrambe le shared-resources.
- Sincronizzata tra:
  - `skills-data/albeni-seo-agent/shared-resources/keyword-matrix.csv` (canonica)
  - `skills-data/semrush-specialist/shared-resources/keyword-matrix.csv`

---

## Non modificati (verificati allineati)

### adv-budget-allocator
Lavora su dimensione ortogonale (6 cluster topici A–F: Scienza Materiali, Costruzione Design, Origini Etiche, Innovazione, Lab Pratico, Governance Heritage) — non impattato dai cluster comportamentali. Logica gap_score e transizione 30 giorni invariate.

### albeni-mt-validator
Non esaminato esplicitamente in questa sessione, ma il glossario Reda/Albeni (source of truth) non è cambiato. Eventuali reference a "C1-C6" andranno verificate nel prossimo alignment pass.

---

## Deploy paths

Tutte le modifiche sono state applicate in:
```
/AI STACK APP/ai-orchestration-layer/skills-data/
├── albeni-seo-agent/
│   ├── SKILL.md                              (modified)
│   └── shared-resources/
│       ├── keyword-matrix.csv                (regenerated — 150 KW)
│       └── keyword-matrix.csv.bak-2026-04-16 (backup)
├── albeni-mt-orchestrator/
│   └── SKILL.md                              (modified)
├── albeni-mt-translator/
│   └── SKILL.md                              (modified)
├── semrush-specialist/
│   ├── SKILL.md                              (modified)
│   └── shared-resources/
│       ├── keyword-matrix.csv                (synced — 150 KW)
│       └── keyword-matrix.csv.bak-2026-04-16 (backup)
└── CHANGELOG_2026-04-17.md                   (this file)
```

**Next step**: la `/sessions/.../mnt/.claude/skills/` è read-only e viene risincronizzata dal layer canonico `skills-data/` attraverso la normale pipeline di deploy. Le modifiche saranno visibili al prossimo reload degli agent.
