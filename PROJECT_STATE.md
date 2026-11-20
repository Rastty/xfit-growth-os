# XFIT — PROJECT_STATE

Updated: **2026-11-20** (Europe/Prague). Source of truth: GitHub `main` + authenticated/public WordPress readback, not a previous chat.

## Goal
Help Czech fitness readers decide what (if anything) to buy: qualified search visit → useful decision → verified product comparison → consent-compliant outbound affiliate click → attributable approved/paid commission. Do not optimize for article count.

## Done and verified
- **2026-11-20:** PR [#265](https://github.com/Rastty/xfit-growth-os/pull/265) merged (`9494810`). Existing `xfit-os-kreatin-nebo-protein` now routes visitors immediately to no-purchase, whey comparison or creatine comparison; replaces hypothetical prices with checkout/label/usable-weight calculations. Public WordPress post **25504**, unchanged URL: https://xfit.cz/xfit-os-kreatin-nebo-protein/. Native publisher run [44767717759](https://github.com/Rastty/xfit-growth-os/actions/runs/44767717759) SUCCESS.
- **2026-11-20:** PR [#266](https://github.com/Rastty/xfit-growth-os/pull/266) merged (`2e8623f6`). All 3 decision links have block-sized accessible touch targets. Native publisher run [44768000280](https://github.com/Rastty/xfit-growth-os/actions/runs/44768000280) SUCCESS, including safety tests and authenticated/public readback; companion code checks [44767999738](https://github.com/Rastty/xfit-growth-os/actions/runs/44767999738) SUCCESS.
- Public WP REST: `id=25504`, `status=publish`, `modified=2026-11-20T15:54:53` UTC, 3 occurrences of `min-height:44px`, no former creatine hypothetical price. Cloud Chrome live DOM: all three links **52px** tall at **1363px** viewport, no horizontal overflow. Source before write matched all 45 editorial body segments. Local full Python suite **696 passed**; mobile-navigation unit suite **6 passed**; dry-run publisher validated.
- Existing independent feed validation, daily creatine and whey refresh, and read-only affiliate/analytics health workflows ran with GitHub SUCCESS on 2026-11-20. This does not prove conversions or merchant availability for each item.

## Blockers and evidence limits
- **Affiliate clicks, purchases, approved and paid commissions: UNKNOWN.** No verified end-to-end GA4 consent → outbound event → Affial conversion readback. Do not infer ROI from workflow success.
- **Real mobile Chrome QA at 320/375/768px: NOT DONE for this release.** Local Chromium refused an OS socket operation; cloud live browser was desktop 1363px only. The 44px geometry is proven in desktop rendered DOM, not all mobile breakpoints.
- Open PRs at time of update: **#248** UX (requires mobile preview), **#261** archive pagination guard, **#262** revenue offline catalog error distinctions, **#263** editorial proposal. #263 references the old chooser JSON hash/text and must be reconciled with #265 before merging. Avoid overlapping edits by other workers.
- Broader theme/ad/cookie changes still lack a proven release and rollback path; do not bypass CMP or WordPress ownership guards.

## Next priority cycles, by expected business value
1. **Revenue attribution:** establish actual consent-safe `advisor_start` / `advisor_complete` / `affiliate_outbound_click` collection and independent Affial approved/paid reporting. Read live preflight artifacts first; no health answers/PII in events; no fabricated revenue.
2. **Mobile first screen:** measure at 320/375/768px and address ad + cookie banner interference via a separately verified theme/asset deployment path. Respect consent, assess PR #248 before overlap.
3. **Traffic-backed existing landing improvements:** prioritize verified GSC/GA4 organic entry pages and qualified comparison handoffs; do not duplicate completed creatine/whey pages or bulk-create articles.

## Rollback
Original article JSON is retained in Git history before PR #265 (`a40b11f4`). Revert only the exact owned WordPress post #25504 through the existing guarded native publisher, and re-verify authenticated readback and the public URL. No archive deletions, redirects or plugin changes were performed in this cycle.
