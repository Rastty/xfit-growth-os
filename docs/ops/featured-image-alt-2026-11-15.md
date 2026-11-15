# XFIT — featured image alt text (2026-11-15)

## Evidence and reader impact

Real Chrome at 375px on 10 pages: [run 43696267488](https://github.com/Rastty/xfit-growth-os/actions/runs/43696267488). Five editorial pages contain a linked featured image with `alt=""`, providing no accessible link description. The image files were individually visually inspected, not inferred from filenames.

| WP media ID | Visually verified content | Public posts using attachment |
|---|---|---|
| 2003 | Bench press with a spotter | 6440, 11945 |
| 1767 | Three women exercising on mats | 7628 |
| 1786 | Man holding a green bottle, sitting on a gym bench | 13717, 13734 |

The corrective text describes only the image. In particular, the bottle is **not** labeled as protein or a supplement; there is no visible product evidence. Existing media, source rights status, article text, post status, canonical URLs, product links and merchant attribution are not changed.

## Bounded rollout and release truth

1. Exact attachment ID and full source URL guard + five existing article IDs and permalinks.
2. Read-only preflight; immutable original media records uploaded as an Actions artifact before any POST.
3. One WordPress media REST POST with `{alt_text: ...}` per unchanged target; no blind retries.
4. Authenticated media readback; verify each of five public pages renders the exact new text on its featured image.
5. Stop on first uncertain response or public mismatch. Any incomplete step is `UNKNOWN`, not deployed proof.

The theme also includes logos and blank AdSense placeholders with intentionally empty `alt=""`: do not fabricate descriptions for decorative images. `tests/live_page_qa.cjs` now separates genuinely absent attributes from editorial featured images with empty text.

## Rollback / recovery

Get the retained `xfit-featured-image-alt-before-<run>` artifact containing exact attachment IDs and original `alt_text` values. Inspect current attachment IDs, exact source URLs and all five post assignments before any restoration. If the targeted metadata is still the value written by this release, restore only that attachment's original `alt_text` through native WP REST, one POST per item, followed by authenticated and public readback. Never overwrite a later human editor's value. This release does not delete or create content and adds no plugin.

## Monitoring

Re-run 375px live Chrome QA after public verification. `imagesMissingAlt` now counts missing attributes, not valid empty decorative alternatives. `emptyFeaturedAlt` is an explicit accessibility failure on the five target pages. GA4 conversion impact remains **UNKNOWN** until attribution is connected and observed.
