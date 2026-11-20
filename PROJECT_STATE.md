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
- Original open PR inventory (before subsequent merges): #248 UX, #261 archive, #262 revenue, #263 editorial. **Current open PRs: #248 and #263**; #261 and #262 are now merged. #263 references the old chooser JSON hash/text and must be reconciled with #265 before merging. Avoid overlapping edits by other workers.
- Broader theme/ad/cookie changes still lack a proven release and rollback path; do not bypass CMP or WordPress ownership guards.

## Next priority cycles, by expected business value
1. **Revenue attribution:** establish actual consent-safe `advisor_start` / `advisor_complete` / `affiliate_outbound_click` collection and independent Affial approved/paid reporting. Read live preflight artifacts first; no health answers/PII in events; no fabricated revenue.
2. **Mobile first screen:** measure at 320/375/768px and address ad + cookie banner interference via a separately verified theme/asset deployment path. Respect consent, assess PR #248 before overlap.
3. **Traffic-backed existing landing improvements:** prioritize verified GSC/GA4 organic entry pages and qualified comparison handoffs; do not duplicate completed creatine/whey pages or bulk-create articles.

## Rollback
Original article JSON is retained in Git history before PR #265 (`a40b11f4`). Revert only the exact owned WordPress post #25504 through the existing guarded native publisher, and re-verify authenticated readback and the public URL. No archive deletions, redirects or plugin changes were performed in this cycle.

## Additional verified evidence (2026-11-20)
- **XFIT Analytics/CMP preflight 44765199965:** both public advisers are readable and each has **8 catalog CTA metadata elements**; Google tag and WebToffee v3 fingerprints exist. However `first_party_analytics_script_reference=false`, `first_party_consent_bridge_script_reference=false`, `xfit_analytics_plugin_state=NOT_INSTALLED`; `analytics_event_observed=false`, `consent_decision_observed=false`. Success means a completed read-only audit, not live tracking. Relevant deployment requirements remain in `docs/revenue/webtoffee3-deployment.md` and issue #5.
- **Private feed validation 44742203784:** normalized **1,604** products with 9 sensitive items skipped; XML dispatch status showed **12 `feed_stocked` candidates for creatine** and **12 for whey**. This is feed-snapshot evidence, not proof of live merchant stock for each shown card. Later 2026-11-20 adviser runs **44752344059/44753138491** ended `live_verified` for WP 25455/25456.
- **UX PR #248** cleanly integrates with current `main` in a local non-publishing review; 696 full tests and 34 focused tests pass. **Not merged/deployed:** required mobile preview workflow is `action_required` and 320/375/768 Chromium screenshots are missing. Do not bypass workflow approval.
- **Current XFIT GSC retrieval:** Windsor.ai connected Search Console inventory has no `xfit.cz` property, so current XFIT impressions/clicks/position could not be sourced through that connector. Do not substitute other sites' data. Historical XFIT exports remain informative but are not a current live performance read.

## Subsequent TURBO completions (2026-11-20)
- **PR #261**, squash `33a315e7`: full-archive audit now fails closed when `X-WP-TotalPages` changes during pagination. The reconciled local full suite **697 PASS**, focused archive suite **32 PASS**, GitHub code checks [44769247820](https://github.com/Rastty/xfit-growth-os/actions/runs/44769247820) SUCCESS. Automatic **read-only** full inventory [44769247653](https://github.com/Rastty/xfit-growth-os/actions/runs/44769247653) was **IN_PROGRESS at this checkpoint**; its completeness and candidate findings must not be claimed until the final result is inspected. No WordPress mutations.
- **PR #262**, squash `0c22a3a4`: offline event validator now distinguishes missing catalog, explicitly empty catalog and unmatched product ID without logging private input. Reconciled local full suite **698 PASS**, focused revenue suite **17 PASS**, code checks [44769424232](https://github.com/Rastty/xfit-growth-os/actions/runs/44769424232) SUCCESS. This does **not** install browser instrumentation or prove any GA4 event.
