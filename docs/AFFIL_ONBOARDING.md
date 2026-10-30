# Xfit — affiliate feed onboarding (private authorization)

Status: **awaiting GitHub Secrets and first real feed validation**.
The user supplied an eHUB redirect and a Venalio Heureka XML feed. These do not
by themselves prove that the eHUB link belongs to the feed's merchant, or that
eHUB product-level deep linking is supported.

## Required GitHub configuration

Settings > Secrets and variables > Actions > New repository secret:
- `XFIT_GREENMEDICAL_FEED_URL`: complete HTTPS feed URL including authorization
  query string, pasted directly into GitHub's encrypted secret (not into git).
- `XFIT_EHUB_DEFAULT_LINK`: full approved eHUB default click URL.

In **Variables** (not Secrets):
- `XFIT_AFFIL_FEED_ENABLED` = `true`

Run Actions → **XFIT Affiliate Feed Validation** → Run workflow. Once enabled,
the pipeline also checks the feed daily. It fetches the XML as a private GitHub
Actions job, validates the host and Heureka item structure, normalizes offers,
rejects restricted/sensitive product classes, and uploads a **7-day private
workflow artifact**. It never modifies the public WordPress site.

## Critical security

The originally supplied feed URL contains a credential-like `secretKey`
parameter and was posted into chat. Rotate/reissue that token in the merchant
backend if possible; paste the NEW token URL only into GitHub Secrets.
Never log, commit, publish, or store the token URL in a public document.
The eHUB click URL identifies a publisher/advertising entity; still store it
separately and validate that it matches the same approved merchant.

## Preconditions before first live affiliate page

1. Real feed accessible and proper products/categories identified.
2. Currency, price freshness, availability and image rights checked.
3. Merchant-to-eHUB click redirect mapping confirmed.
4. Product-level deeplink syntax confirmed by eHUB/in advertiser UI (default
   affiliate click is usually a store link, NOT a product-specific link).
5. Editorial health-claim safeguards applied; do not claim that supplements
   treat illnesses, injuries, or chronic conditions.
6. Only then generate a relevant product guide and test live clicks.
7. Register outbound click events and affiliate disclosure.

This feed pipeline is deliberately validation-only until those gates pass.
