# Protein guide: reader-first early decision paths (2026-11-20)

## Problem and bounded change

The indexed educational article at `/xfit-os-protein-guide/`, WordPress **25451**, already links to the whey comparison, but the practical product handoff follows seven long sections. The reader has no immediate route to check whether supplementation is needed, compare real-label unit economics or see current merchant-catalog offers.

Add three first-party, 48px-minimum-height actions **after the existing introduction and before the first table**:

1. Check protein intake from ordinary food (non-purchase route).
2. Compare cost using the actual nutrition label.
3. Compare whey offers at the existing single-merchant adviser; explicitly disclose affiliate links and stock limitations.

No new post, feed ranking, merchant URL, consent event, plugin or price claim. This is a discoverability/click-path hypothesis, not a measured lift.

## Release and rollback

- `scripts/xfit_protein_early_choices_release.py` checks the exact post ID, owned slug, HTTPS canonical URL, published status, intact reviewed introduction and absence of an earlier partial panel.
- It reads **current** WP raw HTML, preserving every later editorial change. The older `content/ready/*.json` is used only to pin the introduction; it is **never republished**.
- Required immutable Actions artifact saves the full original raw source and modified timestamp before the sole allowed WP POST. A concurrent edit stops the release. Timeout after POST is reconciled with one authenticated GET, **never retried**.
- Public same-URL readback must show exactly one early panel with all three links, correct explanatory copy and no direct merchant link. CI then uses actual Chromium at 320/375/768px to check touch target dimensions, destinations and horizontal overflow.
- If the release produces a bad result, retrieve the artifact named `xfit-protein-early-choices-25451-rollback-<run>`; verify current WordPress raw SHA against the expected post-write SHA and restore *only* post 25451 through a separate reviewed, single-post guarded rollback. Do not overwrite a newer concurrent revision.

## Measurement boundary

No present GA4/consent proof. After the approved analytics plugin is installed, inspect internal choice selection and subsequent partner outbound events with privacy-safe aggregate counts. Actual orders and approved/paid Affial commission remain `UNKNOWN` until independently reconciled.
