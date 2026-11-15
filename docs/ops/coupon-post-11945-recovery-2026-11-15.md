# XFIT: single-article removal of an obsolete 2022 coupon

15 November 2026: public WordPress REST for post **11945**, URL
`https://xfit.cz/jak-kreatin-muze-pomoci-ziskat-svalovy-objem-v-fitness/`,
returned published status and **three rendered instances** of `5NM2022`.
This is evidence of an obsolete promotion, not proof of a currently valid sale.

The recurring batch explicitly quarantines 11945; this one-off action must
change exactly this post or fail closed. It removes only three recognized
`[su_button]...5NM2022[/su_button]` blocks, not the remaining article,
links, pricing, redirects or plugin configuration.

1. Authenticated current raw WordPress body; exact ID, slug, published status
   and canonical HTTPS permalink.
2. Reject any changed/unexpected markup, including a non-removable coupon code.
3. Before POST, upload immutable full HTML and both source hashes as a
   **mandatory 90-day rollback artifact**.
4. Re-read the exact source/hash after the backup; at most one content-only POST.
5. Reconcile any HTTP uncertainty by readback; require exact final raw SHA-256,
   public permalink check and zero remaining `5NM2022`.
6. Success must state `PUBLIC_VERIFIED`; no retries on uncertain write, no
   imaginary SEO/revenue impact.

Workflow: `.github/workflows/xfit-coupon-post-11945-recovery.yml`.
Code: `scripts/xfit_coupon_recovery_11945.py`.

Rollback: download the immutable artifact and reconcile with the current
production body before restoring; never overwrite later legitimate edits.
