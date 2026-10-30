# Issue #3 — preserve audit evidence despite malformed links

Prepared locally, 2026-10-30. One malformed URL in legacy article HTML could
raise ValueError and abort the archive inventory. This prevents reviewers from
assessing the remaining fitness pages and their links to useful guidance.

The audit now skips links that fail URL parsing and records invalid_link_count
per candidate and across all scanned posts. Other internal/external links and
subsequent posts are still assessed. A skipped link is unknown evidence, not
proof that a page has no useful links or permission to unpublish it.

Validation: `python -m unittest tests.test_archive_full` (7 tests), archive
ownership gate and `git diff --check`. Fixtures cover malformed IPv6 and Unicode
host syntax alongside valid internal/external links and a subsequent post.
No network requests, full-archive scan or browser QA: this changes only the
local audit report, with no rendered page changes.

Evidence limits: the full audit artifact and live issue details are unavailable
locally. This is a code/test reproduction, not a claim of affected live URLs.
User impact, traffic and affiliate outcomes remain UNKNOWN. More reliable
review evidence supports retaining useful pages before archive cleanup.

Status: prepared; local tests passed; CI UNKNOWN; WordPress deployment and public
validation not performed; measured clicks/orders UNKNOWN.

Rollback: revert this patch; no WordPress state or wave01 evidence changed.
Next step: independently validate the diff before PR creation. Review parse
failures alongside traffic and incoming links in a future authorized audit.
