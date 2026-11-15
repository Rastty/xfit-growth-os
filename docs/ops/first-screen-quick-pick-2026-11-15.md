# XFIT first-screen source-bound decisions — 2026-11-15

## Observation and change

The creatine and whey advisers already have verified XML-backed price tradeoffs,
budget accordions, real affiliate cards and a no-purchase route. Their actual
product decisions were below the introduction and several explanatory blocks.

The new `xfit_quick_pick.quick_pick` module creates a compact first-screen
decision immediately after the existing feed-date notice in **both** owned
advisers:

- Lowest whole-pack checkout spend within the six displayed offers.
- Lowest cost per 100 g of powder within those same displayed offers.
- One winning option if both criteria point to the exact same product.
- Accessible first-screen link to the existing nonpurchase explanation.

Each action navigates to an on-page `#xfit-offer-N` card. No new merchant link,
JavaScript, plugin, cookie, personalized data or analytics claim is introduced.
The original affiliate links and their exact campaign IDs are untouched.

## Evidence controls

- Every highlighted price and mass is copied from a selected feed-backed card.
- Offer IDs must be unique, prices finite, and unit price must agree with mass.
- Result is labeled a selection of the *displayed* offers, not a market ranking.
- Whey still uses powder mass, not unverified grams of pure protein.
- Availability, labels, delivery charges and final price still require merchant
  confirmation; the quick decision does not claim live stock or conversion.
- A matching 44 px on-page anchor and overflow-safe card layout is checked by
  production mobile QA at a 375 px viewport.

## Hypothesis and measurement

Visitors with a clear price priority should reach a relevant product card with
less scrolling. This is a user-experience hypothesis, **not** a measured CTR or
commission increase. The existing consent-aware analytics adapter is not
verified as publicly active, so there is no attributable uplift claim. After
consent-based analytics are confirmed live, evaluate outbound click-through to
verified affiliate campaign conversions without inferring paid commissions
from pageviews.

## Release procedure

After merging, the existing creatine and whey live workflows must write and
publicly verify their two WordPress posts, preserving prewrite backup receipts.
The 375 px mobile ten-page QA must independently pass. A successful GitHub
merge alone is not proof of a visible WordPress release.
