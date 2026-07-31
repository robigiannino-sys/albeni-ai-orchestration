#!/usr/bin/env python3
"""
Delta di allocazione fra i pesi cluster in produzione e un set candidato.

Perché esiste: cambiare i pesi A-F è una decisione che si prende guardando di
quanto si sposta il budget, non di quanto cambiano i decimali. Fino ad ora quel
confronto si faceva a mano, e la tabella di allocation-model.md era l'unico
posto dove esisteva — ricalcolata a mano, quindi vera solo il giorno in cui è
stata scritta.

Non stima e non inventa: i pesi correnti li legge da advBudgetAllocator.js (la
copia che gira in produzione) e la copertura dalla cluster-page-map generata
dalla crawl map GSC. Se un input manca, si ferma e lo dice.

Uso:
    # delta per un set di pesi ipotetico
    python3 preview_weight_delta.py --weights A=0.28,B=0.12,C=0.18,D=0.08,E=0.22,F=0.12

    # delta per i pesi prodotti da un pull SEMrush
    python3 preview_weight_delta.py --from-csv ../references/kw-volumes-eu-2026-07-31.csv

    # budget diverso da quello della fase attiva
    python3 preview_weight_delta.py --weights ... --budget 1000

Con --from-csv i pesi si ricavano come nel pull: volume ponderato sul mix di
spesa DE 50 / IT 30 / FR 20, perché il peso deve dire dove vanno i soldi.
"""

import argparse
import csv
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SKILL))

ALLOCATOR_JS = os.path.join(REPO, "ai-router", "middleware", "advBudgetAllocator.js")
CLUSTER_MAP = os.path.join(SKILL, "references", "cluster-page-map.md")

CLUSTERS = "ABCDEF"
MARKET_SPLIT = {"de": 0.50, "it": 0.30, "fr": 0.20}


def read_production_weights(path=ALLOCATOR_JS):
    """CLUSTER_KW_WEIGHTS da advBudgetAllocator.js — la copia che conta."""
    if not os.path.isfile(path):
        sys.exit(f"Non trovo {path}: senza i pesi in produzione non c'è delta da mostrare.")
    src = open(path, encoding="utf-8").read()
    block = re.search(r"const CLUSTER_KW_WEIGHTS\s*=\s*\{(.*?)\n\};", src, re.S)
    if not block:
        sys.exit(f"CLUSTER_KW_WEIGHTS non trovato in {path}.")
    found = dict(re.findall(r"(\w+):\s*\{\s*weight:\s*([\d.]+)", block.group(1)))
    weights = {}
    for c in CLUSTERS:
        if c not in found:
            sys.exit(f"Cluster {c} assente da CLUSTER_KW_WEIGHTS: il file è incompleto.")
        weights[c] = float(found[c])
    return weights


def read_coverage(path=CLUSTER_MAP):
    """Totale/indexed per cluster dalla tabella di copertura, più la data di scan."""
    if not os.path.isfile(path):
        sys.exit(f"Non trovo {path}: rigenera con refresh_cluster_map.py.")
    text = open(path, encoding="utf-8").read()

    scan = re.search(r"\*\*Scan\*\*:\s*([\d-]+)", text)
    age = re.search(r"eta'? dato\*\*:\s*(\d+)\s*giorni", text)

    cov = {}
    for c, tot, idx in re.findall(
        r"^\|\s*([A-F])\s*\|[^|]*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", text, re.M
    ):
        cov[c] = {"tot": int(tot), "idx": int(idx)}
    missing = [c for c in CLUSTERS if c not in cov]
    if missing:
        sys.exit(f"Copertura mancante per i cluster {', '.join(missing)} in {path}.")
    return cov, (scan.group(1) if scan else "sconosciuta"), (int(age.group(1)) if age else None)


def weights_from_csv(path):
    """Pesi dal CSV del pull: volume ponderato sul mix di spesa, come in pull_cluster_weights_semrush.py."""
    if not os.path.isfile(path):
        sys.exit(f"Non trovo {path}.")
    wtd = {c: 0.0 for c in CLUSTERS}
    rows = 0
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c, mkt = row.get("Cluster", "").strip(), row.get("Mercato", "").strip().lower()
            if c not in wtd or mkt not in MARKET_SPLIT:
                continue
            wtd[c] += float(row.get("Volume") or 0) * MARKET_SPLIT[mkt]
            rows += 1
    if not rows:
        sys.exit(f"{path} non contiene righe utilizzabili (attese colonne Cluster, Mercato, Volume).")
    tot = sum(wtd.values())
    if tot <= 0:
        sys.exit(f"{path}: volume totale zero, pesi non calcolabili.")
    return {c: wtd[c] / tot for c in CLUSTERS}, rows


def parse_weights(spec):
    """--weights A=0.28,B=0.12,... — normalizza e avvisa se la somma non era 1."""
    out = {}
    for part in spec.split(","):
        if "=" not in part:
            sys.exit(f"Formato pesi non valido: '{part}'. Atteso A=0.28,B=0.12,...")
        k, v = part.split("=", 1)
        k = k.strip().upper()
        if k not in CLUSTERS:
            sys.exit(f"Cluster sconosciuto: '{k}'.")
        out[k] = float(v)
    missing = [c for c in CLUSTERS if c not in out]
    if missing:
        sys.exit(f"Pesi mancanti per {', '.join(missing)}: servono tutti e sei.")
    return out


def allocate(weights, cov, budget):
    """gap_score = non_indexed_ratio × peso, normalizzato sul totale."""
    gap = {}
    for c in CLUSTERS:
        tot, idx = cov[c]["tot"], cov[c]["idx"]
        ratio = (tot - idx) / tot if tot else 0.0
        gap[c] = ratio * weights[c]
    total = sum(gap.values())
    return {
        c: {
            "ratio": (cov[c]["tot"] - cov[c]["idx"]) / cov[c]["tot"] if cov[c]["tot"] else 0.0,
            "gap": gap[c],
            "norm": gap[c] / total if total else 0.0,
            "eur": (gap[c] / total if total else 0.0) * budget,
        }
        for c in CLUSTERS
    }, total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--weights", help="pesi candidati, es. A=0.28,B=0.12,C=0.18,D=0.08,E=0.22,F=0.12")
    src.add_argument("--from-csv", help="CSV prodotto da pull_cluster_weights_semrush.py")
    ap.add_argument("--budget", type=float, default=1667.0,
                    help="budget mensile (default 1667 = fase attiva, phasing uniforme TODO)")
    ap.add_argument("--label", default="candidati", help="etichetta per i pesi candidati nel report")
    args = ap.parse_args()

    cov, scan, age = read_coverage()
    current = read_production_weights()

    if args.from_csv:
        candidate, rows = weights_from_csv(args.from_csv)
        origin = f"{os.path.basename(args.from_csv)} ({rows} righe, ponderate DE 50 / IT 30 / FR 20)"
    else:
        raw = parse_weights(args.weights)
        s = sum(raw.values())
        candidate = {c: raw[c] / s for c in CLUSTERS} if s else raw
        origin = f"--weights (somma {s:.4f}{', normalizzata a 1' if abs(s - 1) > 1e-6 else ''})"

    cur, cur_total = allocate(current, cov, args.budget)
    new, new_total = allocate(candidate, cov, args.budget)

    print(f"\nDelta allocazione ADV — pesi in produzione vs {args.label}")
    print("=" * 78)
    print(f"Scan crawl map: {scan}" + (f" · età {age} giorni" if age is not None else ""))
    if age is not None and age > 7:
        print(f"  ATTENZIONE: dato vecchio di {age} giorni. Rilancia gsc_index_monitor.py "
              f"prima di decidere: il delta qui sotto pesa una copertura stantia.")
    print(f"Pesi candidati da: {origin}")
    print(f"Budget mensile: EUR {args.budget:,.0f}")
    print()

    print(f"{'Cl':<3}{'Non-idx':>9}{'Ratio':>8}{'Peso ora':>10}{'Peso new':>10}"
          f"{'EUR ora':>10}{'EUR new':>10}{'Delta':>10}")
    print("-" * 78)
    for c in CLUSTERS:
        nidx = cov[c]["tot"] - cov[c]["idx"]
        d = new[c]["eur"] - cur[c]["eur"]
        print(f"{c:<3}{nidx:>4}/{cov[c]['tot']:<4}{cur[c]['ratio']:>8.3f}"
              f"{current[c]:>10.4f}{candidate[c]:>10.4f}"
              f"{cur[c]['eur']:>10.0f}{new[c]['eur']:>10.0f}{d:>+10.0f}")
    print("-" * 78)
    print(f"{'Tot':<3}{'':>9}{'':>8}{sum(current.values()):>10.4f}{sum(candidate.values()):>10.4f}"
          f"{sum(v['eur'] for v in cur.values()):>10.0f}"
          f"{sum(v['eur'] for v in new.values()):>10.0f}{0:>+10.0f}")
    print(f"\ngap_score totale: {cur_total:.4f} -> {new_total:.4f}")

    moved = sum(abs(new[c]["eur"] - cur[c]["eur"]) for c in CLUSTERS) / 2
    print(f"Budget che cambia cluster: EUR {moved:,.0f} "
          f"({moved / args.budget * 100:.1f}% del mensile)")

    zeroed = [c for c in CLUSTERS if candidate[c] == 0 and cov[c]["tot"] > cov[c]["idx"]]
    if zeroed:
        print(f"\nATTENZIONE: peso zero su {', '.join(zeroed)}, che hanno pagine non "
              f"indicizzate. Un cluster a peso zero non riceve budget: verifica che sia "
              f"voluto e non un buco di copertura dei seed.")

    if sum(v["eur"] for v in new.values()) < 200:
        print("\nATTENZIONE: totale sotto la soglia di apertura campagna (EUR 200/mese). "
              "Il modello raccomanda Request Indexing manuale + interlinking.")

    print("\nCLUSTER_KW_WEIGHTS per advBudgetAllocator.js:")
    for c in CLUSTERS:
        print(f"  {c}: {{ weight: {candidate[c]:.4f}, ... }},")
    print("\nI pesi vivono in due posti: aggiorna anche la tabella in "
          "references/allocation-model.md nello stesso passaggio.\n")


if __name__ == "__main__":
    main()
