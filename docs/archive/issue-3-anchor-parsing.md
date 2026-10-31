# Issue #3 — count actual HTML anchor destinations

Prepared locally, 2026-10-31. Existing archive link-evidence tests and code
showed that the href regex missed valid whitespace/unquoted attributes and
counted data-href, commented links and script templates as navigation.
This could obscure useful fitness guidance or falsely flag a page as linking
to a spam host. Reproductions use synthetic fixtures, not observed live URLs.

Use the standard-library HTML parser to collect anchor href attributes.
Keep the existing hostname checks and malformed-URL evidence. Decode HTML
entities once. Link counts remain outgoing evidence, not incoming-link counts,
traffic measurements, browser visibility checks or permission to unpublish.

Validation: `python -m unittest tests.test_archive_full` (10 tests),
`python scripts/xfit_agent_scope.py --lane archive` and `git diff --check`.
No network requests, full-archive scan or rendered-page changes; mobile QA
was not performed. The full audit artifact and live issue details are absent
from this checkout. No changes to wave01 or WordPress state.

Status: prepared; local tests passed; CI UNKNOWN; WP deployment and public
validation not performed; measured clicks/orders and user impact UNKNOWN.
More accurate link evidence supports preserving useful reader journeys before
cleanup; no monetization result is claimed.

Rollback: revert this patch. Next step: independent diff validation and PR;
future authorized cleanup still needs traffic, incoming links and rollback.
