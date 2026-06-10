---
name: wom-radar-deployer
description: Headless end-to-end deployment of Merino Radar posts on worldofmerino.com across 4 languages (IT/EN/DE/FR) via custom albeni/v1 REST endpoints. Reads a Radar folder (4 content files + visual PNG), uploads image, creates 4 posts with SEO + Polylang, links translation group. Single Python command, no Chrome extension. Use whenever a Radar brief is ready to publish — TRIGGERS deploy radar, lancia radar, pubblica radar, deploy_radar_post, closing the loop radar, deploy news scanner output, headless radar deploy, radar deploy script. Also trigger when the daily/weekly approval cycle approves a brief, when running from Mac terminal or scheduled task, or when wom-page-deployer's Chrome flow is unavailable. Prefer this over wom-page-deployer for Radar posts when the 4 content files and visual PNG already exist.
---

# WoM Radar Deployer

You are deploying a Merino Radar post end-to-end on `worldofmerino.com` across 4 languages, headlessly. This skill replaces the manual 15-step Chrome-extension flow with a single Python invocation that talks to custom REST endpoints.

This skill is the operational complement to `merino-news-scanner` (which produces the brief and visual). When that pipeline finishes and the human approves, **this** skill is what publishes the result.

## When to use this skill (and when not to)

**Use this skill when:**
- A Radar folder exists on disk with the 4 localized content files (`02-content-IT.md`, `03-content-EN.md`, `04-content-DE.md`, `05-content-FR.md`) and a `visual-*-wom.png`.
- The user wants the deploy to happen now, without opening a browser.
- The deploy is being triggered by a scheduled task / approval webhook (no Cowork UI available).
- The previous flow with `wom-page-deployer` failed silently because Chrome extension wasn't connected.

**Do not use this skill when:**
- The brief is only in Italian — translations not yet generated. (Run `albeni-mt-translator` first to produce the EN/DE/FR files.)
- The visual PNG hasn't been generated. (Run `generate_visuals.py` first.)
- The deploy is for `merinouniversity.com` — that's `mu-content-deployer` territory.
- The user wants to deploy something other than a Radar post (a guide page, a story page, etc.) — use `wom-page-deployer` for those.

## Prerequisites (verified once, then assumed)

Before this skill can run, the WoM site must have the **albeni/v1 custom REST endpoints** active. These are deployed as two WPCode snippets:

- **Snippet 2250 — "Albeni Visual Upload API"** → exposes `POST /wp-json/albeni/v1/upload-visual`
- **Snippet 2278 — "Albeni — Radar deploy endpoints"** → exposes `POST /wp-json/albeni/v1/create-radar-post` and `POST /wp-json/albeni/v1/pll-link`

All three endpoints share the same auth: header `X-Upload-Key` matching the env variable `WP_UPLOAD_SECRET` defined in `~/Documents/Claude/Projects/Merino News/merino-news-scanner/.env`.

If any endpoint returns 404 (`rest_no_route`), one of the snippets is inactive — see `references/troubleshooting.md`.

**Sanity check** before invoking the script (especially after a server restart or plugin update):

```bash
curl -m 15 -X POST https://worldofmerino.com/wp-json/albeni/v1/create-radar-post \
  -H "X-Upload-Key: $(grep WP_UPLOAD_SECRET ~/Documents/Claude/Projects/Merino\ News/merino-news-scanner/.env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Expected: HTTP 400 with `{"code":"albeni_missing_field","message":"title, slug and content are required"...}`. If you get 404, the endpoint snippet (#2278) is inactive and must be re-enabled in WPCode admin before the deploy can proceed. If you get 401, the `WP_UPLOAD_SECRET` doesn't match the one stored in the WPCode snippet.

## The headless pipeline

The whole flow is owned by one Python script:

```
~/Documents/Claude/Projects/Merino News/merino-news-scanner/pipeline/deploy_radar_post.py
```

### Invocation

```bash
cd ~/Documents/Claude/Projects/Merino\ News/merino-news-scanner/pipeline
python3 deploy_radar_post.py <radar-folder-path>
```

`<radar-folder-path>` is the absolute path to the Radar session folder, typically:

```
~/Documents/Claude/Radar/YYYY-MM-DD-<slug>
```

For a dry-run that parses everything but does not deploy:

```bash
python3 deploy_radar_post.py <radar-folder-path> --dry-run
```

### What the folder must contain

The script expects exactly these files in the folder:

- `02-content-IT.md` — Italian content with frontmatter (slug, title, SEO meta, Gutenberg body)
- `03-content-EN.md` — English equivalent (en-us slug)
- `04-content-DE.md` — German equivalent (de-* slug)
- `05-content-FR.md` — French equivalent (fr-* slug)
- `visual-*-wom.png` — the WoM-styled visual (lifestyle mood). If absent, the script also looks in `~/Documents/Claude/Projects/Merino News/merino-news-scanner/` for the most recent `visual-*-wom.png`.

Each content file is parsed by `parse_content_file()` in the script — it pulls slug, title, SEO title/description/focus-keyword and the fenced `\`\`\`html` Gutenberg block. The format follows the convention established in past Radar runs (see `references/content-file-format.md` for the canonical template).

### What the script does, step by step

1. **Parse** the 4 content files — extract title, slug, SEO metadata, Gutenberg body for each language.
2. **Locate visual** — find the WoM PNG (errors out cleanly if missing).
3. **Show summary + interactive confirmation** — prints title/slug/keyword for each language, asks for `YES` to proceed.
4. **Step 1/4: Upload visual** → `POST /albeni/v1/upload-visual` with base64 image. Returns media_id.
5. **Step 2/4: Create 4 posts** → for each lang, `POST /albeni/v1/create-radar-post` with title/slug/content/featured_media/SEO/lang. Each call assigns the right Polylang language and Radar category server-side.
6. **Step 3/4: Link Polylang group** → `POST /albeni/v1/pll-link` with `{lang: post_id}` map. Server clears any stale translation groups and creates a clean 4-language linkage.
7. **Step 4/4: Print Hostinger CDN purge notice** — the hcdn edge does not auto-invalidate. Manually purge from `hpanel.hostinger.com` Dashboard → Clear cache.

The script ends with a printed summary of the 4 published post IDs.

## After the script finishes

The Hostinger CDN (server: hcdn) sits in front of LiteSpeed and is **not** invalidated by REST writes. Until purged, the homes and the `/radar/` hub will keep serving cached HTML even though the new posts exist. Two options:

- **Manual purge**: open `https://hpanel.hostinger.com/websites/worldofmerino.com` → Cancella la cache → Cancella la cache → confirm. Toast: "Cache cleaned successfully".
- **Wait it out**: the edge TTL is short (minutes), so even without purge the new content surfaces shortly.

Then verify the 4 frontend URLs respond 200 with the correct title and featured image:

```bash
for slug in \
  "comprare-meno-XXX" \
  "en-us/en-buy-less-XXX" \
  "de/de-weniger-XXX" \
  "fr/fr-acheter-moins-XXX"; do
  curl -s -o /dev/null -w "%{http_code} https://worldofmerino.com/$slug\n" \
    "https://worldofmerino.com/$slug/"
done
```

## Integration with merino-news-scanner output

A Radar deploy session is typically the result of:

1. `merino-news-scanner` produces `brief-YYYY-MM-DD.md` with a "Visual Proposti" section.
2. The user runs `python3 generate_visuals.py brief-YYYY-MM-DD.md` to produce `visual-YYYYMMDD-fatto1-wom.png`.
3. The user (or `albeni-mt-translator`) writes the 4 content files into a session folder under `~/Documents/Claude/Radar/YYYY-MM-DD-<slug>/`.
4. The user (or the approval webhook trigger) invokes this skill via the `deploy_radar_post.py` script.

Steps 1–3 are upstream of this skill. This skill assumes they're done.

## Integration with notion-approval-deployer

The scheduled `notion-approval-deployer` skill polls Notion for entries with `Stato = "In Produzione"` (set by the human via the approval dashboard webhook). When it finds a Radar entry, it should invoke `deploy_radar_post.py` directly — see the updated `~/Documents/Claude/Scheduled/notion-approval-deployer/SKILL.md` for the exact flow.

This is what closes the loop: human approval click → 30 minutes later the deploy is live, with no Cowork UI required.

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `Endpoint not found: .../create-radar-post` | Snippet 2278 inactive in WPCode | Activate it from WPCode admin or recreate from `pipeline/wpcode-albeni-v1-endpoints.php` |
| HTTP 401 `albeni_unauthorized` | `WP_UPLOAD_SECRET` mismatch between `.env` and PHP snippet | Reconcile both to the same value |
| HTTP 400 `image_data is not valid base64` | PNG corrupted or path wrong | Re-run `generate_visuals.py` to regenerate |
| Script hangs > 60s on first endpoint call | Hostinger PHP-FPM saturation (transient) | Ctrl+C, wait 5–10 minutes, retry |
| Post created but content empty (60 chars `<p>Loading...</p>`) | Old behaviour from manual flow — should not happen with this script | If observed, file a bug in this skill — script always sends full content in single call |
| 4 posts created but Polylang group not linked | `pll-link` call failed silently | Verify Polylang plugin is active, re-run only `pll-link` step manually with the 4 post IDs |
| Posts visible in admin, not on `/radar/` hub | Hostinger CDN not purged | Purge from hPanel as described above |

For deep-dive troubleshooting (server saturation patterns, secret rotation, snippet ID changes), see `references/troubleshooting.md`.

## What this skill explicitly does NOT do

- **Generate the visual**: that's `merino-news-scanner` / `generate_visuals.py`.
- **Write the content**: that's the human (with help from `albeni-mt-translator` for translations).
- **Purge Hostinger CDN**: no public API for hcdn — manual step.
- **Deploy to merinouniversity.com**: that's `mu-content-deployer`.
- **Deploy non-Radar posts** (guides, stories, hub pages): that's `wom-page-deployer`.

## Why this skill exists separately from wom-page-deployer

`wom-page-deployer` is a Chrome-extension-based skill — it requires an active Cowork browser session and walks through the WP admin UI step by step. It works for one-off deploys when a human is at the keyboard.

`wom-radar-deployer` (this skill) is **headless** — pure REST API calls via Python script. It works from cron, from Railway scheduled tasks, from the approval webhook, or from the terminal. The two skills are siblings, not duplicates: same destination (WoM), different transport (UI vs API), different operational context (interactive vs autonomous).

When in doubt for a Radar post deploy: prefer this one. It's faster, more reliable, doesn't depend on browser state, and produces deterministic output that's easy to verify.
