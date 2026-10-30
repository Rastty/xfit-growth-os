# Xfit — affiliate feed onboarding (private authorization)

Status: **awaiting GitHub Secrets and first real feed validation**.
User identifies affiliate program as Affial.com. Supplied tracking URL points to ehub.cz;
that is a PROVIDER MISMATCH needing confirmation in Affial's actual campaign UI.
Venalio Heureka XML feed is separate and does not establish attribution.

## Required GitHub configuration

Settings > Secrets and variables > Actions > New repository secret:
- `XFIT_GREENMEDICAL_FEED_URL`: complete HTTPS feed URL including authorization
  query string, pasted directly into GitHub's encrypted secret (not into git).
- `XFIT_AFFIL_DEFAULT_LINK`: the actual tracking URL generated in the approved Affial.com campaign.
  Do not assume a URL pointing to ehub.cz belongs to Affial.

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
The provided click link uses an ehub.cz hostname, not affial.com. Ask the publisher
to compare against the Affial.com administration under Propagace / Banners & Links
and its generated tracking link. Product offers remain PRIVATE_REVIEW_REQUIRED.

## Preconditions before first live affiliate page

1. Real feed accessible and proper products/categories identified.
2. Currency, price freshness, availability and image rights checked.
3. Merchant-to-Affial campaign click redirect mapping confirmed.
4. Product-level deeplink syntax confirmed in Affial/in advertiser UI (default
   affiliate click is usually a store link, NOT a product-specific link).
5. Editorial health-claim safeguards applied; do not claim that supplements
   treat illnesses, injuries, or chronic conditions.
6. Only then generate a relevant product guide and test live clicks.
7. Register outbound click events and affiliate disclosure.

This feed pipeline is deliberately validation-only until those gates pass.
