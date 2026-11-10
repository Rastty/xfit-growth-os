# Issue #3 — distinguish self-links from archive navigation

Prepared locally, 2026-11-10. The existing audit excluded fragment-only
anchors but counted absolute permalinks and root-relative links back to the
same article as navigation to other pages. This inflated evidence used when
reviewing useful Czech fitness and supplement guidance before cleanup.
Reproduction is synthetic; no affected live URL or traffic result is claimed.

Resolve relative links against the article permalink and exclude internal
destinations with the same path and query (including fragment variants and
the www host alias). Links to another article or another query remain counted.
This counts outgoing destinations, not incoming links, browser visibility,
traffic or verified affiliate clicks. It does not authorize archive removal.
More accurate evidence supports preserving useful reader journeys to guidance
and transparent purchase decisions; monetization impact remains UNKNOWN.

Validation: `python -m unittest tests.test_archive_full` passed 18 tests,
including two new regressions for self-links and query-relative navigation.
The archive ownership gate and `git diff --check` passed. No network access,
archive scan, production changes or mobile browser QA were performed.
The full audit artifact and current issue details are absent from this checkout.

Status: prepared and locally tested; CI UNKNOWN; deployed WP API: not performed;
public page validated: not performed; measured clicks/orders: UNKNOWN.

Rollback: revert this three-file patch; no WordPress state changed.
Next step: independent diff validation and PR creation. Any future cleanup
still requires 90-day GA4/GSC evidence, incoming-link review and rollback.
