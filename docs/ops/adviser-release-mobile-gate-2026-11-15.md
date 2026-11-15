# XFIT adviser release → public mobile QA — 2026-11-15

## Reproduced gap

The published first-screen quick-pick change touched two adviser generators and
the mobile QA script, so all three workflows happened to run. A subsequent whey
content-only hotfix **did not trigger mobile QA**: the `push.paths` filter watched
only the QA script itself and navigation checks. Furthermore, the mobile run
could begin observing the public page before the WordPress writer finished.

The shared `scripts/xfit_quick_pick.py` was also missing from *both* adviser
release path filters. Editing the module alone would leave live pages unchanged
until a scheduled run or an unrelated source edit.

## Fix

1. Both adviser release workflows now monitor the shared quick-pick module and
   its tests, so a module change triggers both WordPress refreshes.
2. Mobile QA monitors the union of source and test paths that can trigger either
   adviser release (and its own existing paths).
3. On a `push` to `main`, the mobile job uses a **read-only** GitHub comparison
   of previous and current commit. It loads each live workflow's `push.paths`
   filter, computes which releases the exact change requires and waits for
   **successful runs for the same commit** before launching Chromium.
4. A failed, skipped or overdue required live release fails closed; no premature
   green mobile status is possible for a deployment that has not completed.
5. Manual/scheduled mobile QA continues to inspect whatever is currently public;
   the commit-specific gate runs only for push events.

## Controls

- No new WordPress plugin, merchant traffic, affiliate link or production write.
- Read-only GitHub `contents: read` and `actions: read`; no elevated token scope.
- Compare changed filenames from the push's before/after SHA; fail on missing or
  truncated compare evidence rather than assuming release completion.
- Unit test asserts mobile QA path coverage remains a superset of both live
  release filters. Future shared dependencies cannot be silently omitted.
- Gate timeout 14 minutes; total mobile job timeout remains 20 minutes.
- Keep source-backup and `live_verified` receipts in the existing two release
  workflows; QA success is separate browser evidence, not a proxy for a write.

## Verification

Run `python -m unittest discover -s tests -p test_release_gate.py -v`, full
unit tests and YAML parse, then merge. Confirm the main-commit runs show both
live adviser releases succeeded *before* the 10-page mobile browser test. This
document does not itself claim that the new automation was production-verified.
