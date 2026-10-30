# Issue #3 — accurate internal-link evidence

Prepared locally, 2026-10-30. The archive audit counted any href containing
`xfit.cz/` as internal, including foreign URLs with that text in a path or query.
It missed relative links. This could mislead review of useful Czech fitness
pages and their navigation to relevant guidance before archive cleanup.

The audit now resolves relative URLs and checks the exact HTTP(S) hostname
(`xfit.cz` or `www.xfit.cz`, case insensitive). Empty links and in-page anchors
do not count as links between archive pages. This remains an outgoing-link
count, not an incoming-link inventory or permission to unpublish a page.

Validation: `python -m unittest tests.test_archive_full` passed all 5 tests,
including relative links, foreign paths/query strings, deceptive hosts,
userinfo, anchors and non-HTTP links. Archive ownership gate and diff whitespace
check passed. No network requests or full-archive scan were performed.

Evidence limits: the full 11,814-post audit artifact and live issue #3 details
were not available locally; existing repository tests and code supplied the
reproduction. Traffic, conversions and user impact remain UNKNOWN.

Release status: prepared; local tests passed; CI UNKNOWN; WordPress deployment
not performed; public validation not performed; measured clicks/orders UNKNOWN.

Rollback: restore the prior link-counting code and remove the two new tests
and this report. No WordPress state or wave01 evidence changed.
Next step: independently validate the diff; use the corrected evidence in a
future authorized audit alongside 90-day GA4/GSC and incoming-link review.
