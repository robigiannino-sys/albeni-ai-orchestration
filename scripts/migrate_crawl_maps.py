#!/usr/bin/env python3
"""
One-shot migration: wom_crawl_map.json + mu_crawl_map.json → Postgres tabella crawl_map_entries.
Step 5 (NEW-02 audit closure), 2026-05-14.

Usage:
    cd "/Users/roberto/Desktop/ALBENI/albeni.com/STEFANO/AI STACK APP/ai-orchestration-layer"
    python3 scripts/migrate_crawl_maps.py            # legge entrambi i siti, POSTa al ml-worker
    python3 scripts/migrate_crawl_maps.py --dry-run  # solo conteggio, niente POST
    python3 scripts/migrate_crawl_maps.py --site mu  # solo MU

Env (riusa pattern recompute_pipeline.py):
    API_KEY (default albeni1905-internal-api-v1)
    ML_WORKER_PUBLIC_URL (default https://albeni-ai-orchestration-production.up.railway.app)

Note:
    - Idempotente: re-run sovrascrive (UPSERT su site+url_path)
    - Batch size 500 per evitare payload troppo grandi
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

try:
    import httpx
except ImportError:
    print("Missing dependency: pip install httpx", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_PATHS = {
    "mu":  REPO_ROOT / "ai-router" / "dashboard" / "mu_crawl_map.json",
    "wom": REPO_ROOT / "ai-router" / "dashboard" / "wom_crawl_map.json",
}
BATCH_SIZE = 500
DEFAULT_BASE = "https://albeni-ai-orchestration-production.up.railway.app"


def _load_env() -> None:
    """Carica .env dal repo root (riusa pattern recompute_pipeline.py)."""
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _post_batch(base: str, api_key: str, site: str, entries: List[Dict], dry_run: bool) -> Dict:
    if dry_run:
        return {"status": "dry-run", "inserted": len(entries)}
    url = f"{base.rstrip('/')}/v1/crawl-map/batch"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    body = {"site": site, "entries": entries, "source": "migration_json"}
    r = httpx.post(url, headers=headers, json=body, timeout=120.0)
    if r.status_code not in (200, 207):
        print(f"  ERROR: HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
        sys.exit(1)
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser(description="Migrate crawl_map JSON → Postgres")
    ap.add_argument("--site", choices=["mu", "wom"], default=None,
                    help="Migrate only one site (default: both)")
    ap.add_argument("--dry-run", action="store_true", help="Skip POST, just count")
    args = ap.parse_args()

    _load_env()
    base = os.environ.get("ML_WORKER_PUBLIC_URL", DEFAULT_BASE)
    api_key = os.environ.get("API_KEY")
    if not api_key:
        print("ERROR: API_KEY not set", file=sys.stderr)
        return 2

    sites = [args.site] if args.site else ["mu", "wom"]

    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Crawl map migration → {base}")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'LIVE'} · Sites: {', '.join(sites)}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    grand_total = 0
    for site in sites:
        path = JSON_PATHS[site]
        if not path.is_file():
            print(f"  ⚠ {site}: file not found at {path} — skip", file=sys.stderr)
            continue
        print(f"\n  ─ {site}: reading {path.name}")
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            print(f"    ERROR: invalid JSON: {e}", file=sys.stderr)
            continue
        if not isinstance(raw, dict):
            print(f"    ERROR: expected dict, got {type(raw).__name__}", file=sys.stderr)
            continue

        # Verdict breakdown (audit preliminare)
        verdict_counts: Dict[str, int] = {}
        for v in raw.values():
            verdict_counts[v] = verdict_counts.get(v, 0) + 1
        print(f"    URLs: {len(raw)} · breakdown: {dict(sorted(verdict_counts.items()))}")

        # Build payload + batch POST
        entries = [{"url_path": k, "verdict": v} for k, v in raw.items()]
        site_total = 0
        for i in range(0, len(entries), BATCH_SIZE):
            chunk = entries[i:i + BATCH_SIZE]
            t0 = time.time()
            resp = _post_batch(base, api_key, site, chunk, args.dry_run)
            elapsed = time.time() - t0
            site_total += int(resp.get("inserted", 0))
            err_count = len(resp.get("errors", []))
            err_str = f" · {err_count} errors" if err_count else ""
            print(f"    batch {i//BATCH_SIZE + 1}: {len(chunk)} entries{err_str} in {elapsed:.1f}s")
            if err_count and not args.dry_run:
                for e in resp["errors"][:3]:
                    print(f"      [{e.get('index')}] {e.get('error')}")
        print(f"    Total inserted for {site}: {site_total}")
        grand_total += site_total

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Done · {grand_total} entries written across {len(sites)} site(s)")
    if not args.dry_run:
        print(f"\n  Verifica: curl -s '{base}/v1/crawl-map/stats' | python3 -m json.tool")
    return 0


if __name__ == "__main__":
    sys.exit(main())
