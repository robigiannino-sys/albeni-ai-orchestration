#!/usr/bin/env python3
"""
SEMrush API Helper — Reusable query layer for the semrush-specialist skill.
Integrated with Albeni 1905 AI Orchestration Layer.

Usage:
    from scripts.semrush_api import SEMrushClient, resolve_shared_resources
    client = SEMrushClient(api_key="YOUR_KEY")
    data, err = client.domain_overview("example.com", database="us")

    # Write results to the correct shared-resources path
    shared = resolve_shared_resources()
    save_to_csv(data, os.path.join(shared, "my-export.csv"))
"""

import os
import csv
import io
import json
import requests
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

BASE_URL = "https://api.semrush.com/"

# Database codes for Albeni markets
DATABASES = {
    "US": "us",
    "UK": "uk",
    "DE": "de",
    "IT": "it",
    "FR": "fr",
}

# Keyword matrix CSV columns (canonical schema)
MATRIX_COLUMNS = [
    "Keyword", "Volume US", "Volume UK", "Volume DE", "Volume IT", "Volume FR",
    "Difficulty", "Intent", "Cluster", "Dominio Assegnato", "Funnel Stage",
    "Priorità", "Rischio Cannibalizzazione", "Note", "Source", "Data Aggiornamento",
]


def resolve_shared_resources(workspace: Optional[str] = None) -> str:
    """
    Find the writable shared-resources directory.
    Tries orchestration layer first, then app root, then creates a fallback.
    """
    ws = workspace or os.environ.get("WORKSPACE", "")

    candidates = [
        # Orchestration layer (canonical — other agents read from here)
        os.path.join(ws, "AI STACK APP", "ai-orchestration-layer",
                     "skills-data", "albeni-seo-agent", "shared-resources"),
        # App root fallback
        os.path.join(ws, "AI STACK APP", "shared-resources"),
    ]

    for path in candidates:
        if os.path.isdir(path) and os.access(path, os.W_OK):
            return path

    # Last resort: create in workspace
    fallback = os.path.join(ws or ".", "shared-resources")
    os.makedirs(fallback, exist_ok=True)
    return fallback


def resolve_config_paths(workspace: Optional[str] = None) -> List[str]:
    """Return candidate paths for .semrush-config.json."""
    ws = workspace or os.environ.get("WORKSPACE", "")
    return [
        os.path.join(ws, "AI STACK APP", "shared-resources", ".semrush-config.json"),
        os.path.join(ws, "AI STACK APP", "ai-orchestration-layer", ".env"),
        os.path.join(resolve_shared_resources(ws), ".semrush-config.json"),
        os.path.expanduser("~/.semrush-config.json"),
    ]


class SEMrushClient:
    def __init__(self, api_key: Optional[str] = None, workspace: Optional[str] = None):
        self.workspace = workspace
        self.api_key = api_key or os.environ.get("SEMRUSH_API_KEY")
        if not self.api_key:
            for path in resolve_config_paths(workspace):
                if os.path.exists(path) and path.endswith(".json"):
                    try:
                        with open(path) as f:
                            self.api_key = json.load(f).get("api_key")
                        if self.api_key:
                            break
                    except (json.JSONDecodeError, IOError):
                        continue
        if not self.api_key:
            raise ValueError(
                "No SEMrush API key found. Set SEMRUSH_API_KEY env var, "
                "provide it in shared-resources/.semrush-config.json, "
                "or pass api_key= to the constructor."
            )
        self._cache: Dict[str, Any] = {}
        self._shared_resources = resolve_shared_resources(workspace)

    @property
    def shared_resources_path(self) -> str:
        """Return the resolved writable shared-resources directory."""
        return self._shared_resources

    def _query(self, params: Dict[str, str]) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Execute a SEMrush API query and return parsed results."""
        params["key"] = self.api_key
        cache_key = json.dumps(sorted(params.items()))
        if cache_key in self._cache:
            return self._cache[cache_key], None

        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
        except requests.RequestException as e:
            return None, f"Request failed: {e}"

        if resp.status_code != 200:
            return None, f"API Error {resp.status_code}: {resp.text.strip()}"

        text = resp.text.strip()
        if not text or text.startswith("ERROR"):
            return None, f"SEMrush error: {text}"

        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        data = list(reader)
        self._cache[cache_key] = data
        return data, None

    # ── Domain Analytics ──────────────────────────────────────────

    def domain_overview(self, domain: str, database: str = "us") -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get domain overview: traffic, keywords, authority score."""
        return self._query({
            "type": "domain_ranks",
            "domain": domain,
            "database": database,
        })

    def domain_organic_keywords(self, domain: str, database: str = "us",
                                 limit: int = 100) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get organic keywords for a domain."""
        return self._query({
            "type": "domain_organic",
            "domain": domain,
            "database": database,
            "display_limit": str(limit),
        })

    def domain_paid_keywords(self, domain: str, database: str = "us",
                              limit: int = 100) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get paid keywords for a domain."""
        return self._query({
            "type": "domain_adwords",
            "domain": domain,
            "database": database,
            "display_limit": str(limit),
        })

    def domain_organic_competitors(self, domain: str, database: str = "us",
                                    limit: int = 20) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get organic competitors for a domain."""
        return self._query({
            "type": "domain_organic_organic",
            "domain": domain,
            "database": database,
            "display_limit": str(limit),
        })

    def domain_paid_competitors(self, domain: str, database: str = "us",
                                 limit: int = 20) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get paid competitors for a domain."""
        return self._query({
            "type": "domain_adwords_adwords",
            "domain": domain,
            "database": database,
            "display_limit": str(limit),
        })

    # ── Backlink Analytics ────────────────────────────────────────

    def backlinks_overview(self, domain: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get backlinks overview for a domain."""
        return self._query({
            "type": "backlinks_overview",
            "target": domain,
        })

    def backlinks(self, target: str, limit: int = 100) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get backlinks for a URL or domain."""
        return self._query({
            "type": "backlinks",
            "target": target,
            "display_limit": str(limit),
        })

    # ── Keyword Analytics ─────────────────────────────────────────

    def keyword_overview(self, keyword: str, database: str = "us") -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get keyword overview: volume, CPC, competition, KD."""
        return self._query({
            "type": "phrase_all",
            "phrase": keyword,
            "database": database,
        })

    def keyword_related(self, keyword: str, database: str = "us",
                         limit: int = 50) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get related keywords."""
        return self._query({
            "type": "phrase_related",
            "phrase": keyword,
            "database": database,
            "display_limit": str(limit),
        })

    def keyword_difficulty(self, keyword: str, database: str = "us") -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get keyword difficulty index."""
        return self._query({
            "type": "phrase_kdi",
            "phrase": keyword,
            "database": database,
        })

    def keyword_serp(self, keyword: str, database: str = "us",
                      limit: int = 10) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get organic SERP results for a keyword."""
        return self._query({
            "type": "phrase_organic",
            "phrase": keyword,
            "database": database,
            "display_limit": str(limit),
        })

    # ── URL Analytics ─────────────────────────────────────────────

    def url_organic_keywords(self, url: str, database: str = "us",
                              limit: int = 100) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """Get organic keywords for a specific URL."""
        return self._query({
            "type": "url_organic",
            "url": url,
            "database": database,
            "display_limit": str(limit),
        })

    # ── Multi-Market Helpers ──────────────────────────────────────

    def cross_market_overview(self, domain: str) -> Dict[str, Any]:
        """Run domain overview across all 5 Albeni markets."""
        results = {}
        for market, db in DATABASES.items():
            data, err = self.domain_overview(domain, database=db)
            results[market] = {"data": data, "error": err}
        return results

    def keyword_gap(self, domain: str, competitors: List[str],
                     database: str = "us", limit: int = 200) -> Dict[str, Any]:
        """
        Find keywords competitors rank for but the target domain doesn't.
        Queries organic keywords for each domain and computes the gap.
        """
        target_data, err = self.domain_organic_keywords(domain, database, limit)
        if err:
            return {"error": f"Failed to get target keywords: {err}"}

        target_kws = set()
        if target_data:
            for row in target_data:
                kw = row.get("Keyword") or row.get("keyword") or ""
                if kw:
                    target_kws.add(kw.lower())

        gap = {}
        for comp in competitors:
            comp_data, comp_err = self.domain_organic_keywords(comp, database, limit)
            if comp_err or not comp_data:
                continue
            for row in comp_data:
                kw = row.get("Keyword") or row.get("keyword") or ""
                if kw and kw.lower() not in target_kws:
                    if kw.lower() not in gap:
                        gap[kw.lower()] = {
                            "keyword": kw,
                            "found_in": [],
                            **{k: v for k, v in row.items() if k.lower() != "keyword"},
                        }
                    gap[kw.lower()]["found_in"].append(comp)

        sorted_gap = sorted(gap.values(), key=lambda x: len(x["found_in"]), reverse=True)
        return {"gap_keywords": sorted_gap, "target_keywords_count": len(target_kws)}

    # ── Keyword Matrix Management ─────────────────────────────────

    def load_keyword_matrix(self) -> List[Dict]:
        """Load the current keyword-matrix.csv from shared-resources."""
        matrix_path = os.path.join(self._shared_resources, "keyword-matrix.csv")
        if not os.path.exists(matrix_path):
            return []
        with open(matrix_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def save_keyword_matrix(self, rows: List[Dict]) -> str:
        """Save keyword-matrix.csv to the writable shared-resources directory."""
        matrix_path = os.path.join(self._shared_resources, "keyword-matrix.csv")
        if not rows:
            return "No data to save"
        with open(matrix_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MATRIX_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return f"Saved {len(rows)} keywords to {matrix_path}"

    def append_to_keyword_matrix(self, new_keywords: List[Dict]) -> str:
        """
        Append new keywords to the matrix, avoiding duplicates.
        Returns summary of what was added.
        """
        existing = self.load_keyword_matrix()
        existing_kws = {row.get("Keyword", "").strip('"').lower() for row in existing}

        added = 0
        for kw in new_keywords:
            kw_text = kw.get("Keyword", "").strip('"').lower()
            if kw_text and kw_text not in existing_kws:
                # Set defaults
                kw.setdefault("Source", "SEMrush API")
                kw.setdefault("Data Aggiornamento", datetime.now().strftime("%Y-%m-%d"))
                existing.append(kw)
                existing_kws.add(kw_text)
                added += 1

        result = self.save_keyword_matrix(existing)
        return f"Added {added} new keywords (skipped {len(new_keywords) - added} duplicates). {result}"


def save_to_csv(data: List[Dict], filepath: str) -> str:
    """Save a list of dicts to CSV."""
    if not data:
        return "No data to save"
    fieldnames = list(data[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    return f"Saved {len(data)} rows to {filepath}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python semrush_api.py <command> [args...]")
        print("Commands: overview, organic, paid, competitors, keyword, related, gap, matrix-info")
        sys.exit(1)

    cmd = sys.argv[1]

    # Special command: show matrix info without API key
    if cmd == "matrix-info":
        shared = resolve_shared_resources()
        matrix_path = os.path.join(shared, "keyword-matrix.csv")
        print(f"Shared resources path: {shared}")
        print(f"Keyword matrix path: {matrix_path}")
        print(f"Matrix exists: {os.path.exists(matrix_path)}")
        if os.path.exists(matrix_path):
            with open(matrix_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            print(f"Total keywords: {len(rows)}")
            clusters = {}
            for r in rows:
                c = r.get("Cluster", "unknown")
                clusters[c] = clusters.get(c, 0) + 1
            print("By cluster:")
            for c, n in sorted(clusters.items()):
                print(f"  {c}: {n}")
        sys.exit(0)

    if len(sys.argv) < 3:
        print("Usage: python semrush_api.py <command> <domain_or_keyword> [database]")
        sys.exit(1)

    target = sys.argv[2]
    db = sys.argv[3] if len(sys.argv) > 3 else "us"

    client = SEMrushClient()

    commands = {
        "overview": lambda: client.domain_overview(target, db),
        "organic": lambda: client.domain_organic_keywords(target, db),
        "paid": lambda: client.domain_paid_keywords(target, db),
        "competitors": lambda: client.domain_organic_competitors(target, db),
        "keyword": lambda: client.keyword_overview(target, db),
        "related": lambda: client.keyword_related(target, db),
    }

    if cmd in commands:
        data, error = commands[cmd]()
        if error:
            print(f"Error: {error}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
