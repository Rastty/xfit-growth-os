# Xfit — Affial NaMaximum affiliate feed setup

## Verified from the owner's Heureka XML sample (2026-10-30)

- XML feed host: `greenmedical.venalio.com/feeds/heureka` — feed service / supplier infrastructure.
- Actual SHOPITEM/URL product host: `www.namaximum.cz` — **the correct merchant** for the Affial campaign.
- Example: ITEM_ID 392, Creatine Pure - Creapure Natural 1kg, EAN 8586017480698, URL path `/kategorie/kreatin/creatine-creapure?variant=392`, image on `greenmedical.bwcdn.net`.
- The PRODUCTNAME and destination are enough to correct the prior host-based mismatch assessment. The full feed has **not** yet been fetched/validated; example has no price, so none is invented.
- Feed URLs may include Heureka `utm_source=heureka&utm_medium=cpc`. These should NOT be reused as affiliate links. The parser strips those tracking parameters while preserving `variant=392`.
- Importer only accepts product URLs on namaximum.cz/www.namaximum.cz, skips other merchant URLs and restricted product classes, and leaves product affiliate_url empty pending validated product-level deeplinks.
- Feed source identity and merchant identity are deliberately separate.

## Required GitHub Secrets

Go to Settings → Secrets and variables → Actions → Secrets.

1. `XFIT_AFFIL_DEFAULT_LINK`: the corrected NaMaximum.cz homepage referral URL generated in **Affial.com**, with the original PAP tracking IDs.
2. `XFIT_NAMAXIMUM_FEED_URL`: the complete XML feed URL including the secret key. For backwards compatibility, the workflow also reads `XFIT_GREENMEDICAL_FEED_URL` if already configured. **Do not duplicate the secret unnecessarily.**
3. Under Actions **Variables**, set `XFIT_AFFIL_FEED_ENABLED=true`.

Once enabled, the **XFIT Affiliate Feed Validation** workflow can fetch the live feed daily and store only a **redacted aggregate summary** in a short-lived GitHub Actions artifact. The full catalog remains on the temporary runner and is not uploaded; the workflow does **not** publish offers.

## Important remaining step: product deep links

Affial requires the relevant product-level affiliate link for commission attribution. Their official help documents **Propagace → Banners & Links → Dynamický odkaz**, where the target URL is entered and an affiliate deeplink is generated. Do not automatically add publisher IDs to the product URLs or assume such links earn commissions until the exact scheme is confirmed.

- https://help.affial.com/article/28-vytvoreni-odkazu
- https://help.affial.com/article/13-jak-zacit-s-propagaci
- https://www.affial.com/namaximum/

Before showing offers on xfit.cz: verify prices and currency, product availability, image rights, correct Affial deeplinks, affiliate disclosure and tracking tests. The supplier's description contains marketing health/performance claims; it must not be reproduced uncritically.

## Security

A previous feed URL with a secret key was pasted in conversation. Rotate/reissue that key if possible before adding the new URL to GitHub Secrets; never paste it in issues, git files or discussion. The public repository contains no credential values.

**Note:** This repository is public; GitHub Actions artifacts must not be considered private. The workflow therefore uploads counts and category totals only, never the full feed product list, secret URL, or affiliate tracking link.

## Confirmed authenticated import, 2026-10-30

- Run: https://github.com/Rastty/xfit-growth-os/actions/runs/41094083014
- Successfully normalized 1,485 offers from NaMaximum feed; excluded 6 products under restricted-products safety filter.
- Merchant verified via each item's namaximum.cz URL, not GreenMedical feed host.
- Top categories: Kapsle/Tablety 84, Proteiny na objem 53, Syrovátkové proteiny 51, Pánská trička 51, Pánské mikiny 49. Categories are not necessarily mutually exclusive.
- All 1,485 included offers have image URL and EAN; 1,473 have a category.
- scripts/xfit_select.py created for deterministic creatine / whey / plant protein candidate shortlists. At <=1,500 CZK shortlist sizes were 12 / 12 / 2; first two are capped at 12 and not total offer counts.
- Feed authentication and affiliate base-link formatting both work. Product-level commission attribution has not yet been verified and there is no public affiliate product selector.
- Public GitHub artifacts contain only redacted aggregate counts, never raw feed secrets or full catalog.
