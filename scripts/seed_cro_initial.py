#!/usr/bin/env python3
"""
Seed iniziale CRO Engine — Step 7 fase rollout, 2026-05-14.

Popola Postgres con 3 slot operativi + 10 variant cluster-aware per il primo
A/B test live su MU / WoM. Mappatura cluster ↔ tono basata su:
- Heritage Mature → eleganza, asset, qualità invisibile
- Business Professional → efficienza, layering, mobilità
- (Generic, cluster=NULL) → fallback per chi non ha ancora cluster assegnato

Usage:
    cd "/Users/roberto/Desktop/ALBENI/albeni.com/STEFANO/AI STACK APP/ai-orchestration-layer"
    python3 scripts/seed_cro_initial.py            # popola tutto
    python3 scripts/seed_cro_initial.py --dry-run  # mostra cosa farebbe
    python3 scripts/seed_cro_initial.py --slot homepage_hero_cta  # solo uno

Idempotente: re-run aggiorna i text esistenti (UPSERT lato backend).
"""
import argparse
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Missing: pip install httpx --user --break-system-packages", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://albeni-ai-orchestration-production.up.railway.app"


# Definizione operativa del seed iniziale.
# Ogni slot ha 3-4 variant: generic (fallback) + 1-2 cluster-specific.
SEED = {
    "homepage_hero_cta": {
        "description": "CTA principale dell'hero homepage WoM/MU. Primo touchpoint del visitor.",
        "variants": [
            # Generic baseline — funziona per tutti, è il safety net
            {"variant_key": "generic_discover", "text": "Scopri l'invisible luxury merino",
             "cluster": None, "language": "it"},
            # Cluster Heritage Mature → tono asset/longevità
            {"variant_key": "heritage_legacy", "text": "Capi che durano. Eleganza che non chiede attenzione.",
             "cluster": "heritage_mature", "language": "it"},
            # Cluster Business Professional → tono efficienza/mobilità
            {"variant_key": "business_efficient", "text": "Layering intelligente. Da meeting a viaggio in 2 strati.",
             "cluster": "business_professional", "language": "it"},
            # English (en-us) generic
            {"variant_key": "generic_discover_en", "text": "Discover invisible luxury merino",
             "cluster": None, "language": "en"},
        ],
    },
    "newsletter_signup_headline": {
        "description": "Headline del form newsletter signup. Conversione TOFU → MOFU.",
        "variants": [
            # Generic baseline
            {"variant_key": "generic_journal", "text": "Iscriviti al Journal — note di campo settimanali",
             "cluster": None, "language": "it"},
            # Heritage Mature → angle culturale, archive, ritualità
            {"variant_key": "heritage_archive", "text": "Field Notes dall'Heritage Archive. Una settimana, un dettaglio.",
             "cluster": "heritage_mature", "language": "it"},
            # Business Professional → angle praticità, viaggio, layering
            {"variant_key": "business_briefing", "text": "Briefing settimanale per chi viaggia leggero.",
             "cluster": "business_professional", "language": "it"},
        ],
    },
    "product_card_cta": {
        "description": "CTA sulle card prodotto (collection grid). Conversione MOFU → BOFU.",
        "variants": [
            # Generic baseline
            {"variant_key": "generic_view", "text": "Vedi dettagli",
             "cluster": None, "language": "it"},
            # Heritage Mature → tono asset/investment
            {"variant_key": "heritage_invest", "text": "Investi nel comfort invisibile",
             "cluster": "heritage_mature", "language": "it"},
            # Business Professional → tono pragmatico/funzionale
            {"variant_key": "business_function", "text": "Performance + eleganza",
             "cluster": "business_professional", "language": "it"},
        ],
    },
}


def _load_env() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed iniziale CRO Engine")
    ap.add_argument("--slot", choices=list(SEED.keys()), default=None,
                    help="Seed solo uno slot (default: tutti)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Mostra cosa farebbe, non POSTa")
    args = ap.parse_args()

    _load_env()
    base = os.environ.get("ML_WORKER_PUBLIC_URL", DEFAULT_BASE).rstrip("/")
    api_key = os.environ.get("API_KEY")
    if not api_key:
        print("ERROR: API_KEY not set in .env", file=sys.stderr)
        return 2

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    slots = [args.slot] if args.slot else list(SEED.keys())

    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  CRO seed → {base}")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'LIVE'} · Slots: {', '.join(slots)}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    total_slots = 0
    total_variants = 0

    for slot_key in slots:
        config = SEED[slot_key]
        print(f"\n  ─ {slot_key}")
        print(f"    {config['description']}")

        # Create/update slot
        if not args.dry_run:
            r = httpx.post(f"{base}/v1/cro/slot", headers=headers,
                           json={"slot_key": slot_key, "description": config["description"]},
                           timeout=30.0)
            if r.status_code != 200:
                print(f"    ERROR slot: HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
                continue
            print(f"    slot {r.json().get('status')}: id={r.json().get('slot_id')}")
        total_slots += 1

        # Create/update variants
        for v in config["variants"]:
            cluster_str = f"[{v['cluster']}]" if v["cluster"] else "[generic]"
            lang_str = v["language"]
            preview = v["text"][:60] + ("…" if len(v["text"]) > 60 else "")
            print(f"      {cluster_str:25s} {lang_str}  «{preview}»")
            if not args.dry_run:
                body = {"slot_key": slot_key, **v}
                r = httpx.post(f"{base}/v1/cro/variant", headers=headers, json=body, timeout=30.0)
                if r.status_code != 200:
                    print(f"      ERROR variant: HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
                    continue
            total_variants += 1

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Done · {total_slots} slot(s) · {total_variants} variant(s)")
    if not args.dry_run:
        print(f"\n  Verifica:")
        print(f"  curl -s '{base}/v1/cro/stats' | python3 -m json.tool")
    return 0


if __name__ == "__main__":
    sys.exit(main())
