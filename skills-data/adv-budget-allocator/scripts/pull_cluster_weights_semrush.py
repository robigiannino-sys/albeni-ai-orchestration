#!/usr/bin/env python3
"""
Pull SEMrush per i pesi keyword dei cluster A-F sull'envelope EU (DE/IT/FR).

Perché esiste: il 30/07/2026 il ricalcolo dei pesi si è fermato per due motivi
insieme. L'API era a zero unità (ERROR 132), e la keyword-matrix locale non può
sostituirla: delle 61 head-term con volume EU, 24 sono assegnate a MU/WoM — i
soli domini che l'allocatore compensa — e coprono tre cluster su sei, lasciando
A (29 pagine non indicizzate, il gap più grande), B e D a peso zero. Servono
volumi EU per le head-term dei cluster editoriali, e quelli si prendono solo con
un pull.

Questo script è quel pull, pronto a partire. Non stima e non inventa: se le
unità non bastano si ferma prima di consumare.

Uso:
    export SEMRUSH_API_KEY=...        # railway variables --service albeni-ai-orchestration
    python3 pull_cluster_weights_semrush.py            # dry-run: unità e costo
    python3 pull_cluster_weights_semrush.py --confirm   # esegue

Output:
    references/kw-volumes-eu-<data>.csv  — una riga per (keyword, mercato)
    tabella "Pesi keyword per cluster" pronta da incollare in allocation-model.md
    e in ai-router/middleware/advBudgetAllocator.js (CLUSTER_KW_WEIGHTS)
"""

import csv
import io
import os
import sys
from datetime import date

import requests

API = "https://api.semrush.com/"
UNITS_URL = "https://www.semrush.com/users/countapiunits.html"
KEY = os.environ.get("SEMRUSH_API_KEY", "")
DATABASES = ["de", "it", "fr"]
MARKET_SPLIT = {"de": 0.50, "it": 0.30, "fr": 0.20}   # envelope €5K EU, piano di lancio

# Costo del listino API standard per `phrase_these`: 10 unità per riga restituita.
# Va riverificato a piano attivo — se SEMrush ha cambiato listino, il dry-run
# sotto stima male e il conto vero lo dà countapiunits prima/dopo.
UNITS_PER_LINE = 10

# Seed per cluster, nella lingua del mercato. Il vocabolario ricalca
# CLUSTER_RULES in refresh_cluster_map.py — che è il classificatore delle pagine —
# così il peso misura la domanda per il contenuto che quel cluster ospita, e non
# la domanda commerciale del capo, che appartiene allo store e non a MU/WoM.
# Il perimetro dei termini è la memoria di progetto `microne-termini-da-difendere`.
SEEDS = {
    "A": {  # Scienza Materiali
        "de": ["merinowolle eigenschaften", "merino 17 mikron", "wolle thermoregulierung",
               "merino vs baumwolle", "merinowolle feinheit"],
        "it": ["lana merino proprietà", "micron lana merino", "lana merino vs cotone",
               "termoregolazione lana", "finezza lana merino"],
        "fr": ["laine mérinos propriétés", "mérinos vs coton", "thermorégulation laine",
               "finesse laine mérinos", "micron laine mérinos"],
    },
    "B": {  # Costruzione Design
        "de": ["t-shirt verarbeitung", "geschnitten und genäht", "nahtlos oder geschnitten",
               "t-shirt passform"],
        "it": ["taglio e cucito t-shirt", "maglieria taglio e cucito", "vestibilità t-shirt",
               "confezione t-shirt"],
        "fr": ["t-shirt coupé cousu", "coupe t-shirt homme", "confection t-shirt"],
    },
    "C": {  # Origini Etiche
        "de": ["nachhaltige wolle", "rws zertifizierte wolle", "wolle lieferkette",
               "wolle rückverfolgbarkeit"],
        "it": ["lana sostenibile", "filiera lana tracciabile", "certificazione RWS lana",
               "lana rigenerativa"],
        "fr": ["laine durable", "laine traçabilité", "laine certifiée RWS"],
    },
    "D": {  # Innovazione
        "de": ["merino technologie", "funktionswolle", "wolle funktionstextil"],
        "it": ["tecnologia lana merino", "tessuto tecnico merino", "lana performance"],
        "fr": ["technologie laine mérinos", "laine technique", "textile technique laine"],
    },
    "E": {  # Lab Pratico
        "de": ["merinowolle waschen", "merino pflege", "kapselgarderobe herren",
               "business reise kleidung", "wolle grammatur"],
        "it": ["lavare lana merino", "cura lana merino", "guardaroba capsula uomo",
               "valigia viaggio business", "grammatura tessuto"],
        "fr": ["laver laine mérinos", "entretien laine mérinos", "garde-robe capsule homme",
               "valise voyage affaires"],
    },
    "F": {  # Governance Heritage
        "de": ["italienische wolle", "made in italy kleidung", "italienische stoffe"],
        "it": ["lana made in italy", "tessuti italiani pregiati", "sartorialità italiana"],
        "fr": ["laine italienne", "made in italy vêtement", "tissus italiens"],
    },
}

CLUSTER_NAMES = {"A": "Scienza Materiali", "B": "Costruzione Design", "C": "Origini Etiche",
                 "D": "Innovazione", "E": "Lab Pratico", "F": "Governance Heritage"}


def units_left() -> int:
    r = requests.get(UNITS_URL, params={"key": KEY}, timeout=30)
    return int(r.text.strip()) if r.text.strip().isdigit() else -1


def pull(phrases, db):
    """phrase_these: un batch di frasi su un database. Ritorna (righe, errore)."""
    r = requests.get(API, params={
        "type": "phrase_these", "key": KEY, "database": db,
        "phrase": ";".join(phrases),
        "export_columns": "Ph,Nq,Cp,Kd,Co,Nr",
    }, timeout=90)
    if r.text.startswith("ERROR"):
        return [], r.text.strip()
    return list(csv.DictReader(io.StringIO(r.text), delimiter=";")), None


def main():
    if not KEY:
        sys.exit("SEMRUSH_API_KEY non impostata.")

    lines = sum(len(v) for c in SEEDS.values() for v in c.values())
    left = units_left()
    cost = lines * UNITS_PER_LINE
    print(f"Seed totali: {lines} righe ({len(DATABASES)} database) · costo stimato {cost:,} unità "
          f"({UNITS_PER_LINE}/riga, listino da riverificare)")
    print(f"Unità residue: {left:,}" if left >= 0 else "Unità residue: non leggibili")

    if "--confirm" not in sys.argv:
        print("\nDry-run. Rilancia con --confirm per eseguire.")
        return
    if 0 <= left < cost:
        sys.exit(f"Unità insufficienti: servono ~{cost:,}, disponibili {left:,}. Niente pull.")

    got, errors = [], []
    for cluster, per_db in SEEDS.items():
        for db, phrases in per_db.items():
            rows, err = pull(phrases, db)
            if err:
                errors.append(f"{cluster}/{db}: {err}")
                continue
            for row in rows:
                got.append({
                    "Cluster": cluster, "Cluster nome": CLUSTER_NAMES[cluster], "Mercato": db,
                    "Keyword": row.get("Keyword", ""), "Volume": int(row.get("Search Volume") or 0),
                    "CPC": row.get("CPC", ""), "KD": row.get("Keyword Difficulty", ""),
                    "Competizione": row.get("Competition", ""),
                    "Risultati": row.get("Number of Results", ""),
                })
            print(f"  {cluster}/{db}: {len(rows)} righe")

    if not got:
        sys.exit("Nessun dato. " + " · ".join(errors))

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "references", f"kw-volumes-eu-{date.today().isoformat()}.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(got[0].keys()))
        w.writeheader()
        w.writerows(got)
    print(f"\nScritto {out} ({len(got)} righe)")

    # Pesi: volume ponderato sul mix di spesa, non sul volume grezzo — il peso
    # deve dire dove vanno i soldi, e i soldi seguono DE 50 / IT 30 / FR 20.
    wtd = {c: 0.0 for c in SEEDS}
    for g in got:
        wtd[g["Cluster"]] += g["Volume"] * MARKET_SPLIT[g["Mercato"]]
    tot = sum(wtd.values())
    print(f"\n| Cluster | Tema KW | Quota volume EU | Peso |\n|---|---|---|---|")
    for c in SEEDS:
        q = wtd[c] / tot if tot else 0
        print(f"| {c}: {CLUSTER_NAMES[c]} | {', '.join(SEEDS[c]['de'][:2])} | {q:.1%} | {q:.3f} |")
    print("\nCLUSTER_KW_WEIGHTS per advBudgetAllocator.js:")
    for c in SEEDS:
        print(f"  {c}: {{ weight: {wtd[c]/tot if tot else 0:.3f}, label: '{CLUSTER_NAMES[c]}' }},")

    if errors:
        print("\nErrori:")
        for e in errors:
            print("  " + e)
    print(f"\nUnità dopo il pull: {units_left():,}")


if __name__ == "__main__":
    main()
