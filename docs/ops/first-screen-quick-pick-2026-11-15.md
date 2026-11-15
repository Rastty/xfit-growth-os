# XFIT first-screen source-bound decisions — 2026-11-15

## Observation and change

The creatine and whey advisers already have verified XML-backed price tradeoffs,
budget accordions, real affiliate cards and a no-purchase route. Their actual
product decisions were below the introduction and several explanatory blocks.

The new `xfit_quick_pick.quick_pick` module creates a compact early decision in
**both** owned advisers. On whey, the existing explanation that powder weight
is not pure protein and its nutritional-label comparison link remain before
the choice; on creatine, the choice follows the feed-date notice:

- Lowest whole-pack checkout spend within the six displayed offers.
- Lowest cost per 100 g of powder within those same displayed offers.
- One winning option if both criteria point to the exact same product.
- Accessible first-screen link to the existing nonpurchase explanation.

The first rollout used `#xfit-offer-N` anchors. The follow-up adds a visible
**one-click "Ověřit cenu a dostupnost" merchant CTA** and keeps a secondary
`#xfit-offer-N` detail link. The primary CTA reuses the exact tracked URL from
its corresponding lower product card, rather than constructing another offer.
The first-screen affiliate disclosure and no-purchase route appear before any
merchant CTA. No new plugin, cookie, personal data or conversion claim is added.

## Evidence controls

- Every highlighted price and mass is copied from a selected feed-backed card.
- Offer IDs must be unique, prices finite, and unit price must agree with mass.
- Result is labeled a selection of the *displayed* offers, not a market ranking.
- Whey still uses powder mass, not unverified grams of pure protein.
- Availability, labels, delivery charges and final price still require merchant
  confirmation; the quick decision does not claim live stock or conversion.
- The exact first-screen tracked URL, product ID, engine and partner must match
  the existing card; malformed URLs, other domains, mismatched variants,
  missing/duplicate campaign parameters or unverified products block release.
- Both the 44 px direct merchant CTA and 44 px on-page detail anchor are checked
  by production mobile QA at 375 px without triggering an actual merchant click.
- The opt-in analytics adapter recognizes the added CTA context but emits no
  events without *current* verified WebToffee analytics consent and GA4; it
  transmits no affiliate credentials, page query parameters or visitor details.

### Ongoing public health contract

The scheduled `XFIT Affiliate Link Health` workflow now checks **both** the
lower product cards and the new first-screen direct merchant CTAs against
WordPress REST's rendered content and the independent public page. Per adviser:

- Exactly one `xfit-rychly-vyber` section, with one or two merchant CTAs.
- Each hero CTA retains its sponsored rel, valid Affial campaign identifiers,
  source catalog engine/partner/product ID and **identical** merchant URL to
  its corresponding product card (query order may differ).
- The hero includes readable affiliate disclosure and its no-purchase link.
- A broken link fails even when WordPress and the public page contain the
  **same** broken URL; cross-surface parity alone is not sufficient.
- Reports provide only counts and typed errors; catalog IDs, affiliate IDs,
  merchant deeplinks and personal data are never included in the output.

This is an early warning for purchase-path breakage, **not** evidence of
actual clicks, valid orders or paid commission. No merchant URLs are visited.

## Hypothesis and measurement

Visitors with a clear price priority should be able to open a source-verified
offer in one click instead of scrolling and clicking twice. This is a
conversion hypothesis, **not** a measured CTR or commission increase.
On 2026-11-15, the attached Windsor.ai GA4 connector exposed a property for
SpecialMagicKitchen only, **not XFIT**; XFIT GA4 funnel values remain
`UNKNOWN`. The consent-aware analytics adapter is also not verified as publicly
active. Do not label these UX changes as recorded click or commission growth.
Once actual consented XFIT tracking is connected and verified, compare
page-level outgoing click actions with separately reconciled Affial approved
and *paid* commissions; pageviews or clicks are not sales.

## Release procedure

After merging, the existing creatine and whey live workflows must write and
publicly verify their two WordPress posts, preserving prewrite backup receipts.
The 375 px mobile ten-page QA must independently pass. A successful GitHub
merge alone is not proof of a visible WordPress release.
