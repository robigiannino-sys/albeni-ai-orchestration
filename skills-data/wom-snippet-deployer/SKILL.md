---
name: wom-snippet-deployer
description: |
  **WoM WPCode Snippet Deployer**: Creates and deploys WPCode PHP snippets on World of Merino — interlinking, E-E-A-T widgets, routing bridges, and `the_content` filters. Full pipeline: WPCode form submission, PHP with Polylang resolution, priority/DOM ordering, design system, 4-language verification.
  - MANDATORY TRIGGERS: WoM snippet, WoM interlinking, WoM WPCode, create WPCode WoM, snippet worldofmerino, deploy interlinking WoM, WoM the_content, letture correlate WoM, cross-collection links, snippet #2063, snippet #1975, snippet #1976, snippet #1989, WoM satellite index
  - Also trigger when: user asks to create a PHP snippet on WoM, add cross-linking between WoM satellites, build a the_content filter for WoM, update the interlinking map with new WoM page IDs, or deploy automated content injection on World of Merino
---

# WoM WPCode Snippet Deployer

You are creating or updating WPCode PHP snippets on World of Merino (WoM) staging (`worldofmerino.com`). This skill encodes the proven pipeline for deploying `the_content` filter snippets that inject structured HTML sections into WoM satellite pages — interlinking boxes, author bylines, satellite indices, cross-domain bridges, and any future automated content injection.

## When to Use This Skill

Use this whenever you need to:
- **Create a new WPCode snippet** on WoM that uses `the_content` filter
- **Update an existing snippet's interlinking map** (e.g., add new page IDs to snippet #2063)
- **Build cross-collection or cross-page linking systems** on WoM
- **Manage DOM ordering** across multiple `the_content` snippets

This skill complements:
- `wom-page-deployer` — creates the actual pages (7-step pipeline); use that FIRST, then this skill to wire up interlinking
- `albeni-wp-operator` — general WP operations (one-off fixes, Polylang debugging)

## Active WoM Snippets (as of March 2026)

Understanding the existing snippet stack is essential — new snippets must fit into the priority chain without breaking DOM order.

| # | Snippet | Priority | Function | Scope |
|---|---------|----------|----------|-------|
| #1989 | E-E-A-T Author Byline | 5 | Author attribution box below title | All satellites |
| #2063 | Collection Interlinking | 8 | "Letture Correlate" cross-links box | 45 mapped satellites |
| #1975 | Satellite Index Grid | 10 | Child-page grid on Collection hubs | Hub pages only |
| #1976 | Soft Routing to MU | 12 | Cross-domain bridge CTA to MU | All satellites |

**DOM order on a typical satellite page:**
```
[Page Content]
  ↓ Byline (#1989, priority 5)
  ↓ Interlinking (#2063, priority 8)
  ↓ MU Bridge (#1976, priority 12)
```

**DOM order on a Collection hub page:**
```
[Page Content]
  ↓ Byline (#1989, priority 5)
  ↓ Satellite Index (#1975, priority 10)
  ↓ MU Bridge (#1976, priority 12)
```

When creating new snippets, choose a priority that maintains logical reading flow. The interlinking box at priority 8 sits between the author context (5) and the navigation/routing elements (10-12).

## Critical Knowledge

### WPCode Form Submission

WPCode uses its own form, NOT standard WP AJAX patterns. The correct approach:

```javascript
// Submit the WPCode snippet form
document.getElementById('wpcode-snippet-manager-form').submit();
```

**Do NOT use** `button.click()` or `jQuery` form submit — they often fail silently. The form ID is `wpcode-snippet-manager-form` (verified March 2026).

**Title field ID:** `wpcode_snippet_title` (not `wpcode-snippet-name`).

**Adding a new snippet requires two navigations:**
1. Go to `/wp-admin/admin.php?page=wpcode-snippet-manager&action=add`
2. This shows a snippet TYPE selection page — click "Aggiungi uno snippet personalizzato" (Add Custom Snippet) to reach the actual code editor

### Polylang English Slug is `en-us` on WoM

WoM uses `en-us` (with hyphen), NOT `en`. This affects:
- `pll_get_post($id, 'en-us')` — must use `en-us`
- `pll_current_language()` returns `en-us` for English pages
- Localized header arrays must key on `'en-us'` not `'en'`

### Unicode in Chrome JS Tool

`\u00xx` escapes are unreliable. Use `String.fromCharCode()`:
```javascript
// à=224, è=232, ù=249, ò=242, é=233, ä=228, ö=246, ü=252
var umlaut_u = String.fromCharCode(252); // ü
```

### WPCode AJAX Save (Alternative Method)

For updating EXISTING snippets programmatically (when you can't use form.submit), the WPCode AJAX endpoint works differently from standard WP. Navigate to the snippet edit page and use the form directly. For code that exceeds Chrome JS tool limits, build the code in `window._code` across multiple calls, then inject it into the CodeMirror editor:

```javascript
// After building window._code across chunks:
var cm = document.querySelector('.CodeMirror').CodeMirror;
cm.setValue(window._code);
// Then submit the form
document.getElementById('wpcode-snippet-manager-form').submit();
```

## The Snippet Deployment Pipeline

### Step 1: Plan the Snippet Architecture

Before writing code, determine:

1. **What pages does it target?** Build an exclusion list (homepages, hubs, author pages, etc.)
2. **What content does it inject?** Related links, metadata boxes, CTAs, etc.
3. **What priority?** Check the active snippet table above — pick a slot that maintains logical DOM order
4. **Does it need an interlinking map?** If yes, map IT page IDs to related IT page IDs (the snippet resolves to current language at runtime via `pll_get_post`)

### Step 2: Build the PHP Code

All WoM `the_content` snippets follow this architecture:

```php
add_filter('the_content', function($content) {
    // Gate: only singular pages, not admin
    if (!is_singular('page') || is_admin()) return $content;

    $page_id = get_the_ID();

    // Exclusion list: homepages, hubs, author pages, special pages
    $exclude = array(
        8, 539, 553, 541,    // IT/EN/DE/FR homepages
        54, 820, 557, 730,   // Heritage Archive hub (all langs)
        57, 679, 555, 724,   // Professionisti hub (all langs)
        58, 681, 556, 725,   // Sostenibilita hub (all langs)
        1977, 1978, 1979, 1980, // Author pages (all langs)
    );
    if (in_array($page_id, $exclude)) return $content;

    // Optional: require parent (satellites only)
    $parent = wp_get_post_parent_id($page_id);
    if (!$parent) return $content;

    // Get current language
    $lang = function_exists('pll_current_language') ? pll_current_language() : 'it';

    // Resolve current page to IT equivalent for map lookup
    $it_id = $page_id;
    if ($lang !== 'it' && function_exists('pll_get_post')) {
        $translated = pll_get_post($page_id, 'it');
        if ($translated) $it_id = $translated;
    }

    // === YOUR LOGIC HERE ===
    // Use $it_id to look up in your map
    // Use pll_get_post($ref_it_id, $lang) to resolve links to current language

    // Localized headers — MUST include 'en-us' key
    $headers = array(
        'it'    => 'Italian Header',
        'en-us' => 'English Header',
        'de'    => 'German Header',
        'fr'    => 'French Header',
    );
    $header = isset($headers[$lang]) ? $headers[$lang] : $headers['it'];

    // Build HTML + CSS
    $html = '<div class="wom-YOUR-SECTION">...</div>';
    $css = '<style>/* WoM design system styles */</style>';

    return $content . $css . $html;
}, PRIORITY_NUMBER);
```

**Key patterns:**
- **IT-first map lookup**: Always map IT page IDs → related IT page IDs. At runtime, resolve current page to its IT equivalent, look up in map, then resolve each related ID back to current language. This way the map only needs IT IDs.
- **Graceful multilingual fallback**: If `pll_get_post()` returns falsy for a target language, the link falls back to the IT version automatically (since `$target_id` starts as the IT ID).
- **Exclusion by all-language IDs**: Include all 4 language variants of excluded pages in the array, because `get_the_ID()` returns the actual page ID, not the IT equivalent.

### Step 3: Build the Interlinking Map (if applicable)

For interlinking snippets, organize the IT page ID map by thematic groups:

```php
$interlinking = array(
    // Heritage: Rules of Elegance
    372 => array(373, 374, 376, 199),
    373 => array(372, 379, 390, 1992),
    // ... group by sub-theme for maintainability

    // Professionisti: Travel & Business
    1886 => array(203, 502, 196, 1992),
    // ...

    // Sostenibilita: Wardrobe & Quality
    1888 => array(195, 382, 467, 1995),
    // ...
);
```

**Cross-collection bridges** are what make the interlinking valuable for topical authority. Each page should link to 2-3 pages in its own Collection + 1-2 pages in related Collections, connected by theme:
- Comfort pages in Heritage → skin-sensitivity pages in Sostenibilita
- Travel pages in Professionisti → packing pages in Heritage
- Capsule wardrobe in Heritage → fewer-items pages in Sostenibilita

Read `references/interlinking-map.md` for the complete current map with all 45 page entries.

### Step 4: Apply WoM Design System Styling

All WoM injected sections use the same design language:

```css
.wom-SECTION-NAME {
    margin: 2.5rem 0 1.5rem;
    padding: 1.5rem 1.8rem;
    background: linear-gradient(135deg, #FAF8F5 0%, #F5F0EB 100%);
    border-left: 4px solid #8B7355;
    border-radius: 0 8px 8px 0;
}
.wom-SECTION-NAME h3 {
    font-family: Playfair Display, Georgia, serif;
    color: #5C4A32;
    font-size: 1.15rem;
    margin: 0 0 .8rem;
    font-weight: 600;
}
.wom-SECTION-NAME ul { list-style: none; padding: 0; margin: 0; }
.wom-SECTION-NAME li {
    padding: .35rem 0;
    border-bottom: 1px solid rgba(139, 115, 85, .12);
}
.wom-SECTION-NAME li:last-child { border-bottom: none; }
.wom-SECTION-NAME a {
    color: #8B7355;
    text-decoration: none;
    font-size: .95rem;
    transition: color .2s;
}
.wom-SECTION-NAME a:hover {
    color: #5C4A32;
    text-decoration: underline;
}
```

**Design tokens:**
- Background: cream gradient `#FAF8F5` → `#F5F0EB`
- Accent: brown `#8B7355` (border, links)
- Dark accent: `#5C4A32` (headers, hover)
- Heading font: Playfair Display (serif)
- Body font: inherited from theme (system)
- Border-left: 4px solid brown
- Border-radius: 0 8px 8px 0 (rounded right side only)

### Step 5: Deploy via WPCode Admin

**For NEW snippets:**

1. Navigate to WPCode add page:
   ```
   /wp-admin/admin.php?page=wpcode-snippet-manager&action=add
   ```

2. Select "Aggiungi uno snippet personalizzato" (PHP Snippet type)

3. Build the PHP code in `window._code` across multiple Chrome JS calls (large snippets exceed single-call limits):
   ```javascript
   // Chunk 1: Opening + exclusions
   window._code = "add_filter('the_content', function($content) {\n";
   window._code += "    if (!is_singular('page') || is_admin()) return $content;\n";
   // ...

   // Chunk 2: Interlinking map (often the largest part)
   window._code += "    $interlinking = array(\n";
   window._code += "        372 => array(373, 374, 376, 199),\n";
   // ...

   // Chunk 3: Resolution logic + HTML + CSS
   window._code += "    // resolve links...\n";
   // ...
   ```

4. Inject into WPCode editor and set metadata:
   ```javascript
   // Set title
   document.getElementById('wpcode_snippet_title').value = 'WoM - Snippet Name';

   // Set code type to PHP (if not already)
   // The type selector may already be set from step 2

   // Inject code into CodeMirror
   var cm = document.querySelector('.CodeMirror').CodeMirror;
   cm.setValue(window._code);

   // Set insertion to "Everywhere" and activate
   // These are usually the defaults for new snippets
   ```

5. Submit the form:
   ```javascript
   document.getElementById('wpcode-snippet-manager-form').submit();
   ```

6. After page reloads, note the snippet ID from the URL (`?snippet_id=XXXX`)

**For UPDATING existing snippets:**

1. Navigate to the snippet edit page: `/wp-admin/admin.php?page=wpcode-snippet-manager&action=edit&snippet_id=2063`
2. Build updated code in `window._code` chunks
3. Inject via CodeMirror: `document.querySelector('.CodeMirror').CodeMirror.setValue(window._code);`
4. Submit: `document.getElementById('wpcode-snippet-manager-form').submit();`

### Step 6: Cache Purge + Frontend Verification

After deploying/updating a snippet, purge LiteSpeed cache on affected pages:

```javascript
(async () => {
    var nonceResp = await fetch('/wp-admin/admin-ajax.php?action=rest-nonce', {credentials: 'same-origin'});
    var nonce = await nonceResp.text();
    // Re-save a sample of affected pages to purge their cache
    var sampleIds = [372, 1886, 1888, 1990, 1992, 1994]; // one per group
    for (var i = 0; i < sampleIds.length; i++) {
        await fetch('/wp-json/wp/v2/pages/' + sampleIds[i], {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-WP-Nonce': nonce},
            body: JSON.stringify({status: 'publish'}),
            credentials: 'same-origin'
        });
        await new Promise(r => setTimeout(r, 200));
    }
})();
```

**Verify on frontend** — check that the injected section appears in correct DOM position with correct content:

```javascript
(async () => {
    var tests = [
        {path: '/le-5-regole-delleleganza-maschile/', lang: 'IT', expect: 'wom-interlinking'},
        {path: '/en-us/en-5-rules-of-mens-elegance/', lang: 'EN', expect: 'wom-interlinking'},
        {path: '/de/de-5-regeln-der-herreneleganz/', lang: 'DE', expect: 'wom-interlinking'},
        {path: '/fr/fr-5-regles-de-lelegance-masculine/', lang: 'FR', expect: 'wom-interlinking'},
        // Add TOFU pages
        {path: '/il-primo-strato/', lang: 'IT-TOFU', expect: 'wom-interlinking'},
        {path: '/en-us/en-the-first-layer/', lang: 'EN-TOFU', expect: 'wom-interlinking'},
    ];
    var results = [];
    for (var i = 0; i < tests.length; i++) {
        var t = tests[i];
        var resp = await fetch(t.path + '?ck=' + Date.now(), {cache: 'no-store'});
        var html = await resp.text();
        var hasSection = html.indexOf(t.expect) > -1;
        var linkCount = (html.match(new RegExp('class="' + t.expect + '"'), 'g') || []).length;
        // Check DOM order: byline before interlinking before bridge
        var bylinePos = html.indexOf('wom-byline');
        var interlinkPos = html.indexOf('wom-interlinking');
        var bridgePos = html.indexOf('wom-mu-bridge');
        var orderOk = (bylinePos < interlinkPos) && (interlinkPos < bridgePos);
        results.push(t.lang + ': ' + (hasSection ? 'PASS' : 'FAIL') + ' | DOM order: ' + (orderOk ? 'OK' : 'WRONG'));
        await new Promise(r => setTimeout(r, 200));
    }
    return results.join('\n');
})();
```

**Expected:** All pages show PASS + DOM order OK. If a page shows FAIL, check:
1. Is the page ID in the exclusion list? (shouldn't be for satellites)
2. Is the IT equivalent ID in the interlinking map?
3. Has LiteSpeed cache been purged?

## WoM Site Reference

| Property | Value |
|----------|-------|
| Production URL | `worldofmerino.com` |
| Production URL | `worldofmerino.com` |
| Theme | `twentytwentyfive-child` |
| Polylang EN slug | `en-us` (NOT `en`) |
| WPCode form ID | `wpcode-snippet-manager-form` |
| WPCode title field | `wpcode_snippet_title` |

### Collection Hub IDs (excluded from satellites-only snippets)

| Collection | IT | EN | DE | FR |
|-----------|-----|-----|-----|-----|
| Heritage Archive | 54 | 820 | 557 | 730 |
| Professionisti in Movimento | 57 | 679 | 555 | 724 |
| Sostenibilita Oltre le Promesse | 58 | 681 | 556 | 725 |

### Homepage IDs

| Lang | ID |
|------|-----|
| IT | 8 |
| EN | 539 |
| DE | 553 |
| FR | 541 |

### Author Page IDs

| Lang | ID |
|------|------|
| IT | 1977 |
| EN | 1978 |
| DE | 1979 |
| FR | 1980 |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `wpcode-snippet-manager-form` not found | On type-selection page, not editor | Click "Aggiungi uno snippet personalizzato" first |
| `wpcode_snippet_title` returns null | Wrong field ID or not on editor page | Verify you're on the snippet editor, not the list |
| CodeMirror.setValue() throws TypeError | `.CodeMirror` not initialized yet | Wait for page load; use `setTimeout` wrapper |
| Snippet saves but doesn't appear on frontend | Snippet set to Inactive | Check "Attivo/Inattivo" toggle on snippet page |
| Links resolve to IT pages on EN/DE/FR | `pll_get_post` returning false | Target page may not have that language version; check Polylang translation group |
| DOM order wrong (bridge before interlinking) | Priority numbers inverted | Check `add_filter` priority: lower number = earlier in DOM |
| Interlinking box doesn't appear on new TOFU page | IT page ID missing from `$interlinking` array | Add the IT ID with 4 related IT IDs to snippet #2063 |
| `window._code` gets truncated | Chrome JS tool payload limit | Split into more/smaller chunks (max ~3KB per call) |
