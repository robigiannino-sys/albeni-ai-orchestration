#!/usr/bin/env python3
"""
Standalone CLI to trigger a pipeline backfill on the live ml-worker.
Albeni 1905 — added 2026-05-06.

Usage:
    # On Roberto's Mac, from the repo root:
    python3 scripts/recompute_pipeline.py

The script reads ML_WORKER_URL and API_KEY from .env (or env vars) and
hits the /v1/admin/recompute-pipeline endpoint. Equivalent to running
the APScheduler job manually.

Defaults:
    ML_WORKER_URL = https://albeni-ai-orchestration-production.up.railway.app
"""
import os
import sys
import json
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Missing dependency: pip install httpx", file=sys.stderr)
    sys.exit(2)


def _load_env():
    """Best-effort load of repo-root .env so this script works without exporting vars."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    _load_env()
    base = os.environ.get(
        "ML_WORKER_PUBLIC_URL",
        "https://albeni-ai-orchestration-production.up.railway.app",
    ).rstrip("/")
    api_key = os.environ.get("API_KEY")
    if not api_key:
        print("ERROR: API_KEY not set (check .env)", file=sys.stderr)
        sys.exit(2)

    url = f"{base}/v1/admin/recompute-pipeline"
    print(f"POST {url}")
    started = time.time()
    try:
        r = httpx.post(url, headers={"X-Admin-Key": api_key}, timeout=300.0)
    except httpx.RequestError as e:
        print(f"ERROR: request failed: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - started
    print(f"HTTP {r.status_code} in {elapsed:.1f}s")
    try:
        body = r.json()
        print(json.dumps(body, indent=2, default=str))
    except Exception:
        print(r.text)
    if r.status_code != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
