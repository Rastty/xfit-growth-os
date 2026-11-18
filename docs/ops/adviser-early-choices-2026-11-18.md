# XFIT: merchant choices before lengthy explanation (2026-11-18)

## Observed visitor defect

The public whey adviser on 2026-11-18 had its source-backed quick purchase
choices after the navigation list and multiple long paragraphs. The verified
offer CTA existed but a reader had to scroll through methodology and budget
caveats before encountering it. The creatine adviser followed the same order.
This is a visibility hypothesis, **not evidence of conversion lift**.

## Bounded change

- Both existing advisers now place their catalog retrieval notice, relevant
  medical/allergen caution, visible checkout-cost and single-merchant limits,
  then the already-verified quick price choices at the start of the page.
  Long methods, price tradeoffs and on-page navigation remain below. The exact
  merchant URLs, offers, price ranking, CSS tap targets and opt-out route are
  unchanged.
- The quick-choice introduction is shorter while maintaining affiliate
  disclosure before merchant links and the alternative not to buy.
- Creatine's detailed product CTAs now expose an accessible, per-link affiliate
  disclosure, matching the previously reviewed whey implementation.
- No new offer, clinical outcome, event payload, plugin or URL is created.

## Controls and release

1. Python guide and source-bound tracking tests plus complete code suite.
2. Local generated Chromium 320/375/768 px test asserts no horizontal overflow,
   >=44 px merchant targets, and priority choices before the navigation; it
   never clicks merchants. An isolated PR-check workflow executes the same
   test with pinned Playwright **before merge**, and mobile production QA runs
   again after release.
3. Merge triggers both native WP one-page adviser workflows. Each backs up the
   article, updates only on changed content, then checks the public permalink.
   The separate mobile QA waits for the same-commit releases.
4. Do not call it deployed unless the per-adviser workflow and independent
   public check confirm the new sequence. No observed clicks/orders/paid
   commissions = `UNKNOWN`; do not infer a sales lift.

Rollback: restore the pre-deploy backed-up exact WordPress raw body (checking
post identity and current hash), or revert this commit and let the normal
fail-closed adviser publishers regenerate prior markup from fresh verified feed.
