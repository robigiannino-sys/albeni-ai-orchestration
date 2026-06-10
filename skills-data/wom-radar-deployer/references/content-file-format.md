# Content file format — canonical template

The Python parser in `deploy_radar_post.py` (`parse_content_file()`) extracts these fields from each content `.md` file:

- **Slug** — must match the convention `^.{3,90}$`, no trailing slashes
- **Titolo** — full title (rendered as H1 by the theme)
- **SEO Title** — Rank Math title (≤60 chars, ends with `| World of Merino` or `| WoM`)
- **SEO Description** — Rank Math meta description (≤155 chars)
- **SEO Focus keyword** — primary search-intent phrase, 2-4 words, in the page's language
- **Body** — Gutenberg blocks inside a fenced ` ```html ` block

The parser is forgiving with whitespace and matches both `**Label**: value` and `- **Label**: value` syntax. SEO fields with parenthetical char counts (`**Title** (59ch): \`...\``) are stripped automatically.

## Slug conventions per language

| Lang | Polylang slug | URL prefix on WoM | Slug pattern |
|------|---------------|-------------------|---------------|
| IT   | `it`          | (none, root)      | `meaningful-italian-keywords` |
| EN   | `en-us`       | `/en-us/`         | `en-meaningful-english-keywords` |
| DE   | `de`          | `/de/`            | `de-meaningful-german-keywords` |
| FR   | `fr`          | `/fr/`            | `fr-meaningful-french-keywords` |

The `en-` / `de-` / `fr-` prefix in the slug is NOT a Polylang requirement — it's a project convention for visibility and to avoid slug collisions. Keep it.

## Canonical template (IT, adapt per language)

```markdown
# IT — Radar post

**Slug**: `comprare-meno-comprare-vero-divieto-ue-invenduto`
**Titolo**: Comprare meno, comprare vero: l'Europa mette fuorilegge la distruzione del tessile
**Categoria**: Radar (term ID 324)
**Lingua Polylang**: `it`

## SEO Rank Math

- **Title** (59ch): `Divieto UE invenduto tessile: cosa cambia dal 19 luglio | WoM`
- **Description** (153ch): `Dal 19 luglio 2026 l'Europa vieta la distruzione del tessile invenduto. Perché è una svolta per il guardaroba consapevole. Analisi World of Merino.`
- **Focus keyword**: `divieto UE invenduto tessile`

## Corpo (Gutenberg blocks)

\`\`\`html
<!-- wp:paragraph {"className":"lead"} -->
<p class="lead">Lead paragraph (3-4 sentences).</p>
<!-- /wp:paragraph -->

<!-- wp:heading -->
<h2 class="wp-block-heading">First H2</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>Body paragraph.</p>
<!-- /wp:paragraph -->

[... 3-4 more H2 + paragraph pairs ...]

<!-- wp:separator {"className":"is-style-wide"} -->
<hr class="wp-block-separator has-alpha-channel-opacity is-style-wide"/>
<!-- /wp:separator -->

<!-- wp:paragraph {"fontSize":"small"} -->
<p class="has-small-font-size"><em>Fonti: ...</em></p>
<!-- /wp:paragraph -->
\`\`\`

**Word count**: ~410 parole.
```

## Why no `<!-- wp:cover -->` or `<!-- wp:heading -->` for the title

The post title is rendered by the theme's article template — putting another H1 in the body creates a **duplicated hero** (we hit this exact bug on 2026-04-23 with a pre-existing post). The script trusts the theme to render the title and only sets `post_title`. The body should start with the lead paragraph, not with a repeat of the title.

Same applies to the featured image — the theme renders it from `featured_media`. Don't add a `<!-- wp:image -->` block at the top of the body.

## Translation conventions (must match upstream skills)

- DE uses formal `Sie` register, `Kapselgarderobe` / `Unsichtbarer Luxus` / `Kosten pro Tragen` glossary terms (never translate "Made in Italy", "ZQ", brand names like "Reda", "CompACT").
- FR uses `vouvoiement` register, `Garde-robe capsule` / `Luxe Invisible` / `Coût par utilisation` glossary terms.
- EN-US: minor American spelling preferences but otherwise neutral international English.

These are enforced upstream by `albeni-mt-translator` (Step 1) and `albeni-mt-validator` (Step 3). This skill does not re-validate them — it trusts the input.
