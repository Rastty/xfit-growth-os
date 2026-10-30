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

Once enabled, the **XFIT Affiliate Feed Validation** workflow can fetch the live feed daily and store its normalized catalog as a short-lived private GitHub Actions artifact; it does **not** yet publish offers.

## Important remaining step: product deep links

Affial requires the relevant product-level affiliate link for commission attribution. Their official help documents **Propagace → Banners & Links → Dynamický odkaz**, where the target URL is entered and an affiliate deeplink is generated. Do not automatically add publisher IDs to the product URLs or assume such links earn commissions until the exact scheme is confirmed.

- https://help.affial.com/article/28-vytvoreni-odkazu
- https://help.affial.com/article/13-jak-zacit-s-propagaci
- https://www.affial.com/namaximum/

Before showing offers on xfit.cz: verify prices and currency, product availability, image rights, correct Affial deeplinks, affiliate disclosure and tracking tests. The supplier's description contains marketing health/performance claims; it must not be reproduced uncritically.

## Security

A previous feed URL with a secret key was pasted in conversation. Rotate/reissue that key if possible before adding the new URL to GitHub Secrets; never paste it in issues, git files or discussion. The public repository contains no credential values.
