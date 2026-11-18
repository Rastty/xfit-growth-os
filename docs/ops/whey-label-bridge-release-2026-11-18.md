# Whey: label-price explanation before the first merchant link (2026-11-18)

## Trigger and bounded correction

Live Chromium run [44345255340](https://github.com/Rastty/xfit-growth-os/actions/runs/44345255340), second attempt, caught `whey_label_price_education_link_missing_or_not_early`. The previous release moved the verified quick choice above the long explanation, inadvertently placing the link to the independent nutrition-label cost method below that choice. The real browser saw the quick decisions and products correctly; the specific early-education invariant failed.

The correction moves the **one** existing first-party nutrition-label calculation link into the whey quick-choice panel, **before its first sponsored merchant action**. It preserves the price-per-100g-powder ranking, public method limitations, milk allergy warning, delivery cautions, verified product URLs, no-purchase option, and short hero position. Creatine choices are unaffected. This is not a claim of improved sales or measured clicks.

## Verification and release gate

- Full Python and JavaScript tests, including the precise ordering assertion.
- PR preview Chromium 320/375/768 px checks tap target, layout, offer visibility and the first-party label link before affiliate CTA.
- Only then merge; normal whey publisher backs up and updates the owned WP post 25456. Production Chromium must verify **actual live** ordering, not only generated HTML. Creatine post 25455 needs no change.
- If either publishing or mobile browser QA fails, mark release incomplete and investigate; do not claim the page is verified.

Rollback: revert the bounded generation change and use the existing one-page backup + verified WordPress publisher. No cache, GA4, CMP, affiliate campaign or hosting settings are modified here.
