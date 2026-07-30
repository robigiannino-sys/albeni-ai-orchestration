#!/usr/bin/env python3
"""
refresh_cluster_map.py — rigenera references/cluster-page-map.md dalle crawl map GSC.

Perche' esiste: fino al 27/07/2026 cluster-page-map.md era una lista di page ID
scritta a mano, con l'istruzione "aggiorna la colonna status". Non e' mai stata
aggiornata dopo il 10/04, e la skill ha continuato a dichiarare "MU 97,1%
non-indexed" mentre il dato reale era 5,6%. Ogni run partiva da una premessa falsa.
La mappa ora si genera; non si scrive a mano.

Uso:
    python3 refresh_cluster_map.py                    # scrive ../references/cluster-page-map.md
    python3 refresh_cluster_map.py --stdout           # stampa e basta
    python3 refresh_cluster_map.py --crawl-dir <dir>  # crawl map altrove

Da lanciare dopo ogni scan di gsc_index_monitor.py (Step 5 della skill gsc-index-monitor).
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CRAWL_DIR = Path("/Users/roberto/Documents/Claude/Projects/albeni1905.com/scripts")
MONITOR_SCRIPT = DEFAULT_CRAWL_DIR / "gsc_index_monitor.py"

CLUSTER_NAMES = {
    "A": "Scienza Materiali",
    "B": "Costruzione Design",
    "C": "Origini Etiche",
    "D": "Innovazione",
    "E": "Lab Pratico",
    "F": "Governance Heritage",
}

# ATTENZIONE: copia fedele di classify_for_adv() in gsc_index_monitor.py (~riga 956).
# E' duplicata perche' li' e' una funzione annidata, non importabile. check_classifier_drift()
# piu' sotto confronta le due liste a ogni run e avvisa se divergono: se scatta l'alert,
# riallineare QUESTA copia a quella del monitor, che resta la sorgente autorevole.
CLUSTER_RULES = [
    ("A", ["material-science", "cheratina", "keratin", "termoregola", "micron",
           "cotone-vs", "cotton-vs", "gsm-decoded", "lca-", "alpha-keratin",
           "gold-standard", "etalon-or"]),
    ("B", ["construction", "artigianalita", "craftsmanship", "architecture-of-fit",
           "coupe-cousu", "architektur"]),
    ("C", ["ethical", "governance", "dal-vello", "sostenibilita", "sustainability",
           "lca", "zq-proto", "durabilite", "nachhaltigkeit", "from-fleece",
           "vom-vlies", "de-la-toison", "filiera"]),
    ("D", ["innovation", "plasma", "compact-tech"]),
    ("E", ["practical-lab", "cost-per-wear", "capsule", "business-travel",
           "maintenance", "guardaroba", "wardrobe", "checklist", "grammatura",
           "weight", "grammage", "gewicht", "150g-190g"]),
    ("F", ["heritage", "manifesto", "redazione", "editorial", "storie",
           "stories", "field-note", "guide", "lead-magnet"]),
]

# Guardrail: mai allocare paid. Pattern su URL, non page ID (gli ID cambiano, i path no).
EXCLUDE_PATTERNS = [
    "cookie-policy", "privacy-policy", "politique-confidentialite", "datenschutz",
    "/category/", "lead-magnet", "/contatti", "/contact", "/faq", "/manifesto",
    "impressum", "termini", "terms", "/audit",
]


def classify(url_path: str) -> str:
    p = url_path.lower()
    for cluster, keys in CLUSTER_RULES:
        if any(k in p for k in keys):
            return cluster
    return "A"  # fallback, come nel monitor


def is_excluded(url_path: str) -> bool:
    p = url_path.lower()
    if p in ("/", ""):
        return True
    return any(k in p for k in EXCLUDE_PATTERNS)


def check_classifier_drift(monitor_path: Path) -> list[str]:
    """Confronta le keyword list locali con quelle di gsc_index_monitor.py."""
    warnings = []
    if not monitor_path.exists():
        return [f"monitor non trovato in {monitor_path} — drift non verificabile"]
    src = monitor_path.read_text(encoding="utf-8", errors="replace")
    # fino al fallback finale, non al primo `return 'A'` (che chiude il cluster A)
    block = re.search(r"def classify_for_adv.*?return 'A'\s*#\s*fallback", src, re.S)
    if not block:
        return ["classify_for_adv() non trovata nel monitor — drift non verificabile"]
    body = block.group(0)
    for cluster, keys in CLUSTER_RULES:
        # [^\]]* e non .*? : altrimenti la cattura scavalca le liste dei cluster precedenti
        found = re.search(
            r"if any\(k in p for k in \[([^\]]*)\]\):\s*\n\s*return '%s'" % cluster, body, re.S
        )
        if not found:
            warnings.append(f"cluster {cluster}: regola assente nel monitor")
            continue
        monitor_keys = set(re.findall(r"'([^']+)'", found.group(1)))
        local_keys = set(keys)
        if monitor_keys != local_keys:
            only_m = sorted(monitor_keys - local_keys)
            only_l = sorted(local_keys - monitor_keys)
            warnings.append(
                f"cluster {cluster}: DRIFT — solo nel monitor {only_m} / solo qui {only_l}"
            )
    return warnings


def load_maps(crawl_dir: Path) -> dict[str, dict[str, str]]:
    maps = {}
    for site, fname in (("MU", "mu_crawl_map.json"), ("WoM", "wom_crawl_map.json")):
        path = crawl_dir / fname
        if not path.exists():
            sys.exit(f"ERRORE: crawl map mancante: {path}")
        maps[site] = json.loads(path.read_text(encoding="utf-8"))
    return maps


def scan_age_days(crawl_dir: Path) -> tuple[str, int]:
    mtimes = [
        (crawl_dir / f).stat().st_mtime
        for f in ("mu_crawl_map.json", "wom_crawl_map.json")
        if (crawl_dir / f).exists()
    ]
    newest = datetime.fromtimestamp(max(mtimes), tz=timezone.utc)
    age = (datetime.now(timezone.utc) - newest).days
    return newest.strftime("%Y-%m-%d"), age


def build_report(maps, scan_date, age, drift):
    agg = defaultdict(lambda: {"tot": 0, "idx": 0, "excl": 0, "neutral": []})
    per_site = {}
    for site, cmap in maps.items():
        s = {"tot": len(cmap), "idx": sum(1 for v in cmap.values() if v == "PASS")}
        per_site[site] = s
        for url, verdict in cmap.items():
            c = classify(url)
            if is_excluded(url):
                agg[c]["excl"] += 1
                continue
            agg[c]["tot"] += 1
            if verdict == "PASS":
                agg[c]["idx"] += 1
            else:
                agg[c]["neutral"].append((site, url, verdict))

    L = []
    L.append("# Cluster-Page Map — stato di indicizzazione")
    L.append("")
    L.append("> ⚠️ **FILE GENERATO — non modificare a mano.**")
    L.append("> Rigenera con: `python3 scripts/refresh_cluster_map.py`")
    L.append("> Sorgente: `mu_crawl_map.json` + `wom_crawl_map.json` prodotte da `gsc_index_monitor.py`.")
    L.append("")
    L.append(f"**Scan**: {scan_date} · **eta' dato**: {age} giorni")
    if age > 7:
        L.append("")
        L.append(f"> 🔴 **Dato vecchio di {age} giorni.** Rilanciare `gsc_index_monitor.py` "
                 "prima di decidere allocazioni: la coda paid→organic si muove di settimana in settimana.")
    L.append("")

    if drift:
        L.append("## ⚠️ Drift del classificatore")
        L.append("")
        L.append("Le regole di questo script divergono da `classify_for_adv()` in `gsc_index_monitor.py` "
                 "(sorgente autorevole). Riallineare `CLUSTER_RULES` prima di fidarsi dei numeri:")
        L.append("")
        for w in drift:
            L.append(f"- {w}")
        L.append("")

    L.append("## Copertura per dominio")
    L.append("")
    L.append("| Dominio | Totale | Indexed | Coverage |")
    L.append("|---|---:|---:|---:|")
    gt = gi = 0
    for site, s in per_site.items():
        gt += s["tot"]; gi += s["idx"]
        L.append(f"| {site} | {s['tot']} | {s['idx']} | {s['idx']/s['tot']*100:.1f}% |")
    L.append(f"| **Totale** | **{gt}** | **{gi}** | **{gi/gt*100:.1f}%** |")
    L.append("")

    L.append("## Copertura per cluster (esclusi i guardrail)")
    L.append("")
    L.append("| Cluster | Nome | Totale | Indexed | Non-idx | Rate | Esclusi |")
    L.append("|---|---|---:|---:|---:|---:|---:|")
    for c in "ABCDEF":
        a = agg[c]
        rate = a["idx"] / a["tot"] * 100 if a["tot"] else 0.0
        L.append(f"| {c} | {CLUSTER_NAMES[c]} | {a['tot']} | {a['idx']} | "
                 f"{a['tot']-a['idx']} | {rate:.1f}% | {a['excl']} |")
    L.append("")

    L.append("## Pagine non indicizzate, per cluster")
    L.append("")
    L.append("Sono le candidate alla compensazione paid. Le pagine escluse dai guardrail "
             "(legal, category, lead-magnet, home, contatti) non compaiono.")
    L.append("")
    for c in "ABCDEF":
        rows = sorted(agg[c]["neutral"])
        L.append(f"### {c} — {CLUSTER_NAMES[c]} ({len(rows)})")
        L.append("")
        if not rows:
            L.append("Nessuna. Cluster interamente coperto: allocazione €0, "
                     "quota redistribuita agli altri.")
        else:
            L.append("| Dominio | URL | Verdict |")
            L.append("|---|---|---|")
            for site, url, verdict in rows:
                L.append(f"| {site} | `{url}` | {verdict} |")
        L.append("")

    L.append("---")
    L.append(f"*Generato da `scripts/refresh_cluster_map.py` · classificatore allineato a "
             f"`classify_for_adv()` di `gsc_index_monitor.py`{' — ⚠️ CON DRIFT' if drift else ''}.*")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crawl-dir", type=Path, default=DEFAULT_CRAWL_DIR)
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parent.parent / "references" / "cluster-page-map.md")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    maps = load_maps(args.crawl_dir)
    scan_date, age = scan_age_days(args.crawl_dir)
    drift = check_classifier_drift(args.crawl_dir / "gsc_index_monitor.py")
    report = build_report(maps, scan_date, age, drift)

    if args.stdout:
        print(report)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"✅ scritto {args.out}")

    print(f"   scan {scan_date} ({age} gg)"
          + ("  🔴 DATO VECCHIO" if age > 7 else ""))
    for w in drift:
        print(f"   ⚠️  drift classificatore: {w}")


if __name__ == "__main__":
    main()
