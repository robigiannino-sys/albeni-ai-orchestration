#!/usr/bin/env python3
"""
Merino Approval Dashboard Generator
-----------------------------------
Queries Notion for all [NEWS] briefs with Stato = "Da Fare" and produces a
single self-contained HTML file that renders each brief like the final
WoM/MU page will look, with one-click Approve / Archive buttons wired
to the Railway webhook.

Usage:
    python generate.py              # writes ../dashboard.html
    python generate.py --open        # also opens it in the default browser

The output is a pure static HTML — no server needed locally. All approval
actions go over HTTPS to the webhook, which updates Notion. The polling
scheduled task (every 30min) then picks up "In Produzione" entries and
triggers the wp/mu deploy skills.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import webbrowser
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", SCRIPT_DIR.parent / "dashboard.html"))

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

if not all([NOTION_TOKEN, NOTION_DB_ID]):
    sys.exit("[fatal] missing NOTION_TOKEN or NOTION_DB_ID in .env")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Notion fetchers
# ---------------------------------------------------------------------------


def query_pending_briefs() -> list[dict[str, Any]]:
    """Return all pages with Stato = 'Da Fare' and title starting with [NEWS]."""
    results: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        payload: dict[str, Any] = {
            "filter": {
                "and": [
                    {"property": "Stato", "select": {"equals": "Da Fare"}},
                    {"property": "Contenuto", "title": {"starts_with": "[NEWS]"}},
                ]
            },
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            "page_size": 100,
        }
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(
            f"{NOTION_API}/databases/{NOTION_DB_ID}/query",
            headers=HEADERS,
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


def fetch_page_blocks(page_id: str) -> list[dict[str, Any]]:
    """Fetch all top-level blocks of a page (recursing one level for tables/toggle)."""
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        r = requests.get(
            f"{NOTION_API}/blocks/{page_id}/children",
            headers=HEADERS,
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return out


# ---------------------------------------------------------------------------
# Content extraction (from Notion blocks → structured brief)
# ---------------------------------------------------------------------------


def rich_text_to_str(rt: list[dict[str, Any]] | None) -> str:
    if not rt:
        return ""
    return "".join(seg.get("plain_text", "") for seg in rt)


def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Minimal block → markdown flattener, enough to split by sections."""
    lines: list[str] = []
    for b in blocks:
        t = b.get("type")
        content = b.get(t, {})
        if t == "heading_1":
            lines.append(f"# {rich_text_to_str(content.get('rich_text'))}")
        elif t == "heading_2":
            lines.append(f"## {rich_text_to_str(content.get('rich_text'))}")
        elif t == "heading_3":
            lines.append(f"### {rich_text_to_str(content.get('rich_text'))}")
        elif t == "paragraph":
            txt = rich_text_to_str(content.get("rich_text"))
            if txt:
                lines.append(txt)
        elif t == "bulleted_list_item":
            lines.append(f"- {rich_text_to_str(content.get('rich_text'))}")
        elif t == "numbered_list_item":
            lines.append(f"1. {rich_text_to_str(content.get('rich_text'))}")
        elif t == "quote":
            lines.append(f"> {rich_text_to_str(content.get('rich_text'))}")
        elif t == "divider":
            lines.append("---")
        elif t == "image":
            src = content.get("file", {}).get("url") or content.get("external", {}).get("url", "")
            if src:
                lines.append(f"![]({src})")
        elif t == "callout":
            lines.append(f"> 💡 {rich_text_to_str(content.get('rich_text'))}")
        elif t == "code":
            lines.append(f"```\n{rich_text_to_str(content.get('rich_text'))}\n```")
        elif t == "table":
            # skip — table rendering would need a second fetch per row
            lines.append("_(tabella — vedi Notion)_")
    return "\n\n".join(lines)


SECTION_PATTERN = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


def split_sections(md: str) -> dict[str, str]:
    """Split markdown into {section_title: body} using #/##/### headings."""
    matches = list(SECTION_PATTERN.finditer(md))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        sections[title] = md[start:end].strip()
    return sections


def extract_first_image(blocks: list[dict[str, Any]]) -> str | None:
    """Find the first image URL — used as preview hero."""
    for b in blocks:
        if b.get("type") == "image":
            img = b["image"]
            return img.get("file", {}).get("url") or img.get("external", {}).get("url")
    return None


TITLES_PATTERN = re.compile(r"^\s*(?:\d+\.|-|\*)\s+[\"\"]?(.+?)[\"\"]?\s*$", re.MULTILINE)
INCIPIT_PATTERN = re.compile(r"\*?[\"\"](.+?)[\"\"]\*?", re.DOTALL)


def build_preview(page: dict[str, Any], blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract the fields needed for the deployed-page mockup."""
    props = page["properties"]

    title = rich_text_to_str(props["Contenuto"]["title"])
    dominio = (props.get("Dominio", {}).get("select") or {}).get("name", "")
    tipo = (props.get("Tipo Contenuto", {}).get("select") or {}).get("name", "")
    cluster = (props.get("Cluster", {}).get("select") or {}).get("name", "")
    keyword = rich_text_to_str(props.get("Keyword Target", {}).get("rich_text"))
    note = rich_text_to_str(props.get("Note", {}).get("rich_text"))

    md = blocks_to_markdown(blocks)
    sections = split_sections(md)

    def find_section(*needles: str) -> str:
        for sec_title, body in sections.items():
            lowered = sec_title.lower()
            if any(n in lowered for n in needles):
                return body
        return ""

    fatto = find_section("fatto")
    angolo = find_section("angolo editoriale", "angolo mu", "angolo wom", "angolo tecnico")
    cluster_map = find_section("mappa cluster")
    keyword_bridge = find_section("ponte keyword", "keyword bridge")

    # Extract proposed title (first entry after "Titoli proposti")
    proposed_title = ""
    if angolo:
        # look for "Titoli proposti:" then first quoted / numbered item
        tp_match = re.search(
            r"[Tt]itoli?\s+propost[oi].*?\n+(.*?)(?:\n{2,}|$)", angolo, re.DOTALL
        )
        if tp_match:
            block = tp_match.group(1)
            t = TITLES_PATTERN.search(block)
            if t:
                proposed_title = t.group(1).strip().strip("*")

    # Extract incipit
    incipit = ""
    if angolo:
        inc_match = re.search(r"[Ii]ncipit[^:\n]*:\s*(.+?)(?:\n{2,}|$)", angolo, re.DOTALL)
        if inc_match:
            raw = inc_match.group(1).strip()
            m = INCIPIT_PATTERN.search(raw)
            incipit = (m.group(1) if m else raw).strip().strip("*")

    hero_image = extract_first_image(blocks)

    return {
        "id": page["id"],
        "url": page["url"],
        "title": title,
        "dominio": dominio,
        "tipo": tipo,
        "cluster": cluster,
        "keyword": keyword,
        "note": note,
        "created": page.get("created_time", ""),
        "sections": sections,
        "fatto": fatto,
        "angolo": angolo,
        "cluster_map": cluster_map,
        "keyword_bridge": keyword_bridge,
        "proposed_title": proposed_title or title.split("—")[-1].strip(),
        "incipit": incipit,
        "hero_image": hero_image,
    }


# ---------------------------------------------------------------------------
# HTML renderers
# ---------------------------------------------------------------------------


def md_to_html(md: str) -> str:
    """Very small markdown → HTML for preview bodies.
    We avoid full markdown lib overhead for simple inline content."""
    if not md:
        return ""
    html = escape(md)
    # bold/italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    # links
    html = re.sub(
        r"\[(.+?)\]\((https?://[^\s)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener" class="underline">\1</a>',
        html,
    )
    # linebreaks
    html = html.replace("\n\n", "</p><p>").replace("\n", "<br/>")
    return f"<p>{html}</p>"


def render_brief_card(b: dict[str, Any]) -> str:
    is_wom = "worldofmerino" in (b["dominio"] or "")
    is_mu = "merinouniversity" in (b["dominio"] or "")
    domain_class = "card--wom" if is_wom else ("card--mu" if is_mu else "card--generic")
    domain_label = "World of Merino" if is_wom else ("Merino University" if is_mu else b["dominio"])
    domain_emoji = "📰" if is_wom else ("🔬" if is_mu else "📄")

    hero_html = (
        f'<img class="hero" src="{escape(b["hero_image"])}" alt="Preview visual"/>'
        if b["hero_image"]
        else '<div class="hero hero--empty">🖼️ Nessun visual ancora generato</div>'
    )

    chips = []
    if b["tipo"]:
        chips.append(f'<span class="chip chip--tipo">{escape(b["tipo"])}</span>')
    if b["cluster"]:
        chips.append(f'<span class="chip chip--cluster">{escape(b["cluster"])}</span>')
    chips_html = "".join(chips)

    keyword_html = (
        f'<div class="kv"><span class="kv-k">Focus keyword DE:</span> <span class="kv-v">{escape(b["keyword"])}</span></div>'
        if b["keyword"]
        else ""
    )

    note_html = (
        f'<details class="note"><summary>📋 Note routing (editor)</summary><div>{md_to_html(b["note"])}</div></details>'
        if b["note"]
        else ""
    )

    # deployed page mockup
    mockup = f"""
      <article class="mockup {domain_class}">
        <header class="mockup-header">
          <div class="mockup-domain">{domain_emoji} {escape(domain_label)}</div>
          <h1 class="mockup-title">{escape(b["proposed_title"])}</h1>
        </header>
        {hero_html}
        <div class="mockup-body">
          {md_to_html(b["incipit"]) if b["incipit"] else ""}
          {md_to_html(b["angolo"]) if b["angolo"] else "<p><em>Contenuto editoriale da finalizzare.</em></p>"}
        </div>
      </article>
    """

    sections_summary = f"""
      <details class="meta">
        <summary>📑 Dettagli brief (routing, cluster, keyword)</summary>
        <div class="meta-grid">
          <div><strong>Il Fatto</strong>{md_to_html(b["fatto"])}</div>
          <div><strong>Mappa Cluster</strong>{md_to_html(b["cluster_map"])}</div>
          <div><strong>Ponte Keyword DE</strong>{md_to_html(b["keyword_bridge"])}</div>
        </div>
      </details>
    """

    return f"""
    <section class="card" data-page-id="{escape(b["id"])}" data-title="{escape(b["title"])}">
      <header class="card-header">
        <div class="card-meta">
          {chips_html}
          <a class="card-source" href="{escape(b["url"])}" target="_blank" rel="noopener">Apri in Notion ↗</a>
        </div>
        <h2 class="card-title">{escape(b["title"])}</h2>
        {keyword_html}
        {note_html}
      </header>

      <div class="card-preview-label">🎬 Anteprima pagina come sarà deployata</div>
      {mockup}

      {sections_summary}

      <footer class="card-actions">
        <button class="btn btn--approve" data-action="approve">✅ Approva & Deploy</button>
        <button class="btn btn--archive" data-action="archive">🗄️ Archivia</button>
        <span class="card-status" aria-live="polite"></span>
      </footer>
    </section>
    """


def render_dashboard(briefs: list[dict[str, Any]]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cards_html = "\n".join(render_brief_card(b) for b in briefs) or (
        '<div class="empty">🎉 Nessun brief pendente. La pipeline è pulita.</div>'
    )

    webhook_url_js = json.dumps(WEBHOOK_URL)
    webhook_secret_js = json.dumps(WEBHOOK_SECRET)

    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Merino Approval Dashboard — {len(briefs)} brief pendenti</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Cormorant+Garamond:wght@400;500;600&display=swap" rel="stylesheet">
  <style>{DASHBOARD_CSS}</style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand">Merino Approval Dashboard</div>
      <div class="meta">
        <span class="badge">{len(briefs)} pendenti</span>
        <span class="ts">Generato {now}</span>
        <button class="btn btn--ghost" onclick="location.reload()">↻ Ricarica</button>
      </div>
    </div>
  </header>

  <main class="container">
    {cards_html}
  </main>

  <footer class="bottombar">
    Albeni 1905 · Content Pipeline · polling automatico ogni 30min
  </footer>

  <script>
    const WEBHOOK_URL = {webhook_url_js};
    const WEBHOOK_SECRET = {webhook_secret_js};
    {DASHBOARD_JS}
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Styles & scripts (embedded)
# ---------------------------------------------------------------------------

DASHBOARD_CSS = r"""
:root {
  --bg: #f7f5f1;
  --fg: #1a1a1a;
  --muted: #6b6b6b;
  --line: #e6e2d8;
  --card-bg: #ffffff;
  --accent: #8b6f47;
  --wom-accent: #3d4b5c;
  --mu-accent: #2a5f3a;
  --approve: #2f7a3f;
  --approve-hover: #24612f;
  --archive: #8a8a8a;
  --archive-hover: #5f5f5f;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg); font-family: 'Inter', system-ui, -apple-system, sans-serif; }
a { color: inherit; }

.topbar {
  position: sticky; top: 0; z-index: 10;
  background: rgba(255,255,255,0.92); backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line);
}
.topbar-inner {
  max-width: 1280px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px;
}
.brand { font-family: 'Cormorant Garamond', serif; font-size: 22px; font-weight: 600; letter-spacing: 0.3px; }
.meta { display: flex; align-items: center; gap: 14px; font-size: 13px; color: var(--muted); }
.badge { background: #eee7d8; color: #5c4a2a; padding: 4px 10px; border-radius: 999px; font-weight: 600; }
.ts { font-variant-numeric: tabular-nums; }

.container { max-width: 1080px; margin: 0 auto; padding: 32px 24px 80px; display: flex; flex-direction: column; gap: 32px; }

.empty { background: var(--card-bg); border: 1px solid var(--line); border-radius: 16px; padding: 48px; text-align: center; color: var(--muted); }

.card {
  background: var(--card-bg); border: 1px solid var(--line);
  border-radius: 16px; overflow: hidden;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.card-header { padding: 20px 24px 14px; border-bottom: 1px solid var(--line); }
.card-meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
.chip { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; padding: 4px 10px; border-radius: 999px; background: #f0ebde; color: #5c4a2a; }
.chip--tipo { background: #e8eef5; color: #2d4a6b; }
.chip--cluster { background: #ede8df; color: #5c4a2a; }
.card-source { margin-left: auto; font-size: 12px; color: var(--muted); text-decoration: none; }
.card-source:hover { text-decoration: underline; }
.card-title { margin: 0; font-size: 18px; font-weight: 600; line-height: 1.35; }
.kv { margin-top: 10px; font-size: 13px; }
.kv-k { color: var(--muted); font-weight: 500; }
.kv-v { color: var(--fg); font-family: 'JetBrains Mono', monospace; }

.note { margin-top: 12px; font-size: 13px; color: var(--muted); }
.note summary { cursor: pointer; user-select: none; font-weight: 500; }
.note > div { padding: 8px 12px; background: #faf7ee; border-left: 3px solid var(--accent); margin-top: 6px; border-radius: 4px; }

.card-preview-label { padding: 14px 24px 8px; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); font-weight: 600; }

.mockup {
  margin: 0 24px; padding: 28px;
  background: #fafaf7; border: 1px solid var(--line); border-radius: 10px;
  line-height: 1.7;
}
.mockup--wom, .mockup.card--wom { --m-accent: var(--wom-accent); border-top: 3px solid var(--wom-accent); }
.mockup--mu, .mockup.card--mu { --m-accent: var(--mu-accent); border-top: 3px solid var(--mu-accent); background: #fcfcfa; }
.mockup-header { margin-bottom: 20px; }
.mockup-domain { font-size: 11px; text-transform: uppercase; letter-spacing: 2px; color: var(--m-accent, var(--accent)); font-weight: 700; margin-bottom: 10px; }
.mockup-title { font-family: 'Cormorant Garamond', serif; font-size: 30px; font-weight: 600; line-height: 1.15; margin: 0; color: #1a1a1a; }
.card--wom .mockup-title { color: #1e2835; }
.card--mu .mockup-title { color: #1a3a25; }
.hero { display: block; width: 100%; max-height: 420px; object-fit: cover; border-radius: 8px; margin-bottom: 20px; }
.hero--empty { background: linear-gradient(135deg,#f0ece2,#e4ddc9); color: var(--muted); padding: 48px; text-align: center; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }
.mockup-body p { margin: 0 0 14px; font-size: 16px; color: #2a2a2a; }
.mockup-body strong { color: var(--m-accent, var(--accent)); }
.mockup-body a { text-decoration-color: #ccc; }

.meta { padding: 14px 24px; background: #fafaf7; border-top: 1px solid var(--line); }
.meta summary { cursor: pointer; user-select: none; font-size: 13px; font-weight: 600; color: var(--muted); }
.meta-grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 12px; font-size: 13px; color: var(--muted); }
.meta-grid strong { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--fg); margin-bottom: 6px; }

.card-actions { padding: 18px 24px; border-top: 1px solid var(--line); display: flex; gap: 12px; align-items: center; background: #fefdfa; }
.btn {
  font: inherit; font-weight: 600; font-size: 14px;
  padding: 10px 18px; border-radius: 8px; cursor: pointer;
  border: 1px solid transparent; transition: all .15s ease;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn--approve { background: var(--approve); color: white; }
.btn--approve:hover:not(:disabled) { background: var(--approve-hover); }
.btn--archive { background: transparent; color: var(--archive); border-color: var(--archive); }
.btn--archive:hover:not(:disabled) { background: var(--archive); color: white; }
.btn--ghost { background: transparent; border-color: var(--line); color: var(--muted); padding: 6px 12px; font-size: 12px; }
.btn--ghost:hover { background: #f0ebde; }
.card-status { font-size: 13px; color: var(--muted); margin-left: auto; font-weight: 500; }
.card-status.ok { color: var(--approve); }
.card-status.err { color: #b04040; }
.card[data-resolved="true"] { opacity: 0.5; }
.card[data-resolved="true"] .btn { pointer-events: none; }

.bottombar { text-align: center; padding: 20px; color: var(--muted); font-size: 12px; border-top: 1px solid var(--line); }
"""

DASHBOARD_JS = r"""
async function resolve(card, action) {
  const pageId = card.dataset.pageId;
  const title = card.dataset.title;
  const status = card.querySelector('.card-status');
  const btns = card.querySelectorAll('.btn');

  let reason = null;
  if (action === 'archive') {
    reason = prompt(`Motivo archiviazione (opzionale) per:\n"${title}"`, '') || '';
  } else {
    if (!confirm(`Confermi approvazione e deploy automatico di:\n\n"${title}"\n\nLa pipeline deployerà questa pagina sul dominio corrispondente entro 30 min.`)) {
      return;
    }
  }

  btns.forEach(b => b.disabled = true);
  status.textContent = action === 'approve' ? '⏳ Approving…' : '⏳ Archiving…';
  status.className = 'card-status';

  try {
    const body = { pageId, actor: 'dashboard' };
    if (reason) body.reason = reason;
    const r = await fetch(`${WEBHOOK_URL}/${action}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Webhook-Secret': WEBHOOK_SECRET,
      },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!data.ok) throw new Error(data.error || 'unknown');
    status.textContent = action === 'approve'
      ? '✅ Approvato — deploy entro 30 min'
      : '🗄️ Archiviato';
    status.className = 'card-status ok';
    card.dataset.resolved = 'true';
  } catch (e) {
    status.textContent = `⚠️ Errore: ${e.message}`;
    status.className = 'card-status err';
    btns.forEach(b => b.disabled = false);
  }
}

document.querySelectorAll('.card').forEach(card => {
  card.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', () => resolve(card, btn.dataset.action));
  });
});
"""


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true", help="Open the generated HTML in the default browser")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Output HTML path")
    args = parser.parse_args()

    if not WEBHOOK_URL or WEBHOOK_URL.startswith("https://your-webhook"):
        print("[warn] WEBHOOK_URL is not configured — approve/archive buttons will fail until you deploy the webhook.")

    print("[fetch] querying Notion for Stato=Da Fare [NEWS] briefs…")
    pages = query_pending_briefs()
    print(f"[fetch] {len(pages)} pending brief(s).")

    briefs: list[dict[str, Any]] = []
    for i, p in enumerate(pages, 1):
        title = rich_text_to_str(p["properties"]["Contenuto"]["title"])
        print(f"  [{i}/{len(pages)}] {title[:80]}…")
        blocks = fetch_page_blocks(p["id"])
        briefs.append(build_preview(p, blocks))

    html = render_dashboard(briefs)
    output = args.output.resolve()
    output.write_text(html, encoding="utf-8")
    print(f"[done] wrote {output}  ({len(html):,} bytes)")

    if args.open:
        webbrowser.open(output.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
