# XFIT — public affiliate offer parity, 2026-11-08

## Actual problem
Previously, \`XFIT Affiliate Link Health\` validated only WordPress REST-rendered
post bodies. It could pass even when public cache, rendering or an unexpected
post-transformation exposed different affiliate product links to readers.
A valid WordPress REST read is not proof of live visitor-visible tracking.

## Read-only fail-closed addition
\`scripts/xfit_affiliate_public_audit.py\` checks both existing, fixed-ID
commercial articles (WP 25455 creatine, WP 25456 whey):
- the exact published WordPress identity, canonical HTTPS permalink and public
  page URL after redirects (reject wrong host/path, query and port);
- 2–12 product cards and exactly one link per card;
- each link's expected engine, real positive catalog item ID, NaMaximum
  merchant hostname, HTTPS product path, \`rel=sponsored\`, Affial signature
  and expected UTM campaign parameters;
- the product-card sequence and *full affiliate link destinations* match
  in WP-rendered HTML and public HTML (URL-encoding/query order ignored);
- the presence of affiliate disclosure in both representations.

No merchant links are clicked. It does not contact Affial, GA4 or analytics
providers. No new WordPress plugins, cookies, WordPress writes or
JavaScript. All private comparison fields (full URLs, affiliate IDs, catalog
IDs) are discarded before output; the log has only counts, canonical Xfit
page URLs and safe issue codes.

## Status semantics
\`PUBLIC_AFFILIATE_PARITY_VERIFIED\` proves only that public CTA links match
WordPress source and fit the configured Affial NaMaximum link shape. It **does
not prove a commissionable click** or that Affial attributed an order.
\`BLOCKED_PUBLIC_OR_TRACKING_MISMATCH\` indicates a reader-facing mismatch
or malformed CTA; no automatic WordPress rewrite should occur.

\`ga4_events\`, \`affial_orders\`, and \`commission\` remain \`UNKNOWN\` unless
real authorized account evidence exists. The owner preference is no new
WordPress plugins: this change does not require one. The existing on-site
tracking bridge remains **not proven deployed**.

## Runbook
GitHub Actions \`XFIT Affiliate Link Health\` runs daily or on updates to
itself / the new audit script / its tests. The test suite runs first, then
the existing read-only WP affiliate health, then this stricter public comparison.
Run URL: https://github.com/Rastty/xfit-growth-os/actions/workflows/xfit-affiliate-health.yml

When failed, inspect the enumerated error only; do not expose a link or
tracking secret. Reconcile live WP source, public cache and feed pipeline
through separately approved write paths. A passing code check alone does
not prove the live audit succeeds; inspect the actual workflow run.

Rollback: revert the new audit and its workflow invocation. No site
content, affiliate campaign data or WordPress configuration changes.
