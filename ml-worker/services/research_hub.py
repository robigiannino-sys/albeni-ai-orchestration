"""
Research Data Hub - AI Orchestration Layer
Albeni 1905 - Invisible Luxury Ecosystem

Universal data import, storage and query engine.
Accepts ANY data file to power AI agents with research intelligence.

Supported sources (auto-detected):
- Semrush (all export types)
- Google Analytics 4 (GA4 exports)
- Google Ads (campaign, keyword, ad group exports)
- Google Search Console (performance, queries, pages)
- Ahrefs (keyword, backlink, organic exports)
- Screaming Frog (crawl exports)
- Shopify (orders, products, analytics)
- Klaviyo (campaign reports, list exports)
- Custom CSV/XLSX (any tabular data)
- PDF documents (strategy docs, briefs, reports — text extracted)
- DOCX documents (strategy docs, briefs, analyses — text extracted)
- TXT/JSON files (raw data, configs, notes)
"""

import csv
import io
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from config import get_settings
from services.semrush_data_library import SemrushDataLibrary

logger = logging.getLogger(__name__)
settings = get_settings()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "research_hub")


class ResearchHub:
    """
    Universal Research Data Hub for the Albeni 1905 AI Orchestration Layer.
    Imports, indexes, and serves data from any source.
    """

    # Source detection signatures (column headers → source type)
    SOURCE_SIGNATURES = {
        # Semrush
        "semrush": {
            "columns": ["Keyword", "Volume", "Keyword Difficulty", "CPC", "Position", "Nq", "Ph", "Po", "Kd%",
                         "Search Volume", "Number of Results", "Trend", "SERP Features", "Keyword Intents",
                         "Results", "Keyword Intent"],
            "filename_hints": ["semrush", "keyword_overview", "organic_research", "domain_analytics",
                               "broad-match", "exact-match", "related-keywords", "all-keywords",
                               "keyword_magic", "keyword-magic", "bulk", "position_tracking"],
        },
        # Google Analytics 4
        "google_analytics": {
            "columns": ["Sessions", "Users", "New Users", "Bounce Rate", "Session Duration", "Page path", "Event name", "Active Users", "Engaged sessions", "Event count"],
            "filename_hints": ["ga4", "google_analytics", "analytics", "audience"],
        },
        # Google Ads
        "google_ads": {
            "columns": ["Campaign", "Ad group", "Impressions", "Clicks", "CTR", "Avg. CPC", "Cost", "Conversions", "Conv. rate", "Quality Score"],
            "filename_hints": ["google_ads", "adwords", "campaign_report", "search_terms"],
        },
        # Google Search Console
        "search_console": {
            "columns": ["Query", "Clicks", "Impressions", "CTR", "Position", "Page", "Top queries", "Top pages"],
            "filename_hints": ["search_console", "gsc", "webmaster", "search_analytics"],
        },
        # Ahrefs
        "ahrefs": {
            "columns": ["Keyword", "Volume", "Keyword Difficulty", "CPC", "Parent Topic", "DR", "UR", "Referring domains", "Backlinks"],
            "filename_hints": ["ahrefs", "site_explorer", "content_explorer"],
        },
        # Screaming Frog
        "screaming_frog": {
            "columns": ["Address", "Status Code", "Title 1", "Meta Description 1", "H1-1", "Word Count", "Crawl Depth", "Response Time"],
            "filename_hints": ["screaming_frog", "crawl", "internal_all"],
        },
        # Shopify
        "shopify": {
            "columns": ["Order", "Product", "SKU", "Variant", "Quantity", "Lineitem price", "Total", "Discount Code", "Shipping"],
            "filename_hints": ["shopify", "orders_export", "products_export"],
        },
        # Klaviyo
        "klaviyo": {
            "columns": ["Campaign Name", "Open Rate", "Click Rate", "Unsubscribe Rate", "Bounce Rate", "Revenue", "Delivered"],
            "filename_hints": ["klaviyo", "campaign_report", "flow_report", "list_export"],
        },
    }

    # Category mapping for UI grouping
    CATEGORIES = {
        "semrush": {"label": "Semrush", "icon": "📈", "color": "#f97316"},
        "google_analytics": {"label": "Google Analytics", "icon": "📊", "color": "#4285f4"},
        "google_ads": {"label": "Google Ads", "icon": "💰", "color": "#34a853"},
        "search_console": {"label": "Search Console", "icon": "🔎", "color": "#ea4335"},
        "ahrefs": {"label": "Ahrefs", "icon": "🔗", "color": "#ff8c00"},
        "screaming_frog": {"label": "Screaming Frog", "icon": "🐸", "color": "#78c832"},
        "shopify": {"label": "Shopify", "icon": "🛍️", "color": "#96bf48"},
        "klaviyo": {"label": "Klaviyo", "icon": "📧", "color": "#00b67a"},
        "pdf_document": {"label": "Documento PDF", "icon": "📄", "color": "#dc2626"},
        "docx_document": {"label": "Documento Word", "icon": "📝", "color": "#2b579a"},
        "skill": {"label": "AI Skill", "icon": "🧠", "color": "#8b5cf6"},
        "text_file": {"label": "File Testo", "icon": "📋", "color": "#71717a"},
        "json_file": {"label": "File JSON", "icon": "🔧", "color": "#52525b"},
        "custom_data": {"label": "Dati Custom", "icon": "📂", "color": "#a1a1aa"},
    }

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._index = self._load_index()
        # Also keep backward compatibility with Semrush-only library
        self._semrush_lib = SemrushDataLibrary()

    def _index_path(self) -> str:
        return os.path.join(DATA_DIR, "_hub_index.json")

    def _load_index(self) -> List[Dict]:
        path = self._index_path()
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return []

    def _save_index(self):
        with open(self._index_path(), "w") as f:
            json.dump(self._index, f, indent=2, default=str)

    # ================================================================
    # SOURCE DETECTION
    # ================================================================

    def detect_source(self, headers: List[str], filename: str) -> str:
        """Auto-detect data source from column headers and filename."""
        filename_lower = filename.lower()
        header_lower = [h.strip().strip('"').lower() for h in headers if h]

        best_source = "custom_data"
        best_score = 0

        for source, sig in self.SOURCE_SIGNATURES.items():
            score = 0
            # Column match
            for col in sig["columns"]:
                if col.lower() in header_lower:
                    score += 2
            # Filename hint match
            for hint in sig["filename_hints"]:
                if hint in filename_lower:
                    score += 3
            if score > best_score:
                best_score = score
                best_source = source

        return best_source if best_score >= 2 else "custom_data"

    def detect_file_type(self, filename: str) -> str:
        """Detect if file is tabular data or a document."""
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if ext in ("csv", "tsv", "xlsx", "xls"):
            return "tabular"
        elif ext == "pdf":
            return "pdf_document"
        elif ext in ("docx", "doc"):
            return "docx_document"
        elif ext == "json":
            return "json_file"
        elif ext in ("txt", "md"):
            return "text_file"
        return "tabular"  # default assumption

    # ================================================================
    # IMPORT
    # ================================================================

    def import_tabular(self, content: str, filename: str, delimiter: str = None) -> Tuple[str, List[Dict]]:
        """Parse CSV/TSV tabular data. Handles Semrush/GA metadata rows."""
        if not content or not content.strip():
            raise ValueError("Il file è vuoto")

        if delimiter is None:
            # Auto-detect from first 2000 chars
            sample = content[:2000]
            if sample.count("\t") > sample.count(";") and sample.count("\t") > sample.count(","):
                delimiter = "\t"
            elif sample.count(";") > sample.count(","):
                delimiter = ";"
            else:
                delimiter = ","

        lines = content.strip().split("\n")

        # Skip metadata rows (Semrush/GA often have 1-5 metadata rows before headers)
        header_idx = 0
        for i, line in enumerate(lines[:15]):
            cols = line.split(delimiter)
            non_empty = [c.strip().strip('"') for c in cols if c.strip().strip('"')]
            if len(non_empty) >= 3:
                # Check it's not a single long string split by accident
                first_val = cols[0].strip().strip('"') if cols else ""
                if not first_val.startswith("http") and len(non_empty) >= 3:
                    header_idx = i
                    break

        clean = "\n".join(lines[header_idx:])
        try:
            reader = csv.DictReader(io.StringIO(clean), delimiter=delimiter)
            raw_headers = reader.fieldnames or []
        except Exception as e:
            logger.error(f"CSV parse error for '{filename}': {e}")
            raise ValueError(f"Errore parsing CSV: {e}")

        if not raw_headers:
            raise ValueError("Nessuna intestazione trovata nel file")

        rows = []
        for row_num, row in enumerate(reader):
            try:
                cleaned = {}
                for k, v in row.items():
                    if k is None:
                        continue
                    key = k.strip().strip('"')
                    if not key:
                        continue
                    val = v.strip().strip('"') if v else ""
                    # Try numeric conversion
                    if val:
                        try:
                            # Handle percentages and comma-as-decimal
                            clean_val = val.replace("%", "").replace(",", ".").strip()
                            if "." in clean_val:
                                cleaned[key] = float(clean_val)
                            else:
                                cleaned[key] = int(clean_val)
                        except (ValueError, OverflowError):
                            cleaned[key] = val
                    else:
                        cleaned[key] = val
                if any(v != "" for v in cleaned.values()):
                    rows.append(cleaned)
            except Exception as e:
                logger.warning(f"Skipping row {row_num} in '{filename}': {e}")
                continue

        source = self.detect_source(raw_headers, filename)
        logger.info(f"CSV parsed: '{filename}' → {len(rows)} rows, {len(raw_headers)} cols, header at line {header_idx}, source={source}")
        return source, rows

    def import_xlsx(self, file_bytes: bytes, filename: str) -> Tuple[str, List[Dict]]:
        """Parse XLSX file. Handles Semrush metadata rows, empty sheets, etc."""
        try:
            import openpyxl
        except ImportError:
            import subprocess
            subprocess.check_call(["pip", "install", "openpyxl", "--break-system-packages", "-q"])
            import openpyxl

        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        except Exception as e:
            logger.error(f"Cannot open XLSX '{filename}': {e}")
            raise ValueError(f"File XLSX non leggibile: {e}")

        ws = wb.active
        if ws is None:
            wb.close()
            raise ValueError("Il file XLSX non contiene fogli attivi")

        # Read all rows into memory (safer for read_only mode)
        all_rows = []
        try:
            for row in ws.iter_rows(values_only=True):
                all_rows.append(row)
        except Exception as e:
            logger.warning(f"Error reading XLSX rows for '{filename}': {e}")
        finally:
            wb.close()

        if not all_rows:
            raise ValueError("Il file XLSX è vuoto")

        # Find the header row: skip metadata rows (Semrush often has 1-5 metadata rows)
        # Header row = first row with 3+ non-empty cells that look like column names
        header_idx = 0
        for idx, row in enumerate(all_rows[:15]):  # Check first 15 rows
            non_empty = [c for c in row if c is not None and str(c).strip()]
            if len(non_empty) >= 3:
                # Check it's not a metadata row (single long string in first cell)
                first_val = str(row[0]).strip() if row[0] else ""
                if len(non_empty) >= 3 and not first_val.startswith("http") and ";" not in first_val:
                    header_idx = idx
                    break

        header_row = all_rows[header_idx]
        headers = []
        for i, c in enumerate(header_row):
            if c is not None and str(c).strip():
                headers.append(str(c).strip())
            else:
                headers.append(f"col_{i}")

        # Parse data rows (everything after header)
        rows = []
        for row in all_rows[header_idx + 1:]:
            if row is None:
                continue
            # Skip completely empty rows
            if all(c is None or (isinstance(c, str) and not c.strip()) for c in row):
                continue
            cleaned = {}
            for i, val in enumerate(row):
                if i >= len(headers):
                    break
                key = headers[i]
                try:
                    if val is None:
                        cleaned[key] = ""
                    elif isinstance(val, (int, float)):
                        cleaned[key] = val
                    else:
                        cleaned[key] = str(val).strip()
                except Exception:
                    cleaned[key] = ""
            if any(v != "" for v in cleaned.values()):
                rows.append(cleaned)

        source = self.detect_source(headers, filename)
        logger.info(f"XLSX parsed: '{filename}' → {len(rows)} rows, {len(headers)} cols, header at row {header_idx}, source={source}")
        return source, rows

    def import_pdf(self, file_bytes: bytes, filename: str) -> Tuple[str, List[Dict]]:
        """Extract text from PDF and store as searchable document."""
        try:
            import subprocess
            # Use pdftotext if available, else fall back to simple extraction
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                result = subprocess.run(
                    ["pdftotext", "-layout", tmp_path, "-"],
                    capture_output=True, text=True, timeout=30
                )
                text = result.stdout
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # Fallback: basic extraction
                text = f"[PDF file: {filename} — {len(file_bytes)} bytes. Full text extraction requires pdftotext.]"
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            text = f"[PDF extraction error: {str(e)}]"

        # Split into paragraphs for indexing
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        rows = [{"paragraph_id": i + 1, "text": p, "word_count": len(p.split())} for i, p in enumerate(paragraphs)]

        return "pdf_document", rows

    def import_docx(self, file_bytes: bytes, filename: str) -> Tuple[str, List[Dict]]:
        """Extract text from DOCX."""
        try:
            import zipfile
            import xml.etree.ElementTree as ET

            docx = zipfile.ZipFile(io.BytesIO(file_bytes))
            xml_content = docx.read("word/document.xml")
            tree = ET.fromstring(xml_content)

            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = []
            for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                texts = [t.text for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if t.text]
                full = "".join(texts).strip()
                if full:
                    paragraphs.append(full)
            docx.close()

        except Exception as e:
            paragraphs = [f"[DOCX extraction error: {str(e)}]"]

        rows = [{"paragraph_id": i + 1, "text": p, "word_count": len(p.split())} for i, p in enumerate(paragraphs)]
        return "docx_document", rows

    def import_json_file(self, content: str, filename: str) -> Tuple[str, List[Dict]]:
        """Import JSON file."""
        try:
            data = json.loads(content)
            if isinstance(data, list):
                rows = data if all(isinstance(r, dict) for r in data) else [{"value": r} for r in data]
            elif isinstance(data, dict):
                rows = [data]
            else:
                rows = [{"value": data}]
        except json.JSONDecodeError:
            rows = [{"raw_content": content}]
        return "json_file", rows

    def import_text(self, content: str, filename: str) -> Tuple[str, List[Dict]]:
        """Import plain text/markdown."""
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [l.strip() for l in content.split("\n") if l.strip()]
        rows = [{"line_id": i + 1, "text": p, "word_count": len(p.split())} for i, p in enumerate(paragraphs)]
        return "text_file", rows

    # ================================================================
    # UNIVERSAL IMPORT ENTRY POINT
    # ================================================================

    def import_file(self, file_bytes: bytes, filename: str, source_override: str = "", label: str = "", notes: str = "") -> Dict:
        """
        Universal file import. Auto-detects type and source.
        Supports: CSV, XLSX, PDF, DOCX, JSON, TXT, MD, TSV
        """
        file_type = self.detect_file_type(filename)
        logger.info(f"Importing file: '{filename}' (type={file_type}, size={len(file_bytes)} bytes)")

        try:
            if file_type == "tabular":
                ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
                if ext in ("xlsx", "xls"):
                    source, rows = self.import_xlsx(file_bytes, filename)
                else:
                    content = file_bytes.decode("utf-8", errors="replace")
                    source, rows = self.import_tabular(content, filename)
            elif file_type == "pdf_document":
                source, rows = self.import_pdf(file_bytes, filename)
            elif file_type == "docx_document":
                source, rows = self.import_docx(file_bytes, filename)
            elif file_type == "json_file":
                content = file_bytes.decode("utf-8", errors="replace")
                source, rows = self.import_json_file(content, filename)
            else:
                content = file_bytes.decode("utf-8", errors="replace")
                source, rows = self.import_text(content, filename)
        except ValueError:
            raise  # Re-raise ValueError with user-friendly messages
        except Exception as e:
            logger.error(f"Unexpected error importing '{filename}': {e}", exc_info=True)
            raise ValueError(f"Errore inaspettato durante l'import di '{filename}': {str(e)}")

        if not rows:
            logger.warning(f"File '{filename}' parsed but produced 0 rows")
            raise ValueError(f"Il file '{filename}' non contiene dati riconoscibili dopo il parsing")

        # Allow manual source override
        if source_override:
            source = source_override

        # Store
        import_id = f"hub_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{len(self._index)}"
        data_path = os.path.join(DATA_DIR, f"{import_id}.json")

        category = self.CATEGORIES.get(source, self.CATEGORIES["custom_data"])
        columns = list(rows[0].keys()) if rows else []

        record = {
            "id": import_id,
            "filename": filename,
            "source": source,
            "category": category["label"],
            "icon": category["icon"],
            "color": category["color"],
            "file_type": file_type,
            "rows_count": len(rows),
            "columns": columns,
            "imported_at": datetime.utcnow().isoformat(),
            "label": label or filename,
            "notes": notes,
            "file_size": len(file_bytes),
            "data_path": data_path,
        }

        # Summary stats
        if rows:
            # Try to extract keyword-related summary
            kw_count = sum(1 for r in rows if any(k.lower() in ("keyword", "query", "search term", "ph") for k in r.keys() if r.get(k)))
            text_count = sum(1 for r in rows if "text" in r)
            record["summary"] = {
                "keyword_rows": kw_count,
                "text_rows": text_count,
                "total_rows": len(rows),
                "columns": columns[:10],
            }

        with open(data_path, "w") as f:
            json.dump({"record": record, "data": rows}, f, default=str)

        self._index.append(record)
        self._save_index()

        logger.info(f"Research Hub imported: {import_id} ({source}, {len(rows)} rows, {filename})")
        return record

    # ================================================================
    # QUERY
    # ================================================================

    def list_all(self, source_filter: str = None) -> List[Dict]:
        """List all imports, optionally filtered by source."""
        results = self._index
        if source_filter:
            results = [r for r in results if r["source"] == source_filter]
        return [{k: v for k, v in r.items() if k != "data_path"} for r in results]

    def get_data(self, import_id: str) -> Optional[Dict]:
        """Get full data for an import."""
        for rec in self._index:
            if rec["id"] == import_id:
                if os.path.exists(rec["data_path"]):
                    with open(rec["data_path"], "r") as f:
                        return json.load(f)
        return None

    def delete(self, import_id: str) -> bool:
        for i, rec in enumerate(self._index):
            if rec["id"] == import_id:
                if os.path.exists(rec["data_path"]):
                    os.remove(rec["data_path"])
                self._index.pop(i)
                self._save_index()
                return True
        return False

    def search(self, query: str, source_filter: str = None) -> List[Dict]:
        """
        Full-text search across ALL imported data.
        Searches keyword fields, text fields, and any string value.
        """
        results = []
        query_lower = query.lower()

        targets = self._index
        if source_filter:
            targets = [r for r in targets if r["source"] == source_filter]

        for rec in targets:
            full = self.get_data(rec["id"])
            if not full:
                continue
            for row in full.get("data", []):
                matched = False
                for key, val in row.items():
                    if isinstance(val, str) and query_lower in val.lower():
                        matched = True
                        break
                if matched:
                    row["_source_id"] = rec["id"]
                    row["_source_file"] = rec["filename"]
                    row["_source_type"] = rec["source"]
                    row["_category"] = rec["category"]
                    results.append(row)

        # Sort by volume if available, else by relevance
        results.sort(
            key=lambda x: x.get("Volume", x.get("volume", x.get("Search Volume", x.get("Clicks", 0)))),
            reverse=True
        )
        return results[:100]

    def get_stats(self) -> Dict:
        """Aggregate stats across all imported data."""
        by_source = {}
        total_rows = 0

        for rec in self._index:
            source = rec["source"]
            if source not in by_source:
                cat = self.CATEGORIES.get(source, self.CATEGORIES["custom_data"])
                by_source[source] = {
                    "label": cat["label"],
                    "icon": cat["icon"],
                    "color": cat["color"],
                    "count": 0,
                    "total_rows": 0,
                }
            by_source[source]["count"] += 1
            by_source[source]["total_rows"] += rec["rows_count"]
            total_rows += rec["rows_count"]

        return {
            "total_imports": len(self._index),
            "total_rows": total_rows,
            "by_source": by_source,
            "sources_connected": len(by_source),
        }
