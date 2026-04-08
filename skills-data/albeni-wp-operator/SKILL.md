---
name: albeni-wp-operator
description: |
  **Albeni 1905 WordPress Operator**: Manages the Albeni/Merino University multi-language WordPress ecosystem on Hostinger. Covers WP REST API, Rank Math SEO, Polylang, Gutenberg, HTML widgets, field_notes CPT, canonical/hreflang cross-domain, WPCode snippets, LiteSpeed cache, FSE templates, and deployment across IT/EN/DE/FR.
  - MANDATORY TRIGGERS: WordPress, WP, Gutenberg, Rank Math, Polylang, SEO meta, focus keyword, staging, front end, pagina, pagine, blocchi, widget, deploy, traduzione pagine, language switcher, field_notes, note di campo, pll_get_post, translation group, canonical, hreflang, WPCode, snippet, FAQ, redirect, LiteSpeed, cache, footer, template part, Schema.org
  - Also trigger when: user asks to update/create/fix WordPress pages, translate page content, fix broken links, apply SEO metadata, build HTML widgets, manage multilingual content on merinouniversity.com, debug redirects, edit FSE templates, or deploy structured data
---

# Albeni 1905 — WordPress Operator

You are the operational agent for the Albeni 1905 "Invisible Luxury" WordPress ecosystem. This skill encodes battle-tested patterns learned through extensive trial-and-error across hundreds of API calls, page builds, and multilingual deployments.

## The Ecosystem

### WordPress Sites (Production)
- **World of Merino (WoM)**: `worldofmerino.com` (Hostinger) — blog/stories site
- **Merino University (MU)**: `merinouniversity.com` (Hostinger) — educational pages
- **Production**: `merinouniversity.com` (custom React frontend — NOT WordPress)
- **Languages**: IT (master), EN, DE, FR via Polylang
- **SEO Plugin**: Rank Math
- **Editor**: Gutenberg (Block Editor)
- **MU Pages**: ~172 published across 4 languages
- **WoM Stories**: 11 story groups × 4 languages = 44 posts

### Polylang Language Slugs — DIFFER PER SITE

**CRITICAL: WoM and MU use DIFFERENT Polylang language slugs for English.**

**WoM (worldofmerino.com):**
- IT: `it`, EN: `en-us` (note the hyphen), DE: `de`, FR: `fr`

**MU (merinouniversity.com):**
- IT: `it`, EN: `en` (NOT `en-us`!), DE: `de`, FR: `fr`

Always verify with `PLL()->model->get_languages_list()` before writing any Polylang handler. Using the wrong slug silently fails — `pll_set_post_language()` returns no error but the language isn't set.

**URL Prefix vs Internal Slug (MU site):**
On MU:
- IT pages: no prefix (root) → `/faq/`, `/department-material-science/`
- EN pages: `/en/` prefix → `/en/en-faq/`, `/en/en-department-material-science/`
- DE pages: `/de/` prefix → `/de/de-faq/`, `/de/de-department-material-science/`
- FR pages: `/fr/` prefix → `/fr/fr-faq/`, `/fr/fr-departement-science-matieres/`

When using `pll_current_language('slug')` in PHP filters on MU, it returns `en` (NOT `en-us`). When using `pll_set_post_language()`, use the internal slug (`en-us` on WoM, `en` on MU). This discrepancy caused bugs in multiple sessions — the `$map` array keys must match what `pll_current_language()` returns, not the Polylang admin slug.

### MU Polylang Settings (March 2026)
- `force_lang`: 1 (directory-based URLs: /en/, /de/, /fr/)
- `hide_default`: true (IT pages have no prefix)
- `browser`: false (browser language detection OFF)
- `redirect_lang`: false (language redirect OFF)

### Multi-Domain Ecosystem
The Albeni 1905 ecosystem spans 4 domains with distinct funnel roles:
- **worldofmerino.com** (WoM) — TOFU: blog, stories, brand awareness
- **merinouniversity.com** (MU) — MOFU: educational content, authority building
- **perfectmerinoshirt.com** (PMS) — BOFU tech: product-focused, technical specs (Hostinger Horizons SPA, no WP)
- **albeni1905.com** — BOFU commercial: e-commerce, conversions (currently unreachable as of Mar 2026)

Each domain has unique content (no duplicate content across domains). Cross-domain links use `target="_blank" rel="noopener"` but historically had no SEO signals. The canonical cross-domain snippet (ID 2493) now rewrites staging URLs to production.

## Before Any Operation

**Option A — Manual nonce (works from any tab):**
1. **Get a fresh nonce**: `fetch('/wp-admin/admin-ajax.php?action=rest-nonce').then(r=>r.text())`
2. **Store it**: `window._nonce = nonce`
3. **Test the connection**: `fetch('/wp-json/wp/v2/pages?per_page=1&_fields=id', {headers:{'X-WP-Nonce':nonce}})`
4. If nonce returns `"0"` or fetch fails with TypeError → session expired → navigate to `/wp-admin/` and re-login

**Option B — `wp.apiFetch` (simpler, available on WP admin pages):**
On any WP admin page, `wp.apiFetch` is globally available and handles nonces automatically:
```javascript
const page = await wp.apiFetch({path: '/wp/v2/pages/123?context=edit'});
await wp.apiFetch({path: '/wp/v2/pages/123', method: 'PUT', data: {content: newContent}});
```
Check availability: `typeof wp !== 'undefined' && wp.apiFetch ? 'available' : 'not available'`

Note: `wpApiSettings.nonce` may NOT be defined even when `wp.apiFetch` works (it uses a different nonce mechanism). Always prefer `wp.apiFetch` on admin pages.

## Critical Rules (Learned the Hard Way)

### Unicode Escapes in JS Tool Are Unreliable

**CRITICAL**: When using the Chrome extension JS tool, `\u00xx` escape sequences in string literals may be transformed by the tool before reaching the browser. This causes `split().join()` text replacements to silently fail (no match = no replacement, no error).

**Workaround — ALWAYS use `String.fromCharCode()` for non-ASCII characters:**
```javascript
// WRONG — \u escapes may be transformed by the tool
var text = 'qualit\u00e0 sartoriale';  // may not match actual content

// CORRECT — fromCharCode always produces the right character
var a_grave = String.fromCharCode(224);  // à
var text = 'qualit' + a_grave + ' sartoriale';  // guaranteed match
```

Common character codes needed:
```javascript
// Italian
var a_grave = String.fromCharCode(224);  // à
var e_grave = String.fromCharCode(232);  // è
var u_grave = String.fromCharCode(249);  // ù
var o_grave = String.fromCharCode(242);  // ò
var e_acute = String.fromCharCode(233);  // é
var A_grave = String.fromCharCode(192);  // À
var U_grave = String.fromCharCode(217);  // Ù (used in "PIÙ")

// German
var ae = String.fromCharCode(228);       // ä
var oe = String.fromCharCode(246);       // ö
var ue = String.fromCharCode(252);       // ü
var Ae = String.fromCharCode(196);       // Ä
var Oe = String.fromCharCode(214);       // Ö
var Ue = String.fromCharCode(220);       // Ü
var ss = String.fromCharCode(223);       // ß
var glq = String.fromCharCode(8222);     // „ (German opening quote)
var grq = String.fromCharCode(8220);     // " (German closing quote)

// Universal
var md = String.fromCharCode(8212);      // — (em dash)
var arrow = String.fromCharCode(8594);   // →
```

### Block-by-Block Translation Pattern (Preferred Method)

Instead of trying to match and replace long text strings (which fails due to encoding issues), use positional replacement on individual blocks:

```javascript
// Step 1: Split IT content into blocks
var blocks = itRaw.split(/(?=<!-- wp:)/);

// Step 2: Define helper functions
function replaceInnerP(block, newText) {
  var openP = block.indexOf('<p');
  var closeTag = block.indexOf('>', openP);
  var closeP = block.indexOf('</p>');
  return block.substring(0, closeTag+1) + newText + block.substring(closeP);
}
function replaceInnerH(block, newText) {
  var m = block.match(/(<h\d[^>]*>)([\s\S]*?)(<\/h\d>)/);
  if (m) return block.replace(m[0], m[1] + newText + m[3]);
  return block;
}
function replaceQuoteP(block, newText) {
  var m = block.match(/<p>([\s\S]*?)<\/p>/);
  if (m) return block.replace(m[1], newText);
  return block;
}

// Step 3: Translate each block by type
enBlocks[0] = replaceInnerP(enBlocks[0], 'English text here');
enBlocks[2] = replaceInnerH(enBlocks[2], 'English heading');
enBlocks[5] = replaceQuoteP(enBlocks[5], 'English quote text');
// Separators, groups: keep as-is

// Step 4: For HTML blocks (Klaviyo, CTA), use split().join() with fromCharCode
var b = enBlocks[23];
b = b.split('Italian text').join('English text');
enBlocks[23] = b;

// Step 5: Assemble
var finalEN = enBlocks.join('');
```

This approach works because:
- `replaceInnerP` finds the `<p>` tag by position, not by text content
- No need to match the exact Italian text (avoids encoding issues)
- Block structure (Gutenberg comments, attributes, styles) is preserved perfectly

### Rank Math SEO — The Silent Failure

The WP REST API **silently ignores** Rank Math meta fields. This PUT returns 200 OK but saves NOTHING:
```javascript
// WRONG — will be silently ignored
fetch('/wp-json/wp/v2/pages/123', {
  body: JSON.stringify({meta: {rank_math_focus_keyword: 'test'}})
})
```

Use the Rank Math dedicated endpoint instead:
```javascript
// CORRECT — this actually works
fetch('/wp-json/rankmath/v1/updateMeta', {
  method: 'POST',
  headers: {'Content-Type':'application/json', 'X-WP-Nonce': nonce},
  body: JSON.stringify({
    objectID: 123,
    objectType: 'post',
    meta: {
      rank_math_focus_keyword: 'your keyword',
      rank_math_title: 'Your Title | Brand',
      rank_math_description: 'Your meta description under 155 chars.'
    }
  })
})
```

### Polylang — The Duplicate Trap

Polylang creates **shadow pages** that the language switcher uses. These are DIFFERENT from the canonical pages you see in the admin list.

**CRITICAL**: NEVER use generic search queries to find Polylang duplicates. This caused a catastrophic overwrite of 22 unrelated pages in a previous session.

**SAFE pattern:**
```javascript
fetch('/wp-json/wp/v2/pages?slug=fr-analyse-cycle-vie&status=any')
```

### Polylang Translation Linking — The ONLY Reliable Method

After extensive trial and error (5+ failed approaches), the ONLY reliable way to fix Polylang translation links is via PHP, using a temporary AJAX handler added to `functions.php`:

```php
// Add temporarily to functions.php as an AJAX handler
add_action('wp_ajax_fix_pll_translations', function() {
    if (!function_exists('pll_save_post_translations')) {
        wp_send_json(array('error' => 'Polylang not available'));
        return;
    }
    $group = array('it'=>64, 'en-us'=>673, 'de'=>361, 'fr'=>763);
    foreach ($group as $slug => $pid) {
        pll_set_post_language($pid, $slug);
    }
    pll_save_post_translations($group);
    wp_send_json(pll_get_post_translations($group['it']));
});
```

Then trigger via: `fetch('/wp-admin/admin-ajax.php?action=fix_pll_translations', {credentials:'include'})`

**What does NOT work:**
- WP REST API meta fields for Polylang → silently ignored
- WPCode Lite snippets → unreliable execution, "Run Now" is Pro-only
- PHP snippets in "Header per l'intero sito" mode → NEVER execute in admin context
- Direct `wp_update_post` with Polylang meta → race conditions

**Remember to remove the AJAX handler from functions.php after use.** Always verify the file length returns to its clean state:
- **WoM** twentytwentyfive-child: **14749 chars** (as of March 2026)
- **MU** twentytwentyfive (NOT child theme): **8295 chars** (as of March 2026)

### Polylang — Cross-Post-Type Translation Linking

Polylang's `pll_save_post_translations()` can link posts across DIFFERENT post types (e.g., a `field_notes` CPT post to a `page`). This is essential when a custom post type (like `field_notes`) needs its language switcher to point to page-type translations in other languages.

**The pattern:**
```php
// Link a field_note (IT) to page translations in EN/FR/DE
$trans = array(
    'it' => 84,      // field_notes post ID
    'en-us' => 1459, // page post ID
    'fr' => 1476,    // page post ID
    'de' => 414      // page post ID
);
pll_set_post_language(84, 'it');
pll_save_post_translations($trans);
```

**The stale translation group trap:** If the target page IDs already belong to an existing translation group (e.g., the page 390 → 1459/1476/414 group), `pll_save_post_translations` may attach your post to that OLD group instead of creating a clean mapping. The field_note then inherits the page's translation group, and `pll_get_post()` returns wrong IDs.

**The fix — always clear old term relationships first:**
```php
// Step 1: Remove from any existing (wrong) translation group
wp_delete_object_term_relationships($fn_id, 'post_translations');

// Step 2: Set language fresh
pll_set_post_language($fn_id, 'it');

// Step 3: Save new translations
pll_save_post_translations(array(
    'it' => $fn_id,
    'en-us' => $en_page_id,
    'fr' => $fr_page_id,
    'de' => $de_page_id
));
```

**Diagnostic — checking the raw translation group:**
```php
$terms = wp_get_object_terms($post_id, 'post_translations');
if (!empty($terms)) {
    $group = maybe_unserialize($terms[0]->description);
    // $group = array('it' => 84, 'en-us' => 1459, 'fr' => 1476, 'de' => 414)
}
```

This diagnostic is the fastest way to understand what Polylang "sees" for a given post — especially when `pll_get_post()` returns unexpected results.

### Polylang — Bulk Operations Pattern

When fixing Polylang for multiple posts at once, batch them into a single AJAX handler to minimize functions.php edits:

```php
add_action('wp_ajax_fix_pll_batch', function() {
    if (!current_user_can('manage_options')) wp_die('no');

    $batch = array(
        84 => array('en-us' => 1459, 'fr' => 1476, 'de' => 414),
        78 => array('en-us' => 1456, 'fr' => 1473, 'de' => 411),
        80 => array('en-us' => 1458, 'fr' => 1475, 'de' => 413),
    );

    $results = array();
    foreach ($batch as $fn_id => $translations) {
        wp_delete_object_term_relationships($fn_id, 'post_translations');
        pll_set_post_language($fn_id, 'it');
        $trans = array('it' => $fn_id);
        foreach ($translations as $lang => $page_id) {
            $trans[$lang] = $page_id;
        }
        pll_save_post_translations($trans);
        $results[$fn_id] = array(
            'en' => pll_get_post($fn_id, 'en-us'),
            'fr' => pll_get_post($fn_id, 'fr'),
            'de' => pll_get_post($fn_id, 'de'),
        );
    }
    wp_send_json_success($results);
});
```

**Workflow for functions.php temporary handlers:**
1. Open theme editor: `/wp-admin/theme-editor.php?file=functions.php&theme=twentytwentyfive-child` (WoM) or `&theme=twentytwentyfive` (MU)
2. Access CodeMirror: `document.querySelector('.CodeMirror').CodeMirror`
3. **CRITICAL: Set content via CodeMirror API, NOT the textarea.** The WP theme editor uses CodeMirror which maintains its own state. Setting `document.getElementById('newcontent').value` directly DOES NOT WORK — CodeMirror overwrites the textarea on save. Always use:
   ```javascript
   var cm = document.querySelector('.CodeMirror').CodeMirror;
   cm.setValue(newContent);  // Set the full content
   cm.save();                // Sync CodeMirror state to textarea
   document.getElementById('submit').click();  // Submit form
   ```
4. Execute: `fetch('/wp-admin/admin-ajax.php?action=fix_pll_batch', {credentials:'same-origin'})`
5. Verify response
6. **Remove handler immediately**: restore file to clean length via `cm.setValue(cleanContent); cm.save();`
7. Save again with `document.getElementById('submit').click()`
8. Verify: reload page, check `cm.getValue().length` matches clean state

### Polylang — Language Misassignment Fix

Pages created via WP admin (especially auto-generated legal/cookie pages) often have **wrong language assignments**. Polylang may assign all translations to `it` instead of their correct language. This causes:
- Language switcher shows wrong/duplicate entries
- `pll_get_post_translations()` returns isolated single-page groups (e.g., `{it: 1125}` instead of a 4-language group)
- Pages appear in wrong language lists in admin

**Diagnosis pattern:**
```php
add_action('wp_ajax_check_pll_langs', function() {
    if (!current_user_can('manage_options')) wp_die('no');
    $ids = array(44, 1125, 1126, 1127); // suspected pages
    $r = array();
    foreach ($ids as $id) {
        $r[$id] = array(
            'lang' => pll_get_post_language($id, 'slug'),
            'trans' => pll_get_post_translations($id),
        );
    }
    wp_send_json_success($r);
});
```

**Fix pattern — correct language + clear old groups + re-link:**
```php
// Step 1: Set correct language on each page
pll_set_post_language(44, 'it');
pll_set_post_language(1125, 'en-us');
pll_set_post_language(1126, 'de');
pll_set_post_language(1127, 'fr');

// Step 2: Clear ALL old (wrong) translation groups
foreach (array(44, 1125, 1126, 1127) as $pid) {
    wp_delete_object_term_relationships($pid, 'post_translations');
}

// Step 3: Create the correct 4-language group
pll_save_post_translations(array(
    'it' => 44, 'en-us' => 1125, 'de' => 1126, 'fr' => 1127
));

// Step 4: Flush caches
wp_cache_flush();
if (function_exists('PLL') && PLL()->model) {
    PLL()->model->clean_languages_cache();
}
```

**Key insight**: `wp_delete_object_term_relationships()` on ALL pages in the group is MANDATORY before `pll_save_post_translations()`. If any page still has an old group reference, Polylang may silently merge groups incorrectly.

### Rank Math SEO — Batch PHP Handler Pattern (Proven)

The fastest and most reliable way to add multiple Rank Math focus keywords is via a temporary AJAX handler in `functions.php` that uses `update_post_meta()` directly:

```php
add_action('wp_ajax_batch_seo_keywords', function() {
    if (!current_user_can('manage_options')) wp_die('no');
    $kw = array(
        630 => 'Italian clothing brands men quality heritage merino luxury',
        622 => 'Italian knitwear brands comparison superfine merino excellence',
        608 => 'Italian mens fashion quality heritage substance craftsmanship',
        585 => 'premium Italian fabrics merino wool material culture wellbeing',
        582 => 'Italian t-shirt manufacturing artisanal merino heritage',
    );
    $r = array();
    foreach ($kw as $pid => $keyword) {
        update_post_meta($pid, 'rank_math_focus_keyword', $keyword);
        $r[$pid] = get_post_meta($pid, 'rank_math_focus_keyword', true);
    }
    wp_send_json_success($r);
});
```

**Why this works better than REST API or Gutenberg store:**
- `update_post_meta()` writes directly to wp_postmeta — no plugin filtering
- Response includes `get_post_meta()` verification — confirms actual DB state
- Batch of 5-11 keywords per handler is optimal
- Works for any post type (posts, pages, field_notes)

**NOTE**: The WP REST API `meta` field does NOT expose `rank_math_focus_keyword` on read either. Verification via REST API will show `EMPTY` even when the keyword is correctly saved. Always verify via PHP `get_post_meta()` in the AJAX response.

### wp.apiFetch — Content Deployment from Admin Pages

`wp.apiFetch` from any WP admin page (e.g., theme editor) can create and update pages directly. This is FASTER than building PHP handlers for content updates:

```javascript
// UPDATE existing page content
const r = await wp.apiFetch({
    path: '/wp/v2/pages/44',
    method: 'PUT',
    data: { title: 'Cookie Policy', content: gutenbergBlocksHTML }
});

// CREATE new page
const r = await wp.apiFetch({
    path: '/wp/v2/pages',
    method: 'POST',
    data: {
        title: 'Privacy Policy',
        slug: 'en-privacy-policy',
        content: gutenbergBlocksHTML,
        status: 'publish'
    }
});
// r.id = new page ID
```

**When to use wp.apiFetch vs PHP handler:**
- Content updates (title, content, slug, status) → `wp.apiFetch` PUT/POST
- Polylang operations (pll_set_post_language, pll_save_post_translations) → PHP AJAX handler
- Rank Math SEO (update_post_meta) → PHP AJAX handler
- Polylang cache flush → PHP AJAX handler (wp_cache_flush + PLL model cache)

**Key constraint for fromCharCode in content**: When passing content via `wp.apiFetch`, non-ASCII characters must use `String.fromCharCode()` in the JS tool. Build the content string with character concatenation:
```javascript
var e_grave = String.fromCharCode(232);
var content = 'Il titolare ' + e_grave + ' la persona...';
```

### Language Switcher — WPCode Snippet Override (pll_get_post)

The FSE header language switcher (WPCode snippet 993, "WoM - Language Switcher (FSE Header)") uses `pll_the_languages()` to generate language links. However, `pll_the_languages()` can return wrong URLs when:
- A post has cross-post-type translations (field_notes → pages)
- Translation groups have been recently modified
- Polylang's internal cache is stale

**The fix — add a `pll_get_post()` override** inside the snippet, right after the `$langs` array is populated and before the HTML is built:

```php
// Fix: Override language URLs using pll_get_post for accurate translation resolution
if ( is_singular() && function_exists( 'pll_get_post' ) ) {
    $current_id = get_the_ID();
    if ( $current_id ) {
        foreach ( $langs as $slug => &$ldata ) {
            $trans_id = pll_get_post( $current_id, $slug );
            if ( $trans_id ) {
                $ldata['url'] = get_permalink( $trans_id );
            }
        }
        unset( $ldata );
    }
}
```

This override is permanent (lives inside the WPCode snippet, not functions.php) and ensures the language switcher always resolves the correct URL by asking Polylang directly for each translation, rather than relying on the potentially stale URL data from `pll_the_languages()`.

**Editing WPCode snippets programmatically:**
WPCode has no REST API endpoint (`rest_no_route` error for `wpcode` post type). To edit a snippet:
1. Navigate to the snippet edit page in WP admin
2. Access the CodeMirror editor instance
3. Use `cm.replaceRange()` to insert code at the correct position
4. Save via the form submit button

### Polylang — Verifying Page ID from Frontend

A common trap: the same slug can exist on multiple pages (e.g., `en-comfort-as-asset` at page 701 AND `en-comfort-as-an-asset` at page 1449). The WP REST API search may return the wrong one.

**Always verify the actual serving page ID from the frontend:**
```javascript
// On the frontend page
document.body.className.match(/page-id-(\d+)/)?.[1]
```

This is the definitive check — it tells you which page WordPress actually resolved for that URL. All content edits must target THIS page ID, not whichever ID the REST API search returns.

### LiteSpeed Cache — The False Negative Generator

After making Polylang or content changes, the frontend may show stale content. `?nocache=1` does NOT bypass LiteSpeed on Hostinger.

**Manual purge**: Admin bar → "Svuotare e pulire tutta la cache" (Purge All)

**Programmatic purge** (from any WP admin page with admin bar):
```javascript
// Find the purge link with its nonce from the admin bar
const purgeUrl = document.querySelector('a[href*="purge_all_lscache"]')?.href;
if (purgeUrl) {
    await fetch(purgeUrl, {credentials: 'same-origin'});
}
```

The nonce is embedded in the admin bar link, so you don't need to generate one separately. This is much faster than navigating to the LiteSpeed settings page.

**Testing with cache bypass**: Append `?v=N` (incrementing N) to test URLs. This often forces a fresh render from LiteSpeed even when the cached version persists. Not 100% reliable but useful for quick checks.

Always purge LiteSpeed cache before verifying any frontend changes.

### Browser-Cached 301 Redirects — The Ghost Redirect

When a page appears to redirect to the homepage for anonymous users but works fine for logged-in users, and all debugging (wp_redirect filter, .htaccess, Polylang settings) shows no active redirect, the most likely cause is a **browser-cached 301 redirect** from a previous state (e.g., during page creation, slug changes, or Polylang configuration).

**Diagnosis**: Test with `cache: 'no-store'` to bypass browser cache:
```javascript
// If this returns the correct URL, it's a browser-cached 301
fetch('https://site.com/page/', {credentials:'omit', redirect:'follow', cache:'no-store'})
  .then(r => 'URL: ' + r.url + ' Status: ' + r.status)

// Compare with default (uses browser cache):
fetch('https://site.com/page/', {credentials:'omit', redirect:'follow'})
  .then(r => 'URL: ' + r.url + ' Status: ' + r.status)
```

If `cache:'no-store'` returns the correct page but the default fetch redirects, it's a browser-cached 301.

**Fix**: The server is already serving the correct page. The user needs to clear their browser cache for that URL (or use incognito). LiteSpeed purge won't help because it's the user's browser, not the server cache.

**Prevention**: During page creation and slug changes, avoid 301 redirects when possible. Use 302 (temporary) redirects for staging/testing.

### Debugging Mysterious Redirects — Full Methodology

When a page redirects unexpectedly, work through this checklist:

1. **Check wp_redirect filter**: Add to functions.php, set a transient with backtrace. If the transient is never set, wp_redirect() is NOT the cause.
2. **Check .htaccess**: Read via AJAX handler (`file_get_contents(ABSPATH . ".htaccess")`). Look for custom RewriteRules.
3. **Check header_register_callback**: Hook into `init` to register a callback that inspects `headers_list()` for Location headers.
4. **Check WPCode snippets**: Especially 301 redirect snippets. Verify slug matching logic doesn't inadvertently catch the page.
5. **Check Rank Math redirects**: `get_post_meta($id, 'rank_math_redirection_header_code', true)` and `rank_math_redirection_url_to`.
6. **Check old slugs**: `get_post_meta($id, '_wp_old_slug')` — WordPress auto-redirects old slugs.
7. **Test cache:'no-store'**: If all above are clean, it's almost certainly a browser-cached 301.

### FSE Template Parts — Editing via REST API

Footer and header templates in Full Site Editing (FSE) themes can be edited via the WP REST API. This is the fastest way to fix links in templates:

```javascript
// Find template parts containing a specific string
wp.apiFetch({path: '/wp/v2/template-parts'}).then(function(parts) {
  for (var i = 0; i < parts.length; i++) {
    var raw = parts[i].content ? (parts[i].content.raw || '') : '';
    if (raw.indexOf('target-string') > -1) {
      console.log(parts[i].slug + ': found, ID=' + parts[i].id);
    }
  }
});

// Update a template part (replace string in content)
wp.apiFetch({path: '/wp/v2/template-parts'}).then(function(parts) {
  for (var i = 0; i < parts.length; i++) {
    if (parts[i].slug === 'footer') {
      var updated = parts[i].content.raw.replace(/old-slug/g, 'new-slug');
      return wp.apiFetch({
        path: '/wp/v2/template-parts/' + encodeURIComponent(parts[i].id),
        method: 'POST',
        data: { content: updated }
      });
    }
  }
});
```

**Template part IDs** use the format `theme//slug` (e.g., `twentytwentyfive//footer`). The `encodeURIComponent()` is essential because of the `//` in the ID.

### Chrome JS Tool — BLOCKED Responses Workaround

The Chrome extension JS tool blocks responses that contain cookie or query string data (URLs with parameters, nonces, etc.). When this happens:

**Workaround 1**: Extract only non-URL data from the response:
```javascript
// BLOCKED — returns URLs with query parameters
wp.apiFetch({path: '/wp/v2/template-parts'}).then(parts => JSON.stringify(parts))

// WORKS — extract only safe scalar data
wp.apiFetch({path: '/wp/v2/template-parts'}).then(function(parts) {
  var out = [];
  for (var i = 0; i < parts.length; i++) {
    out.push(parts[i].slug + ':' + (parts[i].content.raw.indexOf('target') > -1));
  }
  return out.join(', ');
})
```

**Workaround 2**: For fetch responses, avoid returning full HTML or headers. Extract only the specific data you need:
```javascript
// BLOCKED
fetch(url).then(r => r.text())

// WORKS — extract specific info
fetch(url).then(r => 'Status: ' + r.status + ' Redirected: ' + r.redirected)
```

### WPCode Lite Limitations

- **"Run Now" button**: Pro-only feature — does NOT work in Lite
- **Insertion location**: Defaults can silently change to useless hooks (e.g., `mepr_unauthorized_message_after`)
- **PHP in "Header per l'intero sito"**: NEVER executes in admin context
- **Recommendation**: Don't rely on WPCode for PHP execution. Use functions.php AJAX handlers instead.

### Hostinger Rate Limiting

- **Batch size**: max 8-10 sequential API calls before risking timeout
- **Nonce lifetime**: ~15 minutes of inactivity
- **Payload size**: Chrome extension JS tool times out on payloads >15KB
- **Solution for large content**: Build content in browser memory across multiple JS calls, then PUT once

### Content Size Workaround

For pages >15KB, DON'T try to pass the content as a single JS string. Instead:
```javascript
window._content = '';
window._content += '<!-- wp:cover ... -->...<!-- /wp:cover -->';
window._content += '<!-- wp:group ... -->...<!-- /wp:group -->';
fetch('/wp-json/wp/v2/pages/117', {
  method: 'PUT',
  headers: {'Content-Type':'application/json', 'X-WP-Nonce': window._nonce},
  body: JSON.stringify({content: window._content})
});
```

## Canonical Cross-Domain Strategy (MU)

### The Problem

MU (`merinouniversity.com`) outputs all SEO signals (canonical, og:url, hreflang) pointing to the staging domain. For production SEO to work, these must point to `merinouniversity.com`.

Additionally, Rank Math + Polylang have a bug on translated front pages: the EN/DE/FR homepage canonicals incorrectly point to the IT root `/` instead of their own URLs. This is because Rank Math resolves `is_front_page()` to the same canonical for all language variants.

### WPCode Snippet 2493: "Albeni 1905 - MU Canonical Cross-Domain Rewrite"

**Status**: Active, insertion location: `everywhere` (critical — `site_wide_header` won't work for PHP filters)

**4 filters, no conflicts with existing snippets 632/633:**

1. **`rank_math/frontend/canonical` (priority 20)** — Rewrites all canonicals from staging → production via `str_replace()`
2. **`rank_math/frontend/canonical` (priority 30)** — Fixes homepage translation bug: maps non-IT front pages to their correct production URLs using `pll_current_language('slug')` and a hardcoded `$map` array
3. **`rank_math/opengraph/url`** — Rewrites og:url staging → production
4. **`pll_rel_hreflang_attributes` (priority 99)** — Rewrites all hreflang URLs staging → production. Priority 99 ensures it runs AFTER snippet 632 (Custom Hreflang)

**Homepage URL map** (hardcoded in filter 2):
```php
$map = array(
    'en' => 'https://merinouniversity.com/en/en-home/',
    'de' => 'https://merinouniversity.com/de/de-merino-university/',
    'fr' => 'https://merinouniversity.com/fr/fr-merino-university/',
);
```
Note: keys are `en`, `de`, `fr` — matching what `pll_current_language('slug')` returns on MU (NOT `en-us`).

**Architecture notes:**
- Uses PHP `use()` closures to share `$mu_staging` and `$mu_production` config variables across all filters
- The snippet is purely additive — it doesn't disable or override any existing Rank Math or Polylang behavior, just transforms the output
- If the staging domain changes, only the `$mu_staging` variable needs updating

### WPCode Insertion Location — The Silent Killer

When creating WPCode PHP snippets that use `add_filter()` or `add_action()`, the insertion location MUST be `everywhere` or `frontend_only`. The default `site_wide_header` treats PHP code as direct output (like an HTML snippet) and the filters never register.

**Symptoms of wrong insertion location**: snippet is active, no PHP errors, but filters have zero effect on the frontend. This is completely silent — no error logs, no warnings.

**How to verify**: Check the radio button `input[name="wpcode_auto_insert_location"]` — if it shows `site_wide_header`, change to `everywhere` and re-save.

### Verified Results (March 2026)

All 4 homepage variants + internal pages verified:
- Canonical → `merinouniversity.com` (production) ✓
- og:url → `merinouniversity.com` ✓
- Hreflang → all 4 languages on `merinouniversity.com` ✓
- EN/DE/FR homepage canonical bug → FIXED (self-referencing) ✓
- Zero staging domain references remaining in SEO tags ✓

### Cross-Domain State of Other Ecosystem Sites (March 2026)

- **perfectmerinoshirt.com**: Hostinger Horizons SPA — no canonical tag, no robots.txt, no hreflang (cannot be fixed via WP, needs Horizons-level intervention)
- **albeni1905.com**: Unreachable (chrome-error, DNS/hosting issue as of March 2026)
- **worldofmerino.com**: Links to `merinouniversity.com` (production domain) — correct behavior

## `field_notes` Custom Post Type (WoM)

The WoM site uses a `field_notes` CPT for "Note di Campo" articles. These are separate from regular WP pages but display similar content.

### Key Differences from Pages

- **REST API endpoint**: `/wp-json/wp/v2/field_notes/{id}` (not `/pages/`)
- **URL prefix**: `/field-note/slug/` on frontend
- **Template auto-displays featured image**: The template uses `wp-block-post-featured-image` to show the featured image automatically. Content must NOT include a `wp:image` block, or the image appears twice.
- **Polylang not managed by default**: New field_notes may have no Polylang language assignment. You must explicitly call `pll_set_post_language()` and `pll_save_post_translations()`.

### Staging field_notes from Pages (Copying Content)

When a page's content needs to also appear as a field_note, copy the page content while removing the image block:

```javascript
// Fetch page content
const page = await wp.apiFetch({path: '/wp/v2/pages/387?context=edit'});
const content = page.content.raw;

// Remove the first wp:image block (template handles the image)
const imageBlockEnd = content.indexOf('<!-- /wp:image -->') + '<!-- /wp:image -->'.length;
const contentWithoutImage = content.substring(imageBlockEnd).trim();

// Update the field_note with content + featured image
await wp.apiFetch({
    path: '/wp/v2/field_notes/78',
    method: 'PUT',
    data: {
        content: contentWithoutImage,
        featured_media: 230  // media library ID of the image
    }
});
```

### Finding Media IDs for Images

To set `featured_media`, you need the media library ID (not the filename):
```javascript
const allMedia = await wp.apiFetch({path: '/wp/v2/media?per_page=100&_fields=id,source_url'});
const match = allMedia.find(m => m.source_url?.endsWith('/7.webp'));
// match.id is what you pass to featured_media
```

### Note di Campo Page Structure

Each Note di Campo page has 6 Gutenberg blocks:
1. `wp:image` — Hero image (removed when copying to field_note)
2. `wp:html` — Main article body with these CSS classes:
   - `fn-blockquote` — Opening quote
   - `fn-body` — Article paragraphs
   - `fn-todo-box` — Action box(es): "Da fare" (To do) + optional "Continua a leggere" (Keep reading)
   - `fn-closing-quote` — Closing italic quote
3. `wp:html` — CSS styles
4. `wp:html` — Additional structural HTML
5. `wp:html` — Klaviyo signup form
6. `wp:html` — Dark CTA block

### fn-todo-box Patterns

Some pages have 2 todo-boxes (action items only), others have 3 (action items + "Keep reading" links). The 3rd box header is translated per language:
- IT: "Continua a leggere"
- EN: "Keep reading"
- FR: "Continuer à lire"
- DE: "Weiterlesen"

When an IT page has 3 boxes but EN/FR only have 2, you need to add the missing 3rd box. The insertion point is right before the `fn-closing-quote` div.

**Finding the insertion point:**
```javascript
const raw = page.content.raw;
// Find the HTML fn-closing-quote (2nd occurrence — 1st is in CSS)
const positions = [];
let idx = 0;
while ((idx = raw.indexOf('fn-closing-quote', idx)) !== -1) { positions.push(idx); idx += 16; }
const htmlClosingQuote = positions[positions.length - 1]; // last occurrence = HTML element
const insertPos = raw.lastIndexOf('<div', htmlClosingQuote);
// Insert new todo-box HTML at insertPos
```

### WoM field_notes Post IDs

```
regola-01:    FN 74  (featured_media: 88)
regola-02:    FN 75  (featured_media: 89)
errore-01:    FN 76  (featured_media: 0, Polylang: {it:76, en-us:1450, de:405, fr:1467})
errore-02:    FN 77  (featured_media: 0, Polylang: {it:77, en-us:1451, de:406, fr:1468})
gesto-01:     FN 78  (featured_media: 230, Polylang: {it:78, en-us:1456, fr:1473, de:411})
gesto-02:     FN 79
gesto-03:     FN 80  (featured_media: 228, Polylang: {it:80, en-us:1458, fr:1475, de:413})
regola-03:    FN 81  (featured_media: 90)
regola-04:    FN 82  (featured_media: 91)
errore-03:    FN 83  (featured_media: 0, Polylang: {it:83, en-us:1452, de:407, fr:1469})
gesto-04:     FN 84  (featured_media: 224, Polylang: {it:84, en-us:1459, fr:1476, de:414})
regola-05:    FN 85
il-comfort:   FN 96  (featured_media: 94)
arte-transiz: FN 93  (featured_media: 92)
```

## Page Construction Workflow

### The Golden Rule: IT Master First

Always build the Italian version first, validate it with the user, THEN derive other languages from the exact IT raw content. Never build languages independently — structural drift is guaranteed.

### Bulk Translation Workflow (Proven Pattern)

For translating multiple posts across languages efficiently:

1. **Fetch IT raw content**: `fetch('/wp-json/wp/v2/posts/ID?context=edit&_fields=content')`
2. **Split into blocks**: `blocks = raw.split(/(?=<!-- wp:)/)`
3. **Map block structure**: Get type and text summary for each block
4. **Clone blocks array** for each target language
5. **Translate block-by-block** using `replaceInnerP`/`replaceInnerH`/`replaceQuoteP`
6. **For HTML blocks** (Klaviyo, CTA): use `split().join()` with `String.fromCharCode()`
7. **Assemble**: `finalContent = translatedBlocks.join('')`
8. **Verify**: Check block count matches IT, scan for IT remnants
9. **Deploy**: `PUT /wp-json/wp/v2/posts/ID` with `{content: finalContent}`
10. **Re-verify from server**: Fetch back and confirm block count

### Common HTML Blocks (Shared Across Stories)

Most WoM stories end with two HTML blocks that need translation:

**Klaviyo Signup Box** (second-to-last HTML block):
- IT: "Vuoi costruire un guardaroba che funziona davvero?" / "Scarica la guida: Il Guardaroba Invisibile — 12 capi, 30 giorni, meno decisioni." / "Scarica gratis"
- EN: "Want to build a wardrobe that actually works?" / "Download the guide: The Invisible Wardrobe — 12 pieces, 30 days, fewer decisions." / "Download free"
- DE: "Möchtest du eine Garderobe aufbauen, die wirklich funktioniert?" / "Lade den Leitfaden herunter: Die Unsichtbare Garderobe — 12 Teile, 30 Tage, weniger Entscheidungen." / "Kostenlos herunterladen"

**Dark CTA Block** (last HTML block):
- IT: "MENO CAPI, PIÙ STILE" / "Il Guardaroba che Dura nel Tempo" / "Scopri capi pensati per chi sceglie la qualità sartoriale italiana." / "Visita Albeni 1905"
- EN: "FEWER PIECES, MORE STYLE" / "The Wardrobe that Lasts Through Time" / "Discover pieces designed for those who choose Italian sartorial quality." / "Visit Albeni 1905"
- DE: "WENIGER TEILE, MEHR STIL" / "Die Garderobe, die die Zeit überdauert" / "Entdecke Kleidungsstücke für alle, die italienische Schneiderqualität wählen." / "Besuche Albeni 1905"

**Note on PIÙ**: The Ù in "PIÙ" is uppercase U-grave (char code 217), NOT lowercase ù (249). Use `String.fromCharCode(217)`.

### Encoding Rules

| Character | Context | In WP Content | In JS Tool |
|-----------|---------|---------------|------------|
| Apostrophe | `C'è`, `l'intera` | ASCII 39 (`'`) | ASCII 39 |
| Double quotes | `"premium"` | ASCII 34 (`"`) | ASCII 34 |
| Em dash | `—` | Unicode 8212 | `String.fromCharCode(8212)` |
| Italian accents | è, à, ù | Direct Unicode | `String.fromCharCode(232, 224, 249)` |
| German umlauts | ä, ö, ü, ß | Direct Unicode | `String.fromCharCode(228, 246, 252, 223)` |
| German quotes | „text" | Unicode 8222/8220 | `String.fromCharCode(8222)` / `String.fromCharCode(8220)` |
| French guillemets | « » | Unicode 171/187 | `String.fromCharCode(171)` / `String.fromCharCode(187)` |
| Line endings | CRLF | `\r\n` (0x0D 0x0A) | Preserved from source |

**IMPORTANT**: WoM story content uses ASCII straight quotes/apostrophes (not curly). MU page content may differ — always verify with charCode inspection before translating.

### Link Localization Map

When translating from IT, internal links must be remapped:
```
IT: /department-material-science/   → EN: /en-department-material-science/
IT: /construction/                  → DE: /de-construction/
IT: /ethical-origins/               → FR: /fr-department-origine-ethique/
IT: /essenzialismo-tessile/         → EN: /en-textile-essentialism/
IT: /cost-per-wear/                 → DE: /de-cost-per-wear/
```

French slugs are often completely different from the IT pattern — always verify.

### Images with Text Must Be Localized

When an image contains text overlay (like infographics), use language-specific versions:
```
la-chimica-del-lavaggio-_IT-scaled.webp  → IT pages
la-chimica-del-lavaggio-_EN-scaled.webp  → EN pages
la-chimica-del-lavaggio-_DE-scaled.webp  → DE pages
la-chimica-del-lavaggio-_FR-scaled.webp  → FR pages
```

Images WITHOUT text (photos, hero backgrounds) use the same file across all languages.

## HTML Widget Patterns

For rich interactive sections (comparison tables, spec cards, animated diagrams), use `<!-- wp:html -->` blocks with inline CSS/JS. These count as 1 Gutenberg block but can contain entire sections.

Key widget patterns developed for this ecosystem:

1. **Dark spec card** (Technical Specifications) — see `references/widget-patterns.md`
2. **Comparison cards** (red bad / green good) — enzyme comparison, microplastics
3. **3-phase evolution** (past/present/future cards with colored left borders)
4. **Animated SVG diagrams** (felting mechanics, plasma bombardment)
5. **R&D Stage cards** (dark background, icon + badge footer)

All widgets must be translated per-language inside the HTML.

## WoM Story Post IDs

### 11 Story Groups (posts, not pages)
```
guardaroba:  IT=64,  EN=673, DE=361, FR=763
cappotto:    IT=60,  EN=676, DE=359, FR=762
cena:        IT=63,  EN=674, DE=369, FR=761
eleganza:    IT=67,  EN=678, DE=365, FR=764
regola8ore:  IT=70,  EN=677, DE=367, FR=765
ritorno:     IT=183, EN=675, DE=363, FR=766
manifattura: IT=579, EN=582, DE=581, FR=583
tessuti:     IT=580, EN=585, DE=584, FR=586
moda:        IT=606, EN=608, DE=607, FR=609
confronto:   IT=620, EN=622, DE=621, FR=623
brand:       IT=632, EN=630, DE=631, FR=633
```

### Grucce Page Group
```
grucce: IT=394, EN=1463, DE=418, FR=1480
```

### Legal Page IDs (WoM)
```
cookie:  IT=44,   EN=1125, DE=1126, FR=1127
privacy: IT=3,    EN=1864, DE=547,  FR=1865
```

**Status (March 2026):**
- Cookie: 4L complete, content 1918-2284 chars, Polylang linked
- Privacy: 4L complete, content 2374-2703 chars, Polylang linked
- Company: Best before S.r.L., Milano, Italy
- Hosting: Hostinger International Ltd., 61 Lordou Vironos Street, 6023 Larnaca, Cyprus
- Privacy DE (547) was the original real content; IT (3) was WP default template (replaced)
- Privacy EN (1864) and FR (1865) were created from scratch based on DE structure

### MU FAQ Pages (March 2026)

```
faq: IT=2495 (slug: faq, /faq/), EN=2497 (slug: en-faq, /en/en-faq/), DE=2504 (slug: de-faq, /de/de-faq/), FR=2505 (slug: fr-faq, /fr/fr-faq/)
```

**Structure**: All 4 pages have identical HTML — 1 `wp:html` block with inline CSS, hero section (uses FAQ-1-scaled.webp, media ID 2494), 3 accordion sections (6 Q&A items using `<details>/<summary>` pattern), dark CTA block, and Schema.org FAQPage JSON-LD structured data. CSS class prefix: `mu-*`, fonts: Inter/Playfair Display.

**Polylang**: Translation group `pll_69c67002be52a` — uses `en` slug (NOT `en-us`).

**Rank Math SEO**:
- IT: "FAQ lana Merino cura manutenzione durata" / "FAQ Lana Merino | Merino University"
- EN: "FAQ Merino wool care maintenance durability" / "Merino Wool FAQ | Merino University"
- DE: "FAQ Merinowolle Pflege Haltbarkeit Komfort" / "Merinowolle FAQ | Merino University"
- FR: "FAQ laine Merinos entretien soin durabilite" / "FAQ Laine Mérinos | Merino University"

**Old conflicting pages** (renamed/draft):
- Page 53: slug `faq-2`, status DRAFT — old IT FAQ page (previously linked from footer)
- Page 398: slug `en-faq-old-v1` — old EN FAQ (renamed to avoid slug conflict with page 2497)

**Footer link**: Updated from `/faq-2` to `/faq/` in the FSE footer template part (`twentytwentyfive//footer`).

### MU WPCode Snippets (March 2026)

```
1985: "MU Multilingual Nav/Links/SEO Fix" — Active, "Esegui ovunque". Uses template_redirect with output buffering. Skips IT pages (if $lang === 'it' || !$lang) return.
1986: "Polylang Fix" — Active
1987: "301 Redirects - Old Suffixed Pages to Base Translations" — Active, "Solo frontend". Catches slugs ending in -de, -en, -fr → strips suffix → finds IT root → pll_get_post() → 301 redirect.
2493: "Albeni 1905 - MU Canonical Cross-Domain Rewrite" — Active, "everywhere"
633:  "Custom Hreflang" — Active
```

### Note di Campo SEO Keywords (WoM) — Complete Status

All 24 Note di Campo pages have focus keywords in all 4 languages (IT/EN/FR/DE = 96 total).

All 14 blog posts (6 old + 5 mid-range + 3 pillar) have focus keywords in all 4 languages.

Moda consapevole (p.767): IT+EN+FR+DE focus keywords complete.

**Total SEO keywords deployed via batch PHP handlers: 88+**

### Klaviyo Integration (WoM)
- Public API key: `VbcXCv`
- List ID: `QZ8DYr`
- Endpoint: `https://a.klaviyo.com/client/subscriptions/`
- Revision: `2024-10-15`

## Verification Checklist

After every deployment, verify:
1. **Block count matches** across all 4 languages
2. **No IT remnants** in translated pages (scan for common IT words: comprare, scegliere, guardaroba, eleganza, acquisto, etc.)
3. **Correct images** per language (especially text-containing infographics)
4. **Internal links** point to correct language slugs
5. **SEO metadata** applied via Rank Math API (not REST API)
6. **Language switcher** works (check Polylang shadow pages)
7. **LiteSpeed cache purged** before frontend verification

### IT Remnant Detection Script
```javascript
var itCheck = ['cambio','guardaroba','padre','eredit','orologi','pensiamo',
  'pragmatismo','filtri','acquisto','invecchier','risolve','riparare',
  'privazione','minimalisti','Approfondisci','riconosce','Vuoi costruire',
  'Scarica la guida','Scopri la','COMPRARE','SCEGLIERE'];
var plain = content.replace(/<[^>]+>/g, '').replace(/<!-- [^>]+ -->/g, '');
var found = itCheck.filter(function(w) { return plain.indexOf(w) >= 0; });
```

## Child Theme: twentytwentyfive-child

The WoM production site uses a child theme with extensive SEO customizations in `functions.php`:
- noai meta tags
- lang attribute fixes
- canonical URLs
- hreflang tags
- schema markup
- redirects
- nav translations
- OG image
- breadcrumbs
- H1 demotion
- alt text automation
- noindex for specific pages
- footer cleanup

**NEVER add permanent code to functions.php without user approval.** For temporary operations (like Polylang fixes), add AJAX handlers, use them, then immediately remove.

## Session Learnings (2026-03-19) — Consolidated Knowledge

### Architecture Decision: Hybrid Scraping (Option C)

The staging site is a WordPress reconstruction of `merinouniversity.com` (originally built on Hostinger Horizon, a proprietary builder with NO export capability). The approved approach is:

1. **Scrape CSS/layout** from production (the visual "dress")
2. **Keep the SEO heading structure** from staging (improved: single H1, cleaner hierarchy)
3. **Merge**: pixel-perfect production design + optimized staging SEO structure

The staging heading tags were verified to be BETTER than production (H2 for nav logo instead of duplicate H1). Always preserve the staging heading hierarchy when importing production visuals.

### Rank Math SEO — The Gutenberg Store Method

When the `/rankmath/v1/updateMeta` endpoint is unavailable, use the Gutenberg data store directly:

```javascript
// SET SEO data (must be inside the page's Gutenberg editor)
var rm = wp.data.dispatch('rank-math');
rm.updateKeywords('keyword1, keyword2, keyword3');
rm.updateSerpTitle('SEO Title | Brand');
rm.updateDescription('Meta description under 155 chars.');

// SAVE to persist
wp.data.dispatch('core/editor').savePost();

// VERIFY
var rm = wp.data.select('rank-math');
rm.getKeywords();
rm.getSerpTitle();
rm.getDescription();
```

**Critical**: This ONLY works when you're inside the Gutenberg editor of that specific post. Navigate to each post individually.

### Content Saving — What Actually Works

| Method | Works? | Notes |
|--------|--------|-------|
| `editPost({content})` + `savePost()` | NO | WP sanitizes/strips inline HTML |
| `wp.apiFetch` cross-post | NO | Times out from Gutenberg editor |
| `wp.apiFetch` from theme-editor | **YES** | Works for PUT/POST from any admin page (NOT Gutenberg) |
| **Code Editor textarea + "Aggiorna" button** | YES | **THE method** |
| Base64 accumulate → decode → textarea | YES | Slow but reliable for any size |
| localStorage transfer between tabs | YES | For cross-post content transfer |

**THE GOLDEN METHOD:**
1. Open post editor
2. `wp.data.dispatch('core/edit-post').switchEditorMode('text')`
3. Set textarea: `Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(ta, html)`
4. Dispatch: `ta.dispatchEvent(new Event('input',{bubbles:true}))`
5. Click "Aggiorna" button (find via `document.querySelectorAll('button')`)
6. Verify: `wp.data.select('core/editor').didPostSaveRequestSucceed()`

### Polylang — Real Post IDs

| Page | Expected ID | Actual Polylang ID |
|------|------------|-------------------|
| physics-efficient-travel FR | 450 | **445** |
| physics-efficient-travel EN | 409 | 409 |

**Always verify** actual ID via frontend: `document.body.className.match(/page-id-(\d+)/)`

### Cowork Tool Limits

- JS tool `text` parameter: ~1500 chars max for data
- Screenshots fail on heavy WP admin pages — use `javascript_tool` instead
- VM proxy blocks HTTPS to external sites — can't use curl for WP API
- Application Passwords NOT available on Hostinger

### Pages Completed

| Page | IT | EN | DE | FR | SEO |
|------|----|----|----|----|-----|
| physics-efficient-travel | 119 ✅ | 409 ✅ | 332 ✅ | 445 ✅ | All ✅ |
| department-material-science | 32 ✅ | pending | pending | pending | IT ✅ |

## Session Learnings (2026-03-25) — Legal Pages & SEO Batch

### Polylang Language Misassignment — Root Cause

WP auto-generated pages (Privacy Policy, Cookie Policy) and pages created by some plugins default to the site's primary language (IT) regardless of their intended language. The slug may suggest the correct language (e.g., `en-cookie-policy`) but Polylang internally marks them all as `it`.

**Detection**: Check `pll_get_post_language($id, 'slug')` — if it returns `it` for a page with an `en-` or `de-` prefix, the assignment is wrong.

**Prevention**: After creating any new page via REST API that should be in a non-IT language, ALWAYS immediately call `pll_set_post_language()` via PHP AJAX handler before doing anything else.

### WoM functions.php Clean State

As of March 2026, the clean state of `functions.php` (twentytwentyfive-child) is exactly **14749 characters**. After every temp AJAX handler operation:
1. `cm.setValue(cm.getValue().substring(0, 14749))`
2. Save via `document.getElementById('submit').click()`
3. Verify: `cm.getValue().length === 14749`

### Comprehensive Polylang Fix Pattern (Battle-Tested)

For fixing a group of pages that need both language correction AND translation linking:

```php
add_action('wp_ajax_fix_pll_group', function() {
    if (!current_user_can('manage_options')) wp_die('no');

    $group = array('it' => 44, 'en-us' => 1125, 'de' => 1126, 'fr' => 1127);

    // Phase 1: Set correct languages
    foreach ($group as $lang => $pid) {
        pll_set_post_language($pid, $lang);
    }

    // Phase 2: Clear ALL old translation groups (critical!)
    foreach ($group as $lang => $pid) {
        wp_delete_object_term_relationships($pid, 'post_translations');
    }

    // Phase 3: Create the new translation group
    pll_save_post_translations($group);

    // Phase 4: Flush all caches
    wp_cache_flush();
    if (function_exists('PLL') && PLL()->model) {
        PLL()->model->clean_languages_cache();
    }

    // Phase 5: Verify
    $r = array();
    foreach ($group as $lang => $pid) {
        $r[$lang] = array(
            'id' => $pid,
            'lang' => pll_get_post_language($pid, 'slug'),
            'trans' => pll_get_post_translations($pid),
        );
    }
    wp_send_json_success($r);
});
```

**The 4-phase order is critical**: set language → clear old groups → save new group → flush cache. Skipping or reordering causes silent failures.

## WPCode Snippets Registry (MU Site)

Active snippets on `merinouniversity.com`:

| ID | Name | Purpose | Insertion | Notes |
|----|------|---------|-----------|-------|
| 632 | Albeni 1905 - MU Custom Hreflang | Custom hreflang output | `wp_head` + `pll_rel_hreflang_attributes` | 182 lines, 9465 chars |
| 633 | Albeni 1905 - MU Polylang Hreflang Setup | Polylang hreflang config | `pll_the_languages` | 65 lines, 1732 chars |
| 1985 | Nav/Links/SEO Fix | Redirects, `template_redirect` + `pll_` | `everywhere` | Uses Polylang functions |
| 1986 | Polylang Fix | Polylang corrections | — | — |
| 1987 | 301 Redirects | URL redirects | — | — |
| 2036 | Draft Redundant Pages | Drafts redundant pages | — | — |
| 2037 | Draft Orphan Pages | Drafts orphan pages | — | — |
| 2347 | TEMP Page Update API | Temporary API endpoint | — | Should be deactivated when not in use |
| **2493** | **Albeni 1905 - MU Canonical Cross-Domain Rewrite** | **Canonical/og:url/hreflang → production** | **`everywhere`** | **52 lines, 2254 chars. Created 2026-03-27** |

**Interaction map**: Snippet 2493 runs AFTER 632 on `pll_rel_hreflang_attributes` (priority 99 vs default). No conflicts with any other snippet — 2493 is the only one touching Rank Math filters.

## Session Learnings (2026-03-27) — Canonical Cross-Domain

### WPCode PHP Filter Snippets — Insertion Location Trap

The single most common failure mode when creating WPCode snippets with `add_filter()` / `add_action()`: the insertion location defaults to `site_wide_header` on new snippets. This treats the PHP as inline output, never registering the filters. The snippet shows as "Active" with no errors, but has zero effect.

**Prevention**: After creating any PHP snippet that registers hooks/filters, ALWAYS verify the insertion location radio buttons before saving. Set to `everywhere` for filters that must run on all pages.

**Detection**: Navigate to the snippet edit page, run:
```javascript
var radios = document.querySelectorAll('input[name="wpcode_auto_insert_location"]');
var selected = 'none';
radios.forEach(function(r) { if (r.checked) selected = r.value; });
selected; // must be 'everywhere' for filter-based snippets
```

### Rank Math Canonical Filters — Priority Chain

Rank Math's `rank_math/frontend/canonical` filter supports multiple callbacks at different priorities. This enables a two-stage approach:
1. **Priority 20**: General domain rewrite (staging → production) — catches all pages
2. **Priority 30**: Special case override (homepage translation fix) — runs after general rewrite and can override specific URLs

This pattern is useful whenever you need a general rule with exceptions.

### `pll_current_language()` Returns URL Slug, Not Admin Slug

On MU, `pll_current_language('slug')` returns `en` (the URL prefix slug), not `en-us` (the Polylang internal/admin slug). This matters for any PHP code that switches behavior based on current language. Always test with a quick `var_dump()` or AJAX handler before hardcoding language checks.

### Frontend Verification Script (Canonical/Hreflang/OG)

Reusable JS to verify all SEO signals on any frontend page:
```javascript
var canonical = document.querySelector('link[rel="canonical"]');
var ogUrl = document.querySelector('meta[property="og:url"]');
var hreflangs = [];
document.querySelectorAll('link[rel="alternate"][hreflang]').forEach(function(el) {
    hreflangs.push(el.hreflang + ' -> ' + el.href);
});
JSON.stringify({
    page: window.location.pathname,
    canonical: canonical ? canonical.href : 'NONE',
    ogUrl: ogUrl ? ogUrl.content : 'NONE',
    hreflangs: hreflangs,
    hasStaging: (canonical ? canonical.href : '').indexOf('powderblue') >= 0
}, null, 2);
```

### MU Homepage URLs (Verified March 2026)

| Language | URL Path | Page Title |
|----------|----------|-----------|
| IT | `/` (root) | L'Autorità Globale sulla Lana Merino Superfine |
| EN | `/en/en-home/` | Global Authority on Superfine Merino Wool |
| DE | `/de/de-merino-university/` | Globale Autorität für Merinowolle |
| FR | `/fr/fr-merino-university/` | L'Autorité Mondiale sur la Laine Mérinos |

### MU Sitemap Stats (March 2026)

177 total pages: IT:40, EN:46, DE:45, FR:46

## Reference Files

- `references/widget-patterns.md` — Reusable HTML widget code for dark cards, comparison tables, animated SVGs
- `references/page-inventory.md` — Complete page ID map across all languages with Polylang shadow IDs (MU site)
- `references/seo-keywords.md` — Focus keywords, SEO titles, and meta descriptions per page per language (MU site)
