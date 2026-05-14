#!/usr/bin/env python3
"""
Google Ads spend sync — Step 3a Sessione 2.
Pulls daily spend per campaign from Google Ads API (REST) and POSTs to
the ml-worker /v1/adv/spend/batch endpoint.

Albeni 1905 — added 2026-05-14.
Pattern derivato da scripts/recompute_pipeline.py (stessi env helpers e httpx).

Usage:
    # Default: pulla spend di ieri (1 giorno), POSTa al ml-worker
    python3 scripts/google_ads_spend_sync.py

    # Backfill 14 giorni
    python3 scripts/google_ads_spend_sync.py --since 2026-05-01 --until 2026-05-13

    # Dry-run: stampa payload senza POST
    python3 scripts/google_ads_spend_sync.py --dry-run --verbose

    # Customer ID override (es. testing su un altro account)
    python3 scripts/google_ads_spend_sync.py --customer-id 1234567890

Env vars richieste (in .env o esportate):
    GOOGLE_ADS_DEVELOPER_TOKEN
    GOOGLE_ADS_CLIENT_ID
    GOOGLE_ADS_CLIENT_SECRET
    GOOGLE_ADS_REFRESH_TOKEN
    GOOGLE_ADS_CUSTOMER_ID            (es. "1234567890", senza dash)
    GOOGLE_ADS_LOGIN_CUSTOMER_ID      (opzionale, solo se l'account è sotto un MCC manager)
    API_KEY                            (per autenticare al ml-worker: albeni1905-internal-api-v1)
    ML_WORKER_PUBLIC_URL               (default: https://albeni-ai-orchestration-production.up.railway.app)

Setup guide: vedi scripts/GOOGLE_ADS_SETUP.md
"""
import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import httpx
except ImportError:
    print("Missing dependency: pip install httpx", file=sys.stderr)
    sys.exit(2)


# ── Constants ──────────────────────────────────────────────────────────
GOOGLE_OAUTH_TOKEN_URL = "https://www.googleapis.com/oauth2/v3/token"
GOOGLE_ADS_API_VERSION = "v17"   # bump if/when Google deprecates this version
GOOGLE_ADS_REST_BASE = f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}"
DEFAULT_ML_WORKER_URL = "https://albeni-ai-orchestration-production.up.railway.app"

# Country mapping fallback — Albeni opera su 5 mercati (US/UK/DE/IT/FR).
# Google Ads campaign-level country va ricavato da geo_target o naming convention campagna.
# Per ora lasciamo None se non desumibile, l'endpoint /v1/adv/spend/batch accetta country nullable.


# ── Env loader (stesso helper di recompute_pipeline.py) ────────────────
def _load_env() -> None:
    """Best-effort load of repo-root .env so script works without exporting vars."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _require_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"ERROR: {key} not set (check .env)", file=sys.stderr)
        sys.exit(2)
    return val


# ── Google OAuth2: refresh → access token ──────────────────────────────
def get_access_token(client_id: str, client_secret: str, refresh_token: str, verbose: bool = False) -> str:
    """
    Scambia il refresh_token per un access_token short-lived (1 ora).
    Lo facciamo a ogni run perché il sync è batch (1×/giorno) — niente caching.
    """
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if verbose:
        print(f"  → OAuth refresh: POST {GOOGLE_OAUTH_TOKEN_URL}")
    r = httpx.post(GOOGLE_OAUTH_TOKEN_URL, data=payload, timeout=30.0)
    if r.status_code != 200:
        print(f"ERROR: OAuth refresh failed: HTTP {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)
    body = r.json()
    token = body.get("access_token")
    if not token:
        print(f"ERROR: no access_token in response: {body}", file=sys.stderr)
        sys.exit(1)
    if verbose:
        print(f"  ← access_token OK (expires in {body.get('expires_in', '?')}s)")
    return token


# ── Google Ads GAQL query ──────────────────────────────────────────────
def build_gaql(date_from: date, date_to: date) -> str:
    """
    Pull daily spend + impressions + clicks per campaign, segmentato per giorno.
    BETWEEN è inclusivo su entrambi gli estremi.
    Escludiamo campagne REMOVED (cancellate definitivamente) ma teniamo PAUSED — paused può comunque
    aver speso nel periodo richiesto.
    """
    return f"""
        SELECT
            segments.date,
            campaign.id,
            campaign.name,
            campaign.advertising_channel_type,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks
        FROM campaign
        WHERE segments.date BETWEEN '{date_from.isoformat()}' AND '{date_to.isoformat()}'
          AND campaign.status != 'REMOVED'
        ORDER BY segments.date DESC, metrics.cost_micros DESC
    """.strip()


# ── Google Ads REST search ─────────────────────────────────────────────
def fetch_customer_currency(customer_id: str, dev_token: str, login_customer_id: Optional[str],
                             access_token: str, verbose: bool = False) -> str:
    """
    Customer-level currency. Lo leggiamo una sola volta per run per sapere
    se cost_micros è in EUR (caso Albeni) o un'altra valuta.
    """
    url = f"{GOOGLE_ADS_REST_BASE}/customers/{customer_id}/googleAds:search"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": dev_token,
        "Content-Type": "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id
    body = {"query": "SELECT customer.currency_code FROM customer LIMIT 1"}
    r = httpx.post(url, headers=headers, json=body, timeout=30.0)
    if r.status_code != 200:
        print(f"  ⚠ customer currency fetch failed (HTTP {r.status_code}): {r.text[:200]}", file=sys.stderr)
        print(f"  ⚠ falling back to EUR (assumed for Albeni)", file=sys.stderr)
        return "EUR"
    rows = r.json().get("results", [])
    if not rows:
        return "EUR"
    cur = rows[0].get("customer", {}).get("currencyCode", "EUR")
    if verbose:
        print(f"  ← customer currency: {cur}")
    return cur


def fetch_spend(customer_id: str, dev_token: str, login_customer_id: Optional[str],
                access_token: str, gaql: str, verbose: bool = False) -> List[Dict]:
    """
    Lancia la GAQL search. La REST paginazione di Google Ads usa nextPageToken
    ma per finestre brevi (<=30 giorni × tipiche 5-50 campagne) entra in 1 sola pagina.
    Gestiamo comunque la paginazione se serve.
    """
    url = f"{GOOGLE_ADS_REST_BASE}/customers/{customer_id}/googleAds:search"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": dev_token,
        "Content-Type": "application/json",
    }
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id

    all_results: List[Dict] = []
    page_token: Optional[str] = None
    page_num = 0
    while True:
        page_num += 1
        body = {"query": gaql, "pageSize": 1000}
        if page_token:
            body["pageToken"] = page_token
        if verbose:
            print(f"  → page {page_num}: POST {url}")
        r = httpx.post(url, headers=headers, json=body, timeout=60.0)
        if r.status_code != 200:
            print(f"ERROR: Google Ads search failed: HTTP {r.status_code}", file=sys.stderr)
            print(f"  body: {r.text[:500]}", file=sys.stderr)
            sys.exit(1)
        data = r.json()
        results = data.get("results", [])
        all_results.extend(results)
        page_token = data.get("nextPageToken")
        if verbose:
            print(f"  ← page {page_num}: {len(results)} rows (nextPageToken: {'yes' if page_token else 'no'})")
        if not page_token:
            break
        if page_num > 50:  # safety brake
            print("WARNING: stopped paginating at page 50", file=sys.stderr)
            break
    return all_results


# ── Transform Google Ads response → /v1/adv/spend/batch payload ────────
def to_batch_payload(rows: List[Dict], currency: str) -> List[Dict]:
    """
    Map Google Ads search response → schema atteso da /v1/adv/spend/batch.
    cost_micros è in micro-unità della valuta customer: amount = micros / 1_000_000.
    Per Albeni il customer è EUR, quindi amount_eur = amount.
    Se in futuro qualcuno aggiunge un customer non-EUR, va aggiunta una conversion FX qui.
    """
    out: List[Dict] = []
    for row in rows:
        segments = row.get("segments", {})
        campaign = row.get("campaign", {})
        metrics = row.get("metrics", {})
        date_str = segments.get("date")  # 'YYYY-MM-DD'
        if not date_str:
            continue
        cost_micros = int(metrics.get("costMicros", 0))
        amount = cost_micros / 1_000_000.0
        if amount <= 0:
            # Skip righe a costo zero: occupano spazio inutilmente nella tabella.
            # Se in futuro vuoi tenerle (per audit "campagna live ma zero spesa") togli il continue.
            continue
        # amount_eur = amount se currency == EUR, altrimenti per ora lasciamo amount in EUR pari al raw
        # e segnaliamo currency originale (l'endpoint accetta amount_original per audit).
        amount_eur = amount  # FX conversion non implementata — TODO se serve multi-currency
        out.append({
            "channel": "google_ads",
            "date": date_str,
            "campaign_id": str(campaign.get("id", "")),
            "campaign_name": campaign.get("name") or None,
            "amount_eur": round(amount_eur, 2),
            "amount_original": round(amount, 2) if currency != "EUR" else None,
            "currency": currency,
            "impressions": int(metrics.get("impressions", 0)) or None,
            "clicks": int(metrics.get("clicks", 0)) or None,
            "source": "google_ads_sync",
            # country: non determinabile da campaign senza pull aggiuntivo su geo_target_constants.
            # Lasciamo None — endpoint lo accetta.
        })
    return out


# ── POST batch al ml-worker ────────────────────────────────────────────
def post_batch(base_url: str, api_key: str, rows: List[Dict], verbose: bool = False) -> Dict:
    url = f"{base_url.rstrip('/')}/v1/adv/spend/batch"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    if verbose:
        print(f"  → POST {url} ({len(rows)} rows)")
    r = httpx.post(url, headers=headers, json={"rows": rows}, timeout=120.0)
    if r.status_code not in (200, 207):
        print(f"ERROR: ml-worker batch POST failed: HTTP {r.status_code}", file=sys.stderr)
        print(f"  body: {r.text[:500]}", file=sys.stderr)
        sys.exit(1)
    body = r.json()
    if verbose:
        print(f"  ← {body.get('status')}: inserted={body.get('inserted')} errors={len(body.get('errors', []))}")
    return body


# ── CLI ────────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    yesterday = (datetime.utcnow().date() - timedelta(days=1))
    ap = argparse.ArgumentParser(description="Google Ads spend sync → ml-worker")
    ap.add_argument("--since", type=str, default=yesterday.isoformat(),
                    help="Start date (YYYY-MM-DD), default: yesterday")
    ap.add_argument("--until", type=str, default=yesterday.isoformat(),
                    help="End date (YYYY-MM-DD), inclusive, default: yesterday")
    ap.add_argument("--customer-id", type=str, default=None,
                    help="Override GOOGLE_ADS_CUSTOMER_ID env var")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip POST to ml-worker, print payload preview")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Verbose logging (OAuth, pagination, payload)")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    _load_env()

    # ── Validate dates ──
    try:
        date_from = datetime.strptime(args.since, "%Y-%m-%d").date()
        date_to = datetime.strptime(args.until, "%Y-%m-%d").date()
    except ValueError as e:
        print(f"ERROR: invalid date format: {e}", file=sys.stderr)
        return 2
    if date_from > date_to:
        print(f"ERROR: --since {date_from} > --until {date_to}", file=sys.stderr)
        return 2
    span = (date_to - date_from).days + 1

    # ── Read credentials ──
    customer_id = (args.customer_id or _require_env("GOOGLE_ADS_CUSTOMER_ID")).replace("-", "")
    dev_token = _require_env("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = _require_env("GOOGLE_ADS_CLIENT_ID")
    client_secret = _require_env("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = _require_env("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "") or None
    api_key = _require_env("API_KEY")
    base_url = os.environ.get("ML_WORKER_PUBLIC_URL", DEFAULT_ML_WORKER_URL)

    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Google Ads spend sync")
    print(f"  Window:  {date_from} → {date_to} ({span} day{'s' if span != 1 else ''})")
    print(f"  Customer: {customer_id}" + (f" (under MCC {login_customer_id})" if login_customer_id else ""))
    print(f"  Target:   {base_url}/v1/adv/spend/batch")
    print(f"  Mode:     {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ── OAuth + fetch ──
    t0 = time.time()
    access_token = get_access_token(client_id, client_secret, refresh_token, verbose=args.verbose)

    currency = fetch_customer_currency(customer_id, dev_token, login_customer_id, access_token,
                                        verbose=args.verbose)
    if currency != "EUR":
        print(f"  ⚠ customer currency = {currency} (non-EUR). amount_eur sarà lo stesso valore di amount_original — "
              f"aggiungere FX conversion se servono CPA accurati.", file=sys.stderr)

    gaql = build_gaql(date_from, date_to)
    if args.verbose:
        print(f"  GAQL:\n{gaql}\n")

    rows = fetch_spend(customer_id, dev_token, login_customer_id, access_token, gaql, verbose=args.verbose)
    fetch_elapsed = time.time() - t0
    print(f"  Fetched: {len(rows)} raw rows in {fetch_elapsed:.1f}s")

    payload = to_batch_payload(rows, currency)
    skipped = len(rows) - len(payload)
    print(f"  Payload: {len(payload)} rows (skipped {skipped} zero-cost rows)")

    if args.verbose and payload:
        print(f"  Sample payload row:\n{json.dumps(payload[0], indent=4)}")

    if not payload:
        print(f"  ⚠ no spend rows in the window — nothing to POST")
        return 0

    # Aggregate stats per il log
    total_spend = sum(r["amount_eur"] for r in payload)
    by_day: Dict[str, float] = {}
    for r in payload:
        by_day[r["date"]] = by_day.get(r["date"], 0) + r["amount_eur"]
    print(f"  Total spend in window: €{total_spend:.2f}")
    if len(by_day) <= 10 or args.verbose:
        for d in sorted(by_day):
            print(f"    {d}  €{by_day[d]:8.2f}")

    # ── POST ──
    if args.dry_run:
        print(f"\n  DRY-RUN: skipping POST. Re-run without --dry-run to ingest.")
        return 0

    resp = post_batch(base_url, api_key, payload, verbose=args.verbose)
    print(f"  ← ingest: inserted={resp.get('inserted')} errors={len(resp.get('errors', []))} "
          f"total_rows_db={resp.get('total_rows')}")
    if resp.get("errors"):
        print(f"  ⚠ errors (first 3):")
        for e in resp["errors"][:3]:
            print(f"    [{e.get('index')}] {e.get('error')}")
    elapsed = time.time() - t0
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Done in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
