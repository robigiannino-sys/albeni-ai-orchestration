---
name: mu-content-deployer
description: |
  **MU Content Page Deployer**: Deploys new content pages (checklists, scorecards, guides, educational articles) across all 4 languages (IT/EN/DE/FR) on the Merino University WordPress production site. Handles the complete pipeline: HTML content generation, batch page creation via wp.apiFetch, content loading via chunked JS, Polylang translation linking, Rank Math SEO, WPCode snippet updates (#2867 interlinking, #2866 references), LiteSpeed cache purge, and frontend verification.
  - MANDATORY TRIGGERS: deploy pages, deploy content, crea pagine, deploy checklist, deploy guide, nuove pagine MU, new MU pages, batch deploy, pipeline deploy, deploy 4 lingue, implementa pagine
  - Also trigger when: user asks to create new educational pages on MU, deploy interactive content across languages, add new pages to the Practical Lab or any MU department, create checklists/scorecards/guides for behavioral clusters, or implement content from the Framework Editoriale Material-First
---

## 🎙️ Voice Guidelines — MANDATORY READ (v1.0 — 2026-05-12)

**Before producing or modifying any editorial content**, this skill MUST load and apply the universal voice baseline:

📄 `voice-baseline-albeni-content.md` (workspace root, also mirrored at `skills-data/voice-baseline-albeni-content.md`)

It defines:
1. **5 cluster TOV** (C1 Business / C2 Heritage / C3 Conscious / C4 Minimalist / C5 Italian) — §1
2. **Anti-AI-tell hard-fail patterns** (regex v1.1: antitesi cascata, chiusure aforistiche, apertura magazine-cover, personificazione mercato) — §2
3. **4 regole-base distillate** (apertura ancora al fatto, antitesi UNA, chiusura CTA, mercato non parla) — §3
4. **Format-specific overrides** (Radar 300-550w, Story 800+, Osservatorio, MU checklist, customer care, email, ADV) — §4
5. **CTA standard per cluster** — §5
6. **7 anti-exemplar bocciati dal validator** — §6
7. **9-point self-check pre-publish** — §7

For Radar-specific work: also load `merino-news-scanner/references/wom-radar-voice-config.md` v1.1 (already extends this baseline) and validate output against `wom-radar-validator/rubric-v1.1.md`.

**Self-check**: if your output contains any of these phrases, STOP and rewrite:
- "Immagina un mondo in cui", "C'è un X che", "Non è utopia: è", "in un'epoca in cui"
- Multiple antitesi cascata ("Non X, ma Y. Non Z, ma W. Non...")
- Closures like "Forse la lezione più", "Era solo bastato dirlo", "comincia da questa domanda"
- Personificazione "Il mercato ha preso parola", "L'industria sta dicendo"
- Absent CTA to cluster Lead Magnet

---

# MU Content Page Deployer

You are deploying new content pages to Merino University (MU) production site (`merinouniversity.com`). This skill encodes the proven 7-step deployment pipeline that reliably creates, loads, links, and verifies multilingual content pages.

## When to Use This Skill

Use this whenever you need to create NEW pages on MU — whether they're checklists, scorecards, guides, educational articles, or any structured HTML content. The pipeline is designed for batch deployment across all 4 languages simultaneously, but works for single-language pages too.

This skill complements the `albeni-wp-operator` skill, which covers general WP operations. Use this skill specifically for the **end-to-end deployment pipeline** of new content pages. The wp-operator handles individual operations (Polylang fixes, SEO updates, etc.) — this skill orchestrates them into a complete workflow.

## Pre-Flight Checklist

Before starting, confirm you have:

1. **Chrome tab on MU admin dashboard** — `wp.apiFetch` must be available
2. **Content ready** in all 4 languages (or at minimum IT as the master copy)
3. **Parent page ID** — which department hub the pages go under (common parents below)
4. **Page IDs for interlinking** — related existing pages to cross-link

### Common MU Parent Page IDs

| Department | IT Hub ID |
|---|---|
| Material Science | 32 |
| Ethical Origins | 33 |
| Construction & Design | 34 |
| Innovation | 35 |
| **Practical Lab** | **36** |

## The 7-Step Pipeline

### Step 1: Generate Content (HTML + CSS)

All MU interactive pages use a shared design system. Read `references/css-design-system.md` for the full CSS block and design tokens.

**Key principles:**
- Every page wraps in a single `<!-- wp:html -->` block (Gutenberg custom HTML)
- Each page gets a unique container ID (e.g., `id="ck-c1"`) to avoid JS conflicts
- The shared CSS block (~3100 chars) is identical across all pages — cache it in `window._css` for reuse
- JS functions use unique names per page (e.g., `updateScore()`, `updateC2()`)

**Content structure for interactive checklists/scorecards:**
```
<!-- wp:html -->
<div id="[unique-id]" class="ck-page">
  <style>[shared CSS]</style>
  <div class="ck-hero">
    <span class="ck-badge">[cluster badge]</span>
    <h1>[page title]</h1>
    <p>[subtitle/description]</p>
  </div>
  <div class="ck-intro">[intro paragraph]</div>
  [ck-section blocks with ck-items]
  <div class="ck-result">[scoring display]</div>
  <div class="ck-cta">[call-to-action]</div>
  <script>[scoring function]</script>
</div>
<!-- /wp:html -->
```

Read `references/content-templates.md` for complete templates for checklists, scorecards, and guides.

**For non-interactive pages** (articles, guides without scoring), you can use standard Gutenberg blocks (paragraphs, headings, lists) wrapped in `<!-- wp:html -->` with the MU design system CSS.

### Step 2: Batch Create Pages via wp.apiFetch

Create all pages at once from the WP admin dashboard. The pattern creates placeholder pages, returns their IDs, and loads content in the next step.

**Page creation pattern — one language at a time (4-8 pages per batch):**
```javascript
var pages = [
  {title:'Page Title IT', slug:'slug-it'},
  {title:'Page Title 2 IT', slug:'slug-2-it'}
];
window._ids = [];
var chain = Promise.resolve();
pages.forEach(function(p) {
  chain = chain.then(function() {
    return wp.apiFetch({
      path: '/wp/v2/pages',
      method: 'POST',
      data: {
        title: p.title,
        slug: p.slug,
        status: 'publish',
        parent: 36,  // ← parent hub ID
        content: '<!-- wp:html --><p>Loading...</p><!-- /wp:html -->'
      }
    });
  }).then(function(r) { window._ids.push(r.id); });
});
chain.then(function() { window._createResult = 'OK:' + window._ids.join(','); });
```

**Repeat for EN, DE, FR** with localized titles and slugs. The slug convention is:
- IT: `checklist-qualita-heritage-merino`
- EN: `en-checklist-heritage-quality-merino`
- DE: `de-checkliste-heritage-qualitaet-merino`
- FR: `fr-checklist-qualite-heritage-merino`

**Record all page IDs immediately** — you'll need them for every subsequent step.

### Step 3: Load Content via Chunked JS

Content payloads are typically 8-12KB per page, which exceeds the Chrome JS tool's comfortable execution limit (~3000 chars per call). The chunking pattern solves this:

**Step 3a — Cache the shared CSS (do this once):**
```javascript
window._css = '[entire CSS block from references/css-design-system.md]';
```

**Step 3b — Build content incrementally for each page:**
```javascript
// Chunk 1: CSS + hero + intro
window._c = '<!-- wp:html -->\n<div id="ck-c1" class="ck-page"><style>' + window._css + '</style>';
window._c += '<div class="ck-hero">...</div><div class="ck-intro">...</div>';

// Chunk 2: Section 1
window._c += '<div class="ck-section">...</div>';

// Chunk 3: Section 2 + Section 3
window._c += '<div class="ck-section">...</div><div class="ck-section">...</div>';

// Chunk 4: Result + CTA + Script + closing tags
window._c += '<div class="ck-result">...</div><div class="ck-cta">...</div>';
window._c += '<script>function updateScore(){...}<\/script></div>\n<!-- /wp:html -->\n';
```

**Step 3c — Push to WordPress:**
```javascript
wp.apiFetch({
  path: '/wp/v2/pages/PAGE_ID',
  method: 'POST',
  data: { content: window._c, status: 'publish' }
}).then(r => window._saveResult = 'OK:' + r.id)
  .catch(e => window._saveResult = 'ERR:' + e.message);
```

**Repeat for all 20 pages** (5 content types × 4 languages). The CSS is identical — only the text content, titles, function names, and verdict strings change per language.

### Step 4: Link Polylang Translation Groups

Polylang translation linking requires PHP functions (`pll_set_post_language`, `pll_save_post_translations`) which aren't available via REST API. Use a temporary functions.php AJAX handler:

**Step 4a — Navigate to theme file editor:**
```
/wp-admin/theme-editor.php?file=functions.php&theme=twentytwentyfive
```

**Step 4b — Record baseline length and append handler:**
```javascript
var ta = document.getElementById('newcontent');
window._baseline = ta.value.length;  // SAVE THIS — you need it for cleanup

var handler = '\n// TEMP_PLL_HANDLER\nadd_action(\'wp_ajax_tmp_pll_link\',function(){\n  if(!current_user_can(\'manage_options\')) wp_die(\'no\');\n  $groups=json_decode(stripslashes($_POST[\'groups\']),true);\n  $langs=array(\'it\',\'en\',\'de\',\'fr\');\n  $results=array();\n  foreach($groups as $gi=>$g){\n    foreach($langs as $li=>$lang){\n      if(isset($g[$li])) pll_set_post_language((int)$g[$li],$lang);\n    }\n    $tr=array();\n    foreach($langs as $li=>$lang){\n      if(isset($g[$li])) $tr[$lang]=(int)$g[$li];\n    }\n    pll_save_post_translations($tr);\n    $results[]=$tr;\n  }\n  wp_send_json_success($results);\n});\n';
ta.value += handler;
```

**Step 4c — Save via form submit (NOT button click):**
```javascript
HTMLFormElement.prototype.submit.call(document.querySelector('form#template'));
```

**Step 4d — Call the handler:**
```javascript
var groups = [[IT_C1, EN_C1, DE_C1, FR_C1], [IT_C2, EN_C2, DE_C2, FR_C2], ...];
var fd = new FormData();
fd.append('action', 'tmp_pll_link');
fd.append('groups', JSON.stringify(groups));
fetch('/wp-admin/admin-ajax.php', {
  method: 'POST', body: fd, credentials: 'same-origin'
}).then(r => r.json()).then(j => window._pllRes = JSON.stringify(j));
```

Expected response: `{"success":true,"data":[{"it":ID,"en":ID,"de":ID,"fr":ID}, ...]}`

**Step 4e — CRITICAL: Restore functions.php to baseline:**
```javascript
var ta = document.getElementById('newcontent');
var v = ta.value;
var idx = v.indexOf('\n// TEMP_PLL_HANDLER');
if (idx > -1) { ta.value = v.substring(0, idx); }
HTMLFormElement.prototype.submit.call(document.querySelector('form#template'));
```
Verify restored length matches `window._baseline`.

### Step 5: Set Rank Math SEO

Use the dedicated Rank Math REST endpoint (the standard WP REST API silently ignores Rank Math fields):

```javascript
// Define all 20 SEO entries
window._seo = [
  {id: PAGE_ID, title: 'SEO Title', desc: 'Meta description under 155 chars.', focus: 'focus keyword'},
  // ... repeat for all pages
];

// Sequential batch (respects rate limits)
window._seoResults = []; window._seoIdx = 0;
function doNextSeo() {
  if (window._seoIdx >= window._seo.length) {
    window._seoDone = 'ALL_DONE:' + window._seoResults.length; return;
  }
  var s = window._seo[window._seoIdx];
  wp.apiFetch({
    path: '/rankmath/v1/updateMeta', method: 'POST',
    data: {
      objectID: s.id, objectType: 'post',
      meta: {
        rank_math_title: s.title,
        rank_math_description: s.desc,
        rank_math_focus_keyword: s.focus
      }
    }
  }).then(function(r) {
    window._seoResults.push('OK:' + s.id);
    window._seoIdx++; doNextSeo();
  }).catch(function(e) {
    window._seoResults.push('ERR:' + s.id + ':' + e.message);
    window._seoIdx++; doNextSeo();
  });
}
doNextSeo();
```

**SEO content guidelines per language:**
- **Title**: Include primary keyword + compelling descriptor (under 60 chars ideal)
- **Description**: Summarize what the page offers + why it matters (under 155 chars)
- **Focus keyword**: 2-4 word phrase matching the page's target search intent, in the page's language

### Step 6: Update WPCode Snippets

Two snippets must be updated whenever new pages are added to MU:

**Snippet #2867 — Cluster Interlinking:**
1. Navigate to `/wp-admin/admin.php?page=wpcode-snippet-manager&snippet_id=2867`
2. Access CodeMirror: `document.querySelector('.CodeMirror').CodeMirror`
3. Find the correct cluster section in the `$interlinking` array
4. Add new IT page IDs with 3-5 related IT page IDs each
5. Update the parent hub entry if needed
6. Save: `cm.save(); HTMLFormElement.prototype.submit.call(updateBtn.closest('form'));`
7. Verify: check for "Snippet aggiornato" notice

The interlinking snippet uses IT page IDs only — it resolves other languages via `pll_get_post()` at runtime.

**Snippet #2866 — E-E-A-T References:**
1. Navigate to `/wp-admin/admin.php?page=wpcode-snippet-manager&snippet_id=2866`
2. Add new IT page IDs with appropriate scientific reference keys
3. Reference keys are pre-defined in the snippet (e.g., `rippon2003`, `wiedemann2020`, `ncsu_exo`)
4. Save using the same form.submit() pattern

Read `references/snippet-update-patterns.md` for the available reference keys and which clusters they map to.

### Step 7: Cache Purge + Frontend Verification

**Purge LiteSpeed cache:**
```javascript
var purgeAll = document.querySelector('#wp-admin-bar-litespeed-menu a[href*="purge_all"]');
purgeAll.click();
```
Or from any admin page via the admin bar.

**Verification checklist — check one page per language:**
1. Navigate to `?page_id=XXXX` for a sample IT, EN, DE, FR page
2. Verify:
   - Correct title in `document.title`
   - Correct URL path (`/en/`, `/de/`, `/fr/` prefix)
   - Expected number of interactive elements (`.ck-check` count)
   - Interlinking section present (styled div with border-left)
   - References section present (styled div with border-left)
   - JS interactivity works (click checkboxes, score updates)

```javascript
// Quick verification script
var ckPage = document.getElementById('ck-ID');
var checks = ckPage ? ckPage.querySelectorAll('.ck-check').length : 0;
var divs = document.querySelectorAll('div[style]');
var sections = [];
divs.forEach(function(d) {
  var txt = d.textContent.substring(0, 50);
  if (txt.includes('INTERLINKING_HEADER')) sections.push('interlinking');
  if (txt.includes('REFERENCES_HEADER')) sections.push('references');
});
'checks:' + checks + ' | sections:' + sections.join(',');
```

Interlinking headers by language:
- IT: "Approfondimenti Correlati"
- EN: "Related In-Depth Content"
- DE: "Verwandte Vertiefungen"
- FR: "Approfondissements Connexes"

References headers by language:
- IT: "Fonti e Riferimenti"
- EN: "Sources and References"
- DE: "Quellen und Referenzen"
- FR: "Sources et Références"

## Post-Deployment

After successful verification:
1. **Update auto-memory** with new page IDs and deployment details
2. **Update interlinking memory** (`project_cluster_interlinking.md`) with new page count
3. **Update references memory** (`project_eeat_references.md`) if new source keys were added

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `wp.apiFetch` undefined | Not on a WP admin page | Navigate to `/wp-admin/index.php` |
| Content payload timeout | Content > 15KB | Use chunked `window._c` approach |
| Polylang AJAX returns `0` | Handler not saved to functions.php | Verify with `ta.value.includes('TEMP_PLL_HANDLER')` |
| Rank Math SEO silently fails | Using standard REST API | Switch to `/rankmath/v1/updateMeta` |
| WPCode changes not persisting | Using `button.click()` | Use `HTMLFormElement.prototype.submit.call(form)` |
| Frontend shows old content | LiteSpeed cache | Purge via admin bar |
| Interlinking not showing | Page ID missing from snippet #2867 | Add IT page ID to `$interlinking` array |

## Rate Limiting Awareness

Hostinger allows ~8-10 sequential API calls before potential timeout. For deployments of 20+ pages:
- Create pages in batches of 4-5 (one language at a time)
- Load content sequentially (2-3 chunks per page)
- SEO updates work fine in a sequential chain of 20
- Monitor for nonce expiry after ~15min of inactivity
