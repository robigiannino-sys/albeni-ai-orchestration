# Troubleshooting — wom-radar-deployer

Concrete failures encountered during the closing-the-loop build (2026-04-24) and how to recover from them.

## The endpoint returns 404

Check exactly which endpoint:

```bash
SECRET=$(grep WP_UPLOAD_SECRET ~/Documents/Claude/Projects/Merino\ News/merino-news-scanner/.env | cut -d= -f2)
for ep in upload-visual create-radar-post pll-link; do
  echo -n "$ep: "
  curl -s -m 15 -o /dev/null -w "%{http_code}\n" \
    -X POST "https://worldofmerino.com/wp-json/albeni/v1/$ep" \
    -H "X-Upload-Key: $SECRET" \
    -H "Content-Type: application/json" \
    -d '{}'
done
```

**Mapping endpoint → snippet**:

| Endpoint | Snippet ID | Snippet name |
|---|---|---|
| `upload-visual` | 2250 | "Albeni Visual Upload API" |
| `create-radar-post` | 2278 | "Albeni — Radar deploy endpoints" |
| `pll-link` | 2278 | "Albeni — Radar deploy endpoints" |

If `upload-visual` is 404 → snippet 2250 is inactive. If the other two are 404 → snippet 2278 is inactive.

**To re-activate**:

1. Open `https://worldofmerino.com/wp-admin/admin.php?page=wpcode`
2. Find the snippet by name in the list
3. Toggle "Stato" to **Attivo** (right-most column)
4. Re-test with the curl loop above

If the snippet doesn't exist anymore (deleted), recreate it from the source files in `~/Documents/Claude/Projects/Merino News/merino-news-scanner/pipeline/`. The snippet's name and toggle position are conventional, the source-of-truth is the PHP file.

## HTTP 401 albeni_unauthorized

The `WP_UPLOAD_SECRET` value in your `.env` does not match the constant defined inside the WPCode PHP snippet. They must be byte-equal.

Read both:

```bash
# .env value
grep WP_UPLOAD_SECRET ~/Documents/Claude/Projects/Merino\ News/merino-news-scanner/.env

# Snippet value: open the snippet in WPCode admin and look at the line
# define( 'ALBENI_UPLOAD_SECRET'..., 'XXXX' );  (snippet 2250)
# define( 'ALBENI_UPLOAD_SECRET_V1', 'XXXX' );  (snippet 2278)
```

Update one or both to match. Do **not** commit the secret to any public location. If rotating, rotate everywhere at once (snippet 2250, snippet 2278, .env) and verify with the 401 → 400 transition.

## Server hangs / timeouts (PHP-FPM saturation)

Symptom: the script is stuck on the first endpoint call for 60+ seconds with no response, even though the endpoint is correct and authenticated.

Root cause: Hostinger's PHP-FPM worker pool is saturated. This happens when too many heavy AJAX/REST calls land at the same instant — typical triggers are running multiple `pll_save_post_translations` in parallel, or hitting REST during a LiteSpeed cache rebuild storm.

Recovery:

1. **Stop pushing requests immediately**. Each new request takes a worker. Press Ctrl+C on the script.
2. Wait 60–120 seconds. PHP `max_execution_time` will eventually kill stuck workers.
3. Confirm the site is back: `curl -s -o /dev/null -w "%{http_code}\n" https://worldofmerino.com/` should return 200.
4. Retry `deploy_radar_post.py`.

Mitigation when designing future automation: keep handlers lean (one DB write, no loops over many posts), and don't fire concurrent requests if you can serialize them.

## Posts created but content is `<p>Loading...</p>`

This was a real failure mode of the previous Chrome-extension flow (2026-04-23 ESPR deploy). With this skill's `deploy_radar_post.py`, every `create-radar-post` call sends the full body in a single atomic POST — there is no separate "create draft + populate body" step.

If you observe empty content with this skill, something is very wrong. Likely causes:

- The content file's fenced `\`\`\`html ... \`\`\`` block is empty or malformed → parser falls back to empty string. Check the file by hand.
- The content body contains characters that break JSON serialization → improbable since Python's `json.dumps` handles all unicode, but worth verifying with `--dry-run` first.

To recover: delete the 4 empty posts (or update them with the right content via WP admin), fix the input file, re-run the script.

## 4 posts created but Polylang group not linked

After step 5 of the script, if the `pll-link` call fails, you'll have 4 orphan posts each with their own language but no translation group. The script prints the error but continues.

Manual recovery without re-running the whole script:

```bash
SECRET=$(grep WP_UPLOAD_SECRET ~/Documents/Claude/Projects/Merino\ News/merino-news-scanner/.env | cut -d= -f2)

curl -X POST https://worldofmerino.com/wp-json/albeni/v1/pll-link \
  -H "X-Upload-Key: $SECRET" \
  -H "Content-Type: application/json" \
  -d '{"group": {"it": <IT_ID>, "en-us": <EN_ID>, "de": <DE_ID>, "fr": <FR_ID>}}'
```

Replace `<IT_ID>` etc. with the IDs the script printed before failing.

## Hostinger CDN keeps serving stale content

The hcdn edge cache is independent of LiteSpeed and is not touched by REST writes. Symptoms:

- Posts visible in `wp-admin/edit.php` but the home, the `/radar/` hub, and category archives still show the old state.
- Response header `server: hcdn` and `x-litespeed-cache: hit`.

Manual purge:

1. Open `https://hpanel.hostinger.com/websites/worldofmerino.com`
2. Scroll to "Cancella la cache" / "Clear cache" panel
3. Click "Cancella la cache" / "Clear cache" → confirm in modal
4. Toast: "Cache cleaned successfully"

This purges all three layers: Caching Plugin (LiteSpeed), Hostinger CDN, Server-side cache.

For reference: there is no public Hostinger CDN purge API as of 2026-04. If/when one is exposed, the pipeline can be fully automated end-to-end.

## Related memory files

- `wom_deploy_gotchas.md` — accumulated WP/hcdn/Polylang gotchas
- `radar_espr_ban_live.md` — the ESPR session (2026-04-23/24) where this skill was prototyped, with the full bug history that informed every defensive check in this skill
