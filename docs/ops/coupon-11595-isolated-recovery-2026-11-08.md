# WP 11595 — isolated recovery after the 8 Nov 2026 partial coupon batch

## Source of truth
- Scheduled run: https://github.com/Rastty/xfit-growth-os/actions/runs/42465256593
- Rollback artifact uploaded before the batch wrote: https://github.com/Rastty/xfit-growth-os/actions/runs/42465256593/artifacts/13611670652
- Run receipt: 7 existing WP articles with authenticated readback; 21 obsolete `5NM2022` shortcodes removed; WP 11595 `write_request / unchanged`; no uncertain posts, deletes or redirects. This is **PARTIAL**, not an all-green public verification.
- Unresolved tracking issue: https://github.com/Rastty/xfit-growth-os/issues/75

## Immediate protection
`scripts/xfit_coupon_cleanup.py` quarantines **only** 11595 (along with previously isolated 11945) from future bulk attempts. The outstanding old code in 11595 is still tracked in issue #75 and is not silently counted as fixed. All seven prior successful articles are untouched by recovery.

## One-shot repair
`.github/workflows/xfit-coupon-post-11595-recovery.yml` triggers only once on a merge that changes this workflow or via explicit manual dispatch. There is no recurring one-post schedule.

1. Authenticated REST read pins WP ID 11595, published status, a valid matching canonical Xfit HTTPS slug/URL, existing body and exactly three known `5NM2022` blocks (zero allowed only as verified no-write). Reject unknown/restructured text.
2. Read-only snapshot stores the full original HTML, source SHA256, intended target SHA256, post identity and zero remote writes.
3. **Mandatory** uploaded 90-day rollback artifact before any possible POST. If artifact upload fails, no write step runs.
4. Authenticated read immediately before write must match exact snapshot bytes and SHA. One `posts/11595` content-only POST; absolutely no POST retry.
5. Authenticated readback reconciles even ambiguous HTTP errors. Only exact expected updated SHA can progress to an independent public GET of the identical canonical permalink, with the old code absent and visible H1. Mismatches, unchanged source or stale public cache fail with no false `PUBLIC_VERIFIED`.
6. Record `PUBLIC_VERIFIED` including URL and exact one-post/three-block count, or leave issue open with actual error. This task cannot edit any other article, affiliate URL or WordPress plugin.

## Rollback
Download the immutable per-run artifact only if a rollback is necessary. Re-read today's production source before restoring anything; do not overwrite later legitimate editor changes. This change itself introduces no redirects, deletes, new pages or plugins.
