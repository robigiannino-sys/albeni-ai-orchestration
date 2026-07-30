# Cluster-Page Map — stato di indicizzazione

> ⚠️ **FILE GENERATO — non modificare a mano.**
> Rigenera con: `python3 scripts/refresh_cluster_map.py`
> Sorgente: `mu_crawl_map.json` + `wom_crawl_map.json` prodotte da `gsc_index_monitor.py`.

**Scan**: 2026-07-08 · **eta' dato**: 18 giorni

> 🔴 **Dato vecchio di 18 giorni.** Rilanciare `gsc_index_monitor.py` prima di decidere allocazioni: la coda paid→organic si muove di settimana in settimana.

## Copertura per dominio

| Dominio | Totale | Indexed | Coverage |
|---|---:|---:|---:|
| MU | 322 | 304 | 94.4% |
| WoM | 418 | 359 | 85.9% |
| **Totale** | **740** | **663** | **89.6%** |

## Copertura per cluster (esclusi i guardrail)

| Cluster | Nome | Totale | Indexed | Non-idx | Rate | Esclusi |
|---|---|---:|---:|---:|---:|---:|
| A | Scienza Materiali | 299 | 270 | 29 | 90.3% | 18 |
| B | Costruzione Design | 20 | 19 | 1 | 95.0% | 0 |
| C | Origini Etiche | 77 | 68 | 9 | 88.3% | 5 |
| D | Innovazione | 17 | 16 | 1 | 94.1% | 0 |
| E | Lab Pratico | 68 | 60 | 8 | 88.2% | 4 |
| F | Governance Heritage | 213 | 190 | 23 | 89.2% | 19 |

## Pagine non indicizzate, per cluster

Sono le candidate alla compensazione paid. Le pagine escluse dai guardrail (legal, category, lead-magnet, home, contatti) non compaiono.

### A — Scienza Materiali (29)

| Dominio | URL | Verdict |
|---|---|---|
| MU | `/de/de-observatorium/de-dwr-markt-pfas-freie-wolltechnologien` | NEUTRAL |
| MU | `/de/de-observatorium/de-espr-2026-vernichtungsverbot-unverkaufte-waren-textil` | NEUTRAL |
| MU | `/de/de-observatorium/de-iso-14067-biogener-kohlenstoff-merinowolle-klimabilanz` | NEUTRAL |
| MU | `/en/en-observatory/en-iso-14067-biogenic-carbon-merino-wool-carbon-footprint` | NEUTRAL |
| MU | `/fr/departement-origines-ethique` | NEUTRAL |
| MU | `/fr/fr-analyse-cycle-vie` | NEUTRAL |
| MU | `/fr/fr-standards-gouvernance-mondiale` | NEUTRAL |
| MU | `/fr/fr-thermoregulation-active-laine-merinos` | NEUTRAL |
| MU | `/fr/standard-or-17-microns` | NEUTRAL |
| MU | `/reda-super-120s` | NEUTRAL |
| WoM | `/de/de-das-ende-der-wegwerfmode-eu-vernichtungsverbot-textilien-19-juli` | NEUTRAL |
| WoM | `/de/de-die-seele-des-wassers-warum-biella-die-italienische-wolle-erfunden-hat` | NEUTRAL |
| WoM | `/de/de-merinowolle-preis-markt-belohnt-dauerhafte-garderobe` | NEUTRAL |
| WoM | `/de/de-professionisti-in-bewegung/de-merino-koffer-eine-woche-buegelfrei` | NEUTRAL |
| WoM | `/de/de-weniger-kaufen-besser-kaufen-eu-verbot-textilvernichtung` | NEUTRAL |
| WoM | `/en-us/en-about-us` | NEUTRAL |
| WoM | `/en-us/en-professionals-on-the-move/en-merino-suitcase-no-iron-one-week` | NEUTRAL |
| WoM | `/en-us/en-professionals-on-the-move/en-smart-layering-2-layers` | NEUTRAL |
| WoM | `/fr/fr-professionnels-en-mouvement/fr-merino-valise-sans-repassage` | NEUTRAL |
| WoM | `/fr/fr-professionnels-en-mouvement/fr-smart-casual-sans-erreurs` | NEUTRAL |
| WoM | `/fr/fr-tissus-italiens-qualite-culture-materielle` | NEUTRAL |
| WoM | `/i-dieci-virgola-quattro-micron-che-non-fanno-rumore` | NEUTRAL |
| WoM | `/il-salone-che-ha-rimesso-la-materia-al-centro` | NEUTRAL |
| WoM | `/investire-nel-vestire-formula-costo-per-utilizzo` | NEUTRAL |
| WoM | `/professionisti-in-movimento/aereo-boardroom-stabilita-termica-viaggio` | NEUTRAL |
| WoM | `/professionisti-in-movimento/dal-volo-alla-riunione` | NEUTRAL |
| WoM | `/professionisti-in-movimento/en-one-bag-for-work` | NEUTRAL |
| WoM | `/professionisti-in-movimento/merino-valigia-senza-stiro` | NEUTRAL |
| WoM | `/quarantotto-ore-una-borsa-zero-compromessi-bleisure-genz` | NEUTRAL |

### B — Costruzione Design (1)

| Dominio | URL | Verdict |
|---|---|---|
| MU | `/fr/fr-artisanat-italien-vetements-construction-sartoriale` | NEUTRAL |

### C — Origini Etiche (9)

| Dominio | URL | Verdict |
|---|---|---|
| MU | `/de/de-department-practical-lab/de-checkliste-textile-nachhaltigkeit-merino` | NEUTRAL |
| MU | `/fr/fr-durabilite-merinos-choix-conscient` | NEUTRAL |
| WoM | `/de/de-nachhaltigkeit-jenseits-der-versprechen/de-empfindliche-haut-und-stoffe` | NEUTRAL |
| WoM | `/de/de-nachhaltigkeit-jenseits-der-versprechen/de-premium-tshirt-erkennen` | NEUTRAL |
| WoM | `/en-us/en-sustainability-beyond-promises/en-iron-free-care-guide` | NEUTRAL |
| WoM | `/fr/fr-durabilite-au-dela-des-promesses/fr-calculateur-cout-par-port` | NEUTRAL |
| WoM | `/fr/fr-durabilite-au-dela-des-promesses/fr-entretien-sans-repassage` | NEUTRAL |
| WoM | `/fr/fr-durabilite-au-dela-des-promesses/fr-guide-sans-repassage-entretien-invisible` | NEUTRAL |
| WoM | `/fr/fr-durabilite-au-dela-des-promesses/fr-peau-sensible-et-tissus` | NEUTRAL |

### D — Innovazione (1)

| Dominio | URL | Verdict |
|---|---|---|
| MU | `/fr/fr-innovation-avenir` | NEUTRAL |

### E — Lab Pratico (8)

| Dominio | URL | Verdict |
|---|---|---|
| MU | `/de/de-department-practical-lab/de-merinowolle-langlebigkeit-pflege-guide` | NEUTRAL |
| MU | `/en/en-cost-per-wear-investing` | NEUTRAL |
| MU | `/en/en-department-practical-lab/en-checklist-sensory-quality-merino` | NEUTRAL |
| MU | `/fr/fr-laboratoire-pratique/fr-checklist-qualite-sensorielle-merino` | NEUTRAL |
| WoM | `/en-us/en-investment-dressing-cost-per-wear-formula` | NEUTRAL |
| WoM | `/fr/fr-professionnels-en-mouvement/fr-travel-light-checklist` | NEUTRAL |
| WoM | `/guardaroba-minimalista-maschile-meno-capi-piu-stile` | NEUTRAL |
| WoM | `/heritage-archive/capsule-12-capi-30-giorni` | NEUTRAL |

### F — Governance Heritage (23)

| Dominio | URL | Verdict |
|---|---|---|
| WoM | `/de/de-heritage-archive` | NEUTRAL |
| WoM | `/de/de-heritage-archive/de-geste-03-der-rhythmuswechsel-buro-%e2%86%92-abend-in-10-minuten` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-art-of-transition-office-evening` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-gesture-01-hang-let-breathe-30-minutes` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-hanger-method` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-impulse-trap-quick-buys-cost-more-de-2` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-impulse-trap-quick-buys-cost-more-fr` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-label-illusion-brand-names-quality-fr` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-merino-wool-complete-guide` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-mistake-01-buying-occasions-not-frequency` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-mistake-03-wishful-size` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-rule-01-wear-twice-deserves-quality` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-rule-05-invisible-comfort-stable-style` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-rule-06-rule-of-three` | NEUTRAL |
| WoM | `/en-us/en-heritage-archive/en-the-hem-defines-everything` | NEUTRAL |
| WoM | `/en-us/en-professionals-on-the-move/en-merino-wool-base-layer-guide` | NEUTRAL |
| WoM | `/field-note/gesto-02-piega-evita-righe` | NEUTRAL |
| WoM | `/field-note/gesto-04-prepara-3-outfit-autopilota` | NEUTRAL |
| WoM | `/field-note/regola-04-un-neutro-batte-tre-colori` | NEUTRAL |
| WoM | `/fr/fr-heritage-archive/fr-laine-merinos-guide-complet` | NEUTRAL |
| WoM | `/fr/fr-heritage-archive/fr-regle-05-confort-invisible-style-stable` | NEUTRAL |
| WoM | `/fr/fr-marques-italiennes-vetements-homme-qualite-heritage` | NEUTRAL |
| WoM | `/heritage-archive/gesto-03-il-cambio-ritmo-ufficio-%e2%86%92-sera-in-10-minuti` | NEUTRAL |

---
*Generato da `scripts/refresh_cluster_map.py` · classificatore allineato a `classify_for_adv()` di `gsc_index_monitor.py`.*
