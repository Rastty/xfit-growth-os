# XFIT expired-coupon wave – public visibility proof

## Why

Existing scheduled `XFIT Expired Coupon Cleanup` runs twice daily, each with
up to eight bounded `su_button` removals and an immutable authenticated backup.
Recent run [44715718698](https://github.com/Rastty/xfit-growth-os/actions/runs/44715718698)
reported eight authenticated successful article rewrites and 24 removed
obsolete shortcodes. This does **not** by itself establish that visitors saw
the clean article: the site can cache old HTML.

## Additional read-only acceptance gate

After an unchanged workflow's prewrite snapshot and one-attempt WP POST per
article, `scripts.xfit_coupon_cleanup.public_readback()` now reuses the
already-reviewed independent `scripts.xfit_public_coupon_watch.probe()`.
For each authenticated successful post it requires:

1. Exact numeric article identity, slug and `https://xfit.cz/<slug>/` URL.
2. Public HTTP 200 HTML without unsafe redirects; canonical or body post ID
   must identify the same article.
3. Zero **visible** occurrences of the obsolete `5NM2022` code, excluding
   scripts, hidden elements and templates. A `PUBLIC_NO_COUPON_OBSERVED`
   result must also report `visible_mentions=0`.
4. Up to three read-only requests for a stale cache, with bounded waits.

The wave report separates `posts_changed`, `public_verified_post_ids`, and
`public_not_verified`. If anything is unverified, the job fails and exposes
the exact IDs and state **without repeating any WordPress POST**. Previously
authenticated successes stay intact. Public-only proof does not prove paid
affiliate conversions or a sitewide cache purge.

No new WP credentials, plugin, redirects, deletion, broadened edit pattern,
or higher batch limit. The same eight-post cap and original quarantine IDs
remain. The existing scheduled cadence is retained. Repeated independent
release runs must be evaluated by their own IDs and artifacts; no bulk
deletion or inference from the full archive's 3,132 heuristic matches.
