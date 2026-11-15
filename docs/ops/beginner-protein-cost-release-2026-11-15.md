# XFIT — skutečné porovnání ceny proteinu u začátečníků

## Evidence

- Live URL: https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/ (WP 25458).
- Verified 2026-11-15: public article still includes `<summary>Ukázkový výpočet ceny proteinu (modelová čísla, žádná nabídka)</summary>` and illustrative 900 Kč / 133 Kč, not a repeatable buyer workflow.
- Reviewed editorial fix originated in [PR #149](https://github.com/Rastty/xfit-growth-os/pull/149): source-hash-bound proposal with exact `original` and `replacement`, local arithmetic tests and no new medical or product claims.

## Outcome intended for the reader

An expandable decision tool instructs the reader to check the real powder label for their flavor, calculate total protein in the pack, divide the actual basket total (including relevant shipping/fees) by grams of protein, and compare genuine offers. It explicitly recommends ordinary food if sufficient, refuses to guess without data, and warns that price alone doesn't assess allergens, suitability or taste. The illustrative 900 Kč product price disappears; the transparent 900 g × 75 g/100 g = 675 g arithmetic remains.

## Release contract

1. Match the reviewed `editor-beginner-protein-cost.json` to immutable ready-source file/content SHA, then inspect the **current** authenticated WordPress body (not the potentially stale ready file).
2. Verify ID 25458, slug, canonical URL, published state and owned marker. Require the original block exactly once and new block absent.
3. Preserve all other live content, title, excerpt, featured image, links and headings; editorial gate the full revised body.
4. Archive the complete original raw HTML plus hashes and metadata as an Actions artifact before any POST.
5. At most one native WordPress REST content POST, then authenticated readback and canonical public HTML verification. Never repeat an uncertain POST automatically.
6. Run the live 375px Chrome suite after the release: it checks the actual buyer method, no fictitious price, keyboard-operable details and existing four beginner goal links.

## Recovery

If the API write is uncertain, inspect current WP content and the retained `xfit-beginner-protein-cost-before-<run>` artifact. If the article still contains the exact new block and no newer human edits, a manual content-only reversal can replace that block once with the saved original; alternatively restore the complete original raw HTML only after checking all other fields and concurrent changes. No plugin, redirect or URL change is part of this release. Never blindly rerun its production POST.

Affiliate clicks, attributable orders and sales impact remain **UNKNOWN** without reliable GA4/GTM and affiliate reporting.
