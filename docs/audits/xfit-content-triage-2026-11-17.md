# XFIT: quality-first archive triage (read-only)

The 2026-11-17 complete archive audit scanned **11,787 published posts** and
detected **3,170** posts containing the obsolete `5NM2022` promotion. The old
`stale_promo_candidates` list exposed only the first 500 matches in scan order;
it was not a workload priority list. A source-title link suggestion also led to
the discovery of scientifically inaccurate claims in legacy post 4813, which was
subsequently refreshed and publicly verified in deployment run 44147669677.

## New `content_quality_review_queue`

`scripts/xfit_content_triage.py` builds a bounded editorial queue from the
existing archive classification **during the same read-only full scan**. It
requires no new requests, credentials, scheduled write jobs or WP mutations.

- Favors demonstrable reader problems (visible expired promo, thin text), plus
  older health/fitness intent and lack of observed cross-post links.
- Flags health-related titles for cautious claim review. The absence of a
  recognized scientific host from the archive's sampled external-host list
  is a **triage hint**, not proof of factual inaccuracy or missing citations.
- Excludes posts modified in the past 14 days or with unknown/future dates;
  avoids competing with parallel XFIT releases.
- Rejects noncanonical URLs and leaves spam/off-topic decisions to their
  separate moderation lane. Never recommends automated noindex, redirect,
  deletion or article replacement.
- Uses a 12-per-topic cap and stable score sorting so the top queue covers
  multiple reader intents rather than being dominated by near-identical posts.
- Contains explicit `not_covered` and `ranking_kind` fields to prevent
  mistaking heuristics for measured traffic, commission or expected ROI.

**Editorial action after a queue item:** inspect the current live body and
sources, compare competing XFIT guides, review 90-day GSC/GA4 landing metrics,
decide if a substantive correction benefits readers, and only then propose
a pinned onepost change with prewrite backup and public verification.

The existing `XFIT Full Archive Audit` workflow runs weekly, on manual
dispatch, and when the audit/triage logic changes. Its JSON artifact now
contains the quality queue alongside duplicate, coupon and internal-link
findings. No per-article automation is attached to the queue.
