---
name: wom-page-deployer
description: |
  **WoM Page Deployer**: Deploys new content pages (guides, articles, stories, lifestyle content) across all 4 languages (IT/EN/DE/FR) on the World of Merino WordPress production site. Handles the complete pipeline: Gutenberg content creation via REST API, Polylang language assignment via Quick Edit, translation group linking via PHP snippet in functions.php, Rank Math SEO metadata, LiteSpeed cache purge, and hreflang/language-switcher verification.
  - MANDATORY TRIGGERS: deploy WoM, deploy World of Merino, crea pagine WoM, new WoM pages, WoM guide, WoM stories, deploy worldofmerino, nuove pagine WoM, WoM content pages, pagine worldofmerino, deploy TOFU pages, WoM 4 lingue
  - Also trigger when: user asks to create new pages on WoM production, deploy lifestyle/brand content across languages on World of Merino, create guides/articles for behavioral clusters on WoM, implement TOFU content pages on worldofmerino.com, or batch-create multilingual blog/guide pages on worldofmerino.com
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

# WoM Page Deployer

You are deploying new content pages to World of Merino (WoM) production site (`worldofmerino.com`). This skill encodes the proven 7-step deployment pipeline learned through extensive trial-and-error. It reliably creates, translates, links, and verifies multilingual TOFU content pages.

## When to Use This Skill

Use this whenever you need to create NEW pages on WoM — whether they're lifestyle guides, brand stories, cluster-targeted articles, or any TOFU content. The pipeline deploys across all 4 languages simultaneously but works for single-language pages too.

This skill complements:
- `albeni-wp-operator` — general WP operations (individual fixes, Polylang debugging, SEO updates)
- `mu-content-deployer` — Merino University pages (interactive checklists, scorecards, educational content)

Use this skill specifically for the **end-to-end deployment pipeline** of new content pages on WoM.

## Critical Knowledge (Learned the Hard Way)

### Polylang English Slug is `en-us` on WoM

**WoM uses `en-us` (with hyphen) for English.** This differs from MU which uses `en`. Using the wrong slug silently fails — `pll_set_post_language()` returns no error but the language isn't set, and `pll_save_post_translations()` silently drops that language from the group.

| Language | Polylang slug | URL prefix | Example path |
|----------|--------------|------------|-------------|
| Italian  | `it`         | (none)     | `/dal-volo-alla-riunione/` |
| English  | `en-us`      | `/en-us/`  | `/en-us/en-from-flight-to-meeting/` |
| German   | `de`         | `/de/`     | `/de/de-vom-flug-zum-meeting/` |
| French   | `fr`         | `/fr/`     | `/fr/fr-du-vol-a-la-reunion/` |

### Slug Convention

- IT: `dal-volo-alla-riunione` (no prefix, no language tag)
- EN: `en-from-flight-to-meeting` (`en-` prefix in slug, served under `/en-us/` path)
- DE: `de-vom-flug-zum-meeting` (`de-` prefix)
- FR: `fr-du-vol-a-la-reunion` (`fr-` prefix)

### Quick Edit is the Reliable Method for Setting Languages

REST API `POST /wp-json/wp/v2/pages` does NOT set Polylang language — the Polylang metabox is silently ignored. The reliable method is **Quick Edit** via admin-ajax with `inline_lang_choice`.

### Rank Math SEO — Use the Dedicated Endpoint

The WP REST API silently ignores Rank Math meta fields. Always use `/wp-json/rankmath/v1/updateMeta`.

### Theme Editor Save Uses AJAX, Not Form Submit

The WP theme editor (since 4.9) saves via `action=edit-theme-plugin-file`, NOT via `form.submit()`. The nonce lives in `#template input[name="nonce"]`. This AJAX call can be slow on Hostinger (30-60s) — use fire-and-forget XHR and verify by reloading afterward.

### LiteSpeed Cache Purge via Page Re-save

Query string cache-busting (`?v=timestamp`) does NOT bypass LiteSpeed server cache. To purge, re-save the page via REST API `POST /wp-json/wp/v2/pages/{id}` with `{status: 'publish'}`.

### Rate Limiting on Hostinger

Hostinger allows ~8-10 sequential API calls before potential timeout. For deployments of 12+ pages:
- Create pages in batches of 3-4 (one language at a time)
- Add 300-500ms delay between calls
- Monitor for nonce expiry after ~15min of inactivity
- If nonce returns `"0"`, session expired — navigate to `/wp-admin/` and re-authenticate

### Unicode in Chrome JS Tool

`\u00xx` escape sequences are unreliable in the Chrome JS tool. Always use `String.fromCharCode()`:
```javascript
// Italian: à=224, è=232, ù=249, ò=242, é=233
// German: ä=228, ö=246, ü=252, ß=223, Ä=196, Ö=214, Ü=220
// French: é=233, è=232, ê=234, ç=231, â=226, ô=244, î=238, ë=235
// Punctuation: —=8212 (em dash), →=8594 (arrow)
var e_grave = String.fromCharCode(232);  // è
```

## Pre-Flight Checklist

Before starting, confirm you have:

1. **Three Chrome tabs open on WoM admin:**
   - **Nonce tab**: `/wp-admin/admin-ajax.php?action=rest-nonce`
   - **Theme editor**: `/wp-admin/theme-editor.php?theme=twentytwentyfive-child&file=functions.php`
   - **Pages list**: `/wp-admin/edit.php?post_type=page` (for Quick Edit nonce)
2. **Content ready** in all 4 languages (or at minimum IT as master copy)
3. **Page IDs for interlinking** — related existing pages to cross-link (if applicable)

Check `wp.apiFetch` availability on any admin tab:
```javascript
typeof wp !== 'undefined' && wp.apiFetch ? 'available' : 'not available'
```

## The 7-Step Pipeline

### Step 1: Generate Content (Gutenberg Blocks)

WoM pages use standard Gutenberg blocks (not the `<!-- wp:html -->` monoblocks used on MU for interactive content). The typical structure for a guide/article:

```html
<!-- wp:paragraph {"className":"lead"} -->
<p class="lead">Lead paragraph introducing the topic — engaging, TOFU-style.</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">Section Heading</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Body text paragraph with lifestyle/brand content.</p>
<!-- /wp:paragraph -->

<!-- wp:separator {"className":"is-style-wide"} -->
<hr class="wp-block-separator has-alpha-channel-opacity is-style-wide"/>
<!-- /wp:separator -->
```

**For large content payloads (>5KB)**, use the chunked loading pattern from MU: cache shared elements in `window._css` or `window._base`, build content incrementally in `window._c` across multiple JS calls, then push to WP in one save call. This avoids Chrome JS tool payload limits.

```javascript
// Chunk 1: Lead + first section
window._c = '<!-- wp:paragraph {"className":"lead"} -->\n<p class="lead">...</p>\n<!-- /wp:paragraph -->\n';
window._c += '<!-- wp:heading -->\n<h2 class="wp-block-heading">...</h2>\n<!-- /wp:heading -->\n';

// Chunk 2: More sections
window._c += '<!-- wp:paragraph -->\n<p>...</p>\n<!-- /wp:paragraph -->\n';

// Final push
wp.apiFetch({path:'/wp/v2/pages/PAGE_ID', method:'POST', data:{content: window._c, status:'publish'}});
```

Read `references/content-templates.md` for WoM-specific TOFU content templates by cluster.

### Step 2: Batch Create Pages

Create all pages at once from any WP admin tab. Prefer `wp.apiFetch` (handles nonces automatically) over raw `fetch` when available.

**Pattern — one language at a time (3-5 pages per batch):**

```javascript
var pages = [
  {title:'Dal Volo alla Riunione', slug:'dal-volo-alla-riunione'},
  {title:'Come Scegliere una T-shirt Premium', slug:'come-scegliere-tshirt-premium'}
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
        content: '<!-- wp:paragraph --><p>Loading...</p><!-- /wp:paragraph -->'
      }
    });
  }).then(function(r) { window._ids.push(r.id); });
});
chain.then(function() { window._createResult = 'OK:' + window._ids.join(','); });
```

**Repeat for EN, DE, FR** with localized titles and slugs.

**Record ALL page IDs immediately** — you need them for every subsequent step. Organize them in a mapping:
```javascript
window._pageMap = {
  guide1: {it: 1886, en: 1892, de: 1895, fr: 1898},
  guide2: {it: 1887, en: 1893, de: 1896, fr: 1899},
  guide3: {it: 1888, en: 1894, de: 1897, fr: 1900}
};
```

### Step 3: Assign Polylang Languages via Quick Edit

Navigate to the pages list tab and get the Quick Edit nonce, then batch-set languages for ALL pages (including IT):

```javascript
(async () => {
  var inlineNonce = document.getElementById('_inline_edit').value;

  var assignments = [
    // IT pages — set explicitly, REST API does NOT auto-assign
    {id: 1886, lang: 'it'}, {id: 1887, lang: 'it'}, {id: 1888, lang: 'it'},
    // EN pages — MUST use 'en-us' not 'en'
    {id: 1892, lang: 'en-us'}, {id: 1893, lang: 'en-us'}, {id: 1894, lang: 'en-us'},
    // DE pages
    {id: 1895, lang: 'de'}, {id: 1896, lang: 'de'}, {id: 1897, lang: 'de'},
    // FR pages
    {id: 1898, lang: 'fr'}, {id: 1899, lang: 'fr'}, {id: 1900, lang: 'fr'},
  ];

  var results = [];
  for (var i = 0; i < assignments.length; i++) {
    var a = assignments[i];
    var formData = new URLSearchParams();
    formData.append('action', 'inline-save');
    formData.append('post_type', 'page');
    formData.append('post_ID', a.id);
    formData.append('_inline_edit', inlineNonce);
    formData.append('inline_lang_choice', a.lang);
    formData.append('_status', 'publish');
    formData.append('post_status', 'publish');

    var resp = await fetch('/wp-admin/admin-ajax.php', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: formData.toString(),
      credentials: 'same-origin'
    });
    var text = await resp.text();
    var ok = text.length > 100;
    results.push(a.id + '(' + a.lang + '): ' + (ok ? 'OK' : 'FAIL'));
    await new Promise(function(r) { setTimeout(r, 300); });
  }
  return results.join('\n');
})();
```

Pages created via REST API appear as Italian in the admin but aren't actually tagged in Polylang's taxonomy — always set ALL pages explicitly.

### Step 4: Link Translation Groups via PHP Snippet

Polylang translation linking requires `pll_save_post_translations()` which is only available in PHP. The proven method is a temporary snippet in `functions.php` triggered via frontend fetch with cache bypass.

**Step 4a — Navigate to theme editor and record baseline:**
```javascript
var cm = document.querySelector('.CodeMirror').CodeMirror;
var baseContent = cm.getValue();
window._baselineLength = baseContent.length;  // SAVE for cleanup
```

**Step 4b — Build and append the temporary snippet:**

The snippet uses `template_redirect` hook (not `wp_ajax_`) because it's simpler and doesn't require a separate AJAX call to trigger. It's gated by a query parameter so it only fires when explicitly requested.

```javascript
var fixSnippet = '\n// TEMP: Fix Polylang translations\n'
+ "add_action('template_redirect', function() {\n"
+ "    if (!isset($_GET['pll_fix']) || $_GET['pll_fix'] !== 'run') return;\n"
+ "    header('Content-Type: text/plain');\n\n"
+ "    $lang_map = array(\n"
+ "        1886 => 'it', 1887 => 'it', 1888 => 'it',\n"
+ "        1892 => 'en-us', 1893 => 'en-us', 1894 => 'en-us',\n"
+ "        1895 => 'de', 1896 => 'de', 1897 => 'de',\n"
+ "        1898 => 'fr', 1899 => 'fr', 1900 => 'fr',\n"
+ "    );\n\n"
+ "    foreach ($lang_map as $pid => $lang) {\n"
+ "        pll_set_post_language($pid, $lang);\n"
+ "        $check = pll_get_post_language($pid);\n"
+ "        echo \"Set page $pid to $lang => got: $check\\n\";\n"
+ "    }\n\n"
+ "    echo \"\\n--- Linking translation groups ---\\n\";\n\n"
+ "    $g1 = array('it' => 1886, 'en-us' => 1892, 'de' => 1895, 'fr' => 1898);\n"
+ "    pll_save_post_translations($g1);\n"
+ "    echo 'Group 1: '; print_r(pll_get_post_translations(1886));\n\n"
+ "    $g2 = array('it' => 1887, 'en-us' => 1893, 'de' => 1896, 'fr' => 1899);\n"
+ "    pll_save_post_translations($g2);\n"
+ "    echo 'Group 2: '; print_r(pll_get_post_translations(1887));\n\n"
+ "    $g3 = array('it' => 1888, 'en-us' => 1894, 'de' => 1897, 'fr' => 1900);\n"
+ "    pll_save_post_translations($g3);\n"
+ "    echo 'Group 3: '; print_r(pll_get_post_translations(1888));\n\n"
+ "    exit;\n"
+ "});\n";

var newContent = baseContent + fixSnippet;
cm.setValue(newContent);
document.getElementById('newcontent').value = newContent;
```

**Step 4c — Save via theme editor AJAX (fire-and-forget):**
```javascript
var nonce = document.querySelector('#template input[name="nonce"]').value;
var xhr = new XMLHttpRequest();
xhr.open('POST', '/wp-admin/admin-ajax.php', true);
xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
xhr.onload = function() { window._saveResult = xhr.status + ': ' + xhr.responseText.substring(0,100); };
var params = 'action=edit-theme-plugin-file&nonce=' + encodeURIComponent(nonce)
  + '&file=functions.php&theme=twentytwentyfive-child&newcontent=' + encodeURIComponent(newContent);
xhr.send(params);
```

**Important**: This call can be slow (30-60s on Hostinger). Reload the editor afterward and verify the file contains `pll_fix` before triggering.

**Step 4d — Trigger the snippet (from nonce tab):**
```javascript
(async () => {
  var resp = await fetch('/?pll_fix=run&v=' + Date.now(), {cache: 'no-store'});
  return await resp.text();
})();
```

**Expected output**: Each page shows `Set page XXXX to LANG => got: LANG` (all matching), and each group shows all 4 languages in the translation array. If any EN page shows `got:` (empty), the slug is wrong — must be `'en-us'` not `'en'`.

**Step 4e — CRITICAL: Remove snippet and restore functions.php:**
```javascript
var cm = document.querySelector('.CodeMirror').CodeMirror;
var content = cm.getValue();
var tempIdx = content.indexOf('// TEMP:');
if (tempIdx > -1) {
  var clean = content.substring(0, tempIdx).trimEnd() + '\n';
  cm.setValue(clean);
  document.getElementById('newcontent').value = clean;
  // Save clean version via same AJAX pattern as 4c
}
```

Verify the restored file has no `TEMP` or `pll_fix` markers. Clean file length for WoM `twentytwentyfive-child/functions.php`: **~16,773 chars** (as of March 2026).

### Step 5: Set Rank Math SEO for All Pages

Batch-set SEO metadata using the recursive callback pattern (more resilient than simple for-loop for large batches):

```javascript
window._seo = [
  {id: 1886, title: 'SEO Title IT | World of Merino', desc: 'Description under 155 chars', focus: 'keyword IT'},
  {id: 1892, title: 'SEO Title EN | World of Merino', desc: 'Description EN', focus: 'keyword EN'},
  // ... all pages, all languages
];

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
- **Title**: Primary keyword + compelling descriptor, under 60 chars, append `| World of Merino`
- **Description**: What the page offers + why it matters, under 155 chars
- **Focus keyword**: 2-4 word phrase matching target search intent, in the page's own language

### Step 6: Cache Purge + Frontend Verification

**Purge cache** by re-saving each page via REST API:
```javascript
(async () => {
  var nonceResp = await fetch('/wp-admin/admin-ajax.php?action=rest-nonce', {credentials: 'same-origin'});
  var nonce = await nonceResp.text();
  var allIds = [1886, 1887, 1888, 1892, 1893, 1894, 1895, 1896, 1897, 1898, 1899, 1900];
  for (var i = 0; i < allIds.length; i++) {
    await fetch('/wp-json/wp/v2/pages/' + allIds[i], {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-WP-Nonce': nonce},
      body: JSON.stringify({status: 'publish'}),
      credentials: 'same-origin'
    });
    await new Promise(function(r) { setTimeout(r, 200); });
  }
})();
```

**Verification — fetch each page and check hreflang + language switcher:**
```javascript
(async () => {
  var pages = [
    {id: 1886, path: '/dal-volo-alla-riunione/', lang: 'IT'},
    {id: 1892, path: '/en-us/en-from-flight-to-meeting/', lang: 'EN'},
    {id: 1895, path: '/de/de-vom-flug-zum-meeting/', lang: 'DE'},
    {id: 1898, path: '/fr/fr-du-vol-a-la-reunion/', lang: 'FR'},
    // ... all pages
  ];
  var results = [];
  for (var i = 0; i < pages.length; i++) {
    var p = pages[i];
    var resp = await fetch(p.path + '?ck=' + Date.now(), {cache: 'no-store'});
    var html = await resp.text();
    var hreflangs = (html.match(/hreflang/g) || []).length;
    var langItems = (html.match(/lang-item/g) || []).length;
    results.push(p.id + ' ' + p.lang + ' => ' + resp.status + ' | hreflang:' + hreflangs + ' | switcher:' + langItems);
    await new Promise(function(r) { setTimeout(r, 200); });
  }
  return results.join('\n');
})();
```

**Expected results per page:**

| Check | Expected | Notes |
|-------|----------|-------|
| HTTP status | 200 | 404 = slug wrong or page not published |
| hreflang count | 4+ | 4 from Polylang; IT pages may show 8 (cross-domain canonical rewrite adds extras) |
| lang-item count | 6 | Language switcher entries for all configured WoM languages |

### Step 7: Post-Deployment

After successful verification:

1. **Update auto-memory** with new page IDs and deployment details
2. **Update conformity report** (`project_conformity_report_mar2026.md`) if pages were part of a conformity audit item
3. **Update Notion** content pipeline if tracking deployments there (see `reference_notion_workspace.md`)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `wp.apiFetch` undefined | Not on a WP admin page | Navigate to `/wp-admin/index.php` |
| Quick Edit returns short response (<100 chars) | Nonce expired | Reload pages list, get fresh `_inline_edit` nonce |
| `pll_set_post_language` returns empty for EN | Using `'en'` instead of `'en-us'` | **Always** use `'en-us'` for English on WoM |
| `pll_save_post_translations` drops EN from group | EN pages don't have language set | Set EN language first (Quick Edit), then re-run translation linking |
| Rank Math SEO silently fails | Using standard REST API `/wp/v2/pages` | Use `/rankmath/v1/updateMeta` endpoint |
| Hreflang missing on one page | LiteSpeed cache | Re-save page via REST API, re-fetch with `{cache:'no-store'}` |
| Theme editor save hangs (XHR timeout) | Hostinger slow response | Save usually completes anyway — reload editor and verify content |
| Content with è/ä/ç garbled | `\u` escapes transformed by Chrome tool | Use `String.fromCharCode()` instead |
| Frontend shows old content after changes | LiteSpeed cache | Purge all via admin bar or re-save each page |
| Nonce returns `"0"` | WP session expired | Navigate to `/wp-admin/` and re-login |

## WoM Site Reference

| Property | Value |
|----------|-------|
| Production URL | `worldofmerino.com` |
| Production URL | `worldofmerino.com` |
| Theme | `twentytwentyfive-child` |
| functions.php clean length | ~16,773 chars (March 2026) |
| Polylang EN slug | `en-us` (NOT `en`) |
| Content type | TOFU: lifestyle guides, brand stories, cluster articles |
| Cross-domain role | Top-of-funnel → links to MU (MOFU) and PMS/Albeni (BOFU) |
| CTA target | `albeni1905.com` (BOFU commercial) |
