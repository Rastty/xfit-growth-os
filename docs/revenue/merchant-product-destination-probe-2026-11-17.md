# XFIT — independent merchant destination check (2026-11-17)

## Reader problem

A valid affiliate URL and an in-stock-looking XML row cannot guarantee that
the shop still serves the exact product page. The existing XFIT public parity
audit correctly verifies campaign params, merchant host, catalog variant and
the actual visitor-facing cards, but does **not** visit merchant destinations.

## Bounded, privacy-preserving diagnostic

`scripts/xfit_merchant_destination_probe.py` runs after public parity in the
daily `XFIT Affiliate Link Health` workflow. It reads only the six public
creatine and six whey product cards, validates each catalog ID against its
single `variant`, strips **all** Affial/UTM/custom origin parameters and only
then sends a GET to `https://www.namaximum.cz/...?...variant=N` (or the
allowlisted apex host). It sends no referrer, cookies or product/health
answers. It rejects redirects to another host, product path or query string.
There are at most twelve requests with a nine-second timeout apiece.

Only aggregate counts by existing public XFIT page and outcome appear in
the Actions log: `HTTP_2XX`, `SUSPECT_404_OR_410`, or
`UNKNOWN_ROBOT_OR_NETWORK`. Merchant URLs, product IDs and campaign IDs are
never printed. A response from a robot does **not** establish human-visible
stock availability, checkout success or affiliate credit.

## No automatic product removal

- `HTTP_2XX`: the merchant served a response to this robot; stock remains **UNKNOWN**.
- `SUSPECT_404_OR_410`: investigate the exact product/variant manually on
  merchant site and compare with a fresh feed before changing XFIT cards.
  A bot-visible 404/410 is not proof that ordinary buyers cannot purchase.
- `UNKNOWN_ROBOT_OR_NETWORK`: 403, 429, 5xx, redirects, timeout or other
  errors are not purchase failures. No negative ranking or card removal.

This task never mutates WordPress, rankings, affiliate links or analytics.
It exits successfully on merchant non-2xx diagnostics, preserving independent
CI and the last verified page rather than triggering a blind rewrite.
Only malformed local page / unsafe link evidence is a diagnostic failure.

## Validation and rollback

Run `python -m unittest tests.test_merchant_destination_probe -v` and the
normal XFIT full suite. Inspect the actual production workflow output after
merge; code coverage alone does not prove the merchant served any page.
Rollback: revert the script, tests, documentation and one added workflow step.

Affiliate orders, credited clicks, payments and commissions stay `UNKNOWN`
until actual consented measurement and verified network exports exist.
