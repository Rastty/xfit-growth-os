# XFIT archive wave01 — fresh evidence required before draft unpublishing

The reversible 34-post off-topic e-bike cleanup is **staged, not executed by
this change**. Its allowlist in `config/xfit-offtopic-wave01.json` still cites
GA4 ending **2026-10-29** and GSC ending **2026-10-28**. On 2026-11-17 these
observations are 19 and 20 days old respectively; they do not prove zero
traffic or zero impressions today.

`scripts/xfit_archive_wave01.py` now blocks both `snapshot` and `apply`
before WordPress access unless **both** cited source windows:

- are valid approximately 90-day ranges (84–100 inclusive days),
- do not end in the future, and
- ended at most 14 UTC calendar days before the attempt.

The previously captured, complete rollback snapshot remains mandatory and
content SHA / ID / slug checks still apply. The **`restore` command deliberately
does not require fresh traffic evidence**: reversing a prior unpublish must
not become impossible merely because its original measurement aged.

This gate is a minimum temporal check, **not independent validation** that
GA4/GSC figures are correct. Before dispatching the cleanup, obtain and review
new 90-day XFIT-specific GA4 landing sessions and GSC URL metrics for every
allowlisted post; exclude any URL with observed traffic, impressions, links,
or other retention reason. Update the exact evidence periods only after that
review, rather than extending dates to bypass the gate. Independently retain
the WordPress backup artifact before any status mutation.

No article was deleted, drafted, published, redirected, or noindexed here.
