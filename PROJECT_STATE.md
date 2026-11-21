# XFIT — PROJECT_STATE

Updated: **2026-11-21**, Europe/Prague. Truth: GitHub main, Actions and authenticated + public WordPress readback. [Historical status](docs/archive/PROJECT_STATE-pre-turbo-2026-11-21.md).

## Goal
Trustworthy Czech fitness and supplement decision service. Solve reader need first, then a clearly labeled qualified affiliate option or no purchase. Grow real traffic and independently verified income; no article-count or commit-count goals. XFIT operates independently without WPVibe.

## Verified baseline — not growth
- Finalized GSC 2026-10-21..11-17: **8 Google clicks / 2,018 impressions / average position 24.73**. Pilates primary 1 click / 103 impressions; source: https://github.com/Rastty/prometheus-growth-os/actions/runs/44764745930 . GSC ≠ affiliate sales.
- NaMaximum creatine WP #25455 and whey WP #25456 were published through REST and publicly verified: https://github.com/Rastty/xfit-growth-os/actions/runs/44886082180 and https://github.com/Rastty/xfit-growth-os/actions/runs/44886082171 . Latest 11/11 real mobile QA passed: https://github.com/Rastty/xfit-growth-os/actions/runs/44886530696 . Current prices, stock and merchant checkout still require live merchant proof.
- GA4 advisor/outbound consent-gated plugin v0.1.4 is **prepared but not installed or proven ingesting**. Approved and paid Affial commissions: **UNKNOWN**, not zero.

## TURBO 2026-11-21 — publisher drift guard
- PR #313: https://github.com/Rastty/xfit-growth-os/pull/313 . Updated direct-publish pipeline compares **previous Git version** of a ready document with live WP edit-context raw text, exact link targets and raw title before any write; new file cannot overwrite an existing article; draft manual dispatch cannot unpublish a live guide.
- Verified PR CI **SUCCESS** including Python/Node tests: https://github.com/Rastty/xfit-growth-os/actions/runs/44889736937 . No WordPress content POST in this cycle. Feature becomes active when merged on main; verify separate main CI.
- Rollback: revert PR #313 if a proven false positive cannot be resolved through source reconciliation. Never silently overwrite a newer live edit.

## Post-merge WordPress automation incident — 2026-11-21
- Merge #313 triggered existing adviser release workflows because both depend on `scripts/wp_publish.py`. **Main code CI passed**: https://github.com/Rastty/xfit-growth-os/actions/runs/44889874886 . This is **not** evidence of a new WP content release.
- Creatine https://github.com/Rastty/xfit-growth-os/actions/runs/44889874916 **FAILED** at authenticated one-post prewrite backup (`XFIT_ADVISER_BACKUP_ERROR: PublishError`); **no creatine publish step executed**.
- Whey https://github.com/Rastty/xfit-growth-os/actions/runs/44889874843 **FAILED** after `ADVISER_PREWRITE_BACKUP_READY` at `XFIT_WHEY_ERROR: PublishError: Public verification failed (URLError)`; WP POST outcome is **UNKNOWN**, not safe to retry blindly. Backup artifact run 44889874843 retained for recovery. Code source/public page separately visible in web readback but not a same-run revision proof.
- Follow-on mobile QA https://github.com/Rastty/xfit-growth-os/actions/runs/44889874842 **FAILED** while awaiting same-commit live releases. Previous verified public guides and 11/11 successful mobile QA remain historical evidence, not a new pass.
- No automatic rerun; next permitted action is read-only WP/source and public reconciliation using existing source-freshness workflow before any new release. Owner-deferred WEDOS remains deferred; escalate only if this blocks ongoing monetization.
## TURBO second cycle — no unwanted release on maintenance-only push
- [PR #314](https://github.com/Rastty/xfit-growth-os/pull/314) merged as `949006a8bb67807abc9d32a159eb053c992f9d23`. Creator and whey scheduled/dispatch workflow retained; changes to real offer builders, affiliate links, catalog and selection still trigger product release.
- Shared publisher implementation, publisher-only tests and workflow YAML no longer auto-start unrelated WP content releases or their dependent mobile gate. [PR tests passed](https://github.com/Rastty/xfit-growth-os/actions/runs/44890252725); [main CI passed](https://github.com/Rastty/xfit-growth-os/actions/runs/44890302972). No new WordPress post/content publication claimed, and no observed earnings/traffic lift.
- Invariant: both live guides and mobile QA watch the same content-relevant input paths; full `scripts/**` and `tests/**` still trigger Code Checks. Rollback is revert PR #314. A daily scheduled refresh may still hit the separate WEDOS/REST issue; verify through GET readback before any retry.
## Safety and concurrency
- Legacy Pilates #3394 nested shell remains write-quarantined: previous onepost attempts failed before POST; the workflow was disabled in PR #312. Do not retry, weaken guard or discard surrounding content. Primary #3660 already has the correct title.
- WEDOS/host troubleshooting deferred by owner; #9371 and #9462 onepost safety gates remain. Analytics plugin and static protein calculator assets cannot be described as installed until first-party hosting, consent testing and public readback are proven.
- Open independent Codex PRs #248 (UX), #263 (editor), #270 (revenue), #271 (archive) must be reviewed and updated against latest main before considering any merge. No duplicate work.

## 2026-11-21 growth cycle — search-visible Pilates → existing mat guide
- **WP #3660 LIVE_VERIFIED** on the unchanged canonical URL https://xfit.cz/jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates/ . [PR #315](https://github.com/Rastty/xfit-growth-os/pull/315) built an exact one-paragraph replacement of an outdated “selection coming soon” statement with an actionable, non-affiliate link to the **existing** mat-selection guide https://xfit.cz/xfit-os-vyber-podlozky-na-cviceni/ (which already links back). Not a new page.
- First deployment [44890718720](https://github.com/Rastty/xfit-growth-os/actions/runs/44890718720) was correctly **BLOCKED before backup/POST**: the source paragraph's visible text matched but had markup. GET-only [PRs #316/#317](https://github.com/Rastty/xfit-growth-os/pull/317) proved **one candidate, 234/234 exact visible characters, one inline tag pair, zero comments, no prior link**. [PR #318](https://github.com/Rastty/xfit-growth-os/pull/318) accepted only one attribute-free harmless emphasis pair, retaining all other article HTML.
- **Actual WP release receipt:** [run 44891136451](https://github.com/Rastty/xfit-growth-os/actions/runs/44891136451) SUCCESS, original full body rollback artifact 14701778216 saved **before POST**, then **PUBLIC_VERIFIED** WP #3660, **1 POST, 1 existing post changed, 0 new posts, 0 redirects**. The run verified authenticated readback and public content/anchor. No measured search, behavior or affiliate lift claimed. Main CI from [PR #318](https://github.com/Rastty/xfit-growth-os/actions/runs/44891091817) SUCCESS.
- This is a subject-relevant organic handoff, **not** a direct monetized offer. Do not revisit unless fresh GSC or user data provides a reason; do not touch quarantined WP #3394.

## Post-incident live adviser reconciliation — 2026-11-21
- [PR #319](https://github.com/Rastty/xfit-growth-os/pull/319) safely triggered the **existing** GET-only public source-freshness job, no duplicate workflow and no POST. [Run 44891338281](https://github.com/Rastty/xfit-growth-os/actions/runs/44891338281) **SUCCESS**, `wordpress_writes: 0`.
- All four controlled decision pages `PUBLIC_FRESH` against authenticated raw and public HTML. Creatine #25455 and whey #25456 each have **6 source/public product cards, matching verified affiliate link destinations, stable commercial facts/decision paragraphs, complete CTA metadata**. Crucially the **ordinary cache view matched WordPress source** on both advisers (no observed divergence). The old whey 44889874843 POST itself is still historically **unconfirmed**, but the **current** customer-facing page is source-consistent, so do not blind retry.
- No GA4 funnel ingestion, merchant stock/checkout, approved/paid Affial commission or traffic lift established by this check. These remain unknown. Preserve owner decision to defer WEDOS unless a future scheduled release cannot maintain freshness.

## 2026-11-21 evidence-led creatine repair — LIVE
- GSC finalized 2026-10-21..11-17: existing URL `/kreatin-a-jeho-nevyhody-co-byste-meli-vedet-nez-ho-zacnete-uzivat-v-fitness/` **37 impressions, 0 clicks, avg position 21.05**; no fresh ranking measured. Previous article repeated H1/FAQ sections and incorrectly asserted creatine causes dehydration, hypertension and neck cramps.
- [PR #320](https://github.com/Rastty/xfit-growth-os/pull/320) created an evidence-backed, no-buy-first in-place rewrite with NIH ODS, Operation Supplement Safety and 2025 clinical review links. Its first production [run 44892726796](https://github.com/Rastty/xfit-growth-os/actions/runs/44892726796) was **BLOCKED before POST** on risky source markup.
- [GET-only diagnosis](https://github.com/Rastty/xfit-growth-os/actions/runs/44892975143) confirmed original **WP #11304**, raw 5,760 characters, SHA-256 `435798dbf0e51b909e9f5736be9f5a6651179b3a398653002f9306661d84e62a`, nested document shells and iframe. [PR #323](https://github.com/Rastty/xfit-growth-os/pull/323) made a **one-post exact hash+length+title+slug+ID exception**, not a blanket relaxation. Other posts, especially quarantined #3394, remain protected.
- **ACTUALLY DEPLOYED & PUBLIC VERIFIED:** [run 44893199715](https://github.com/Rastty/xfit-growth-os/actions/runs/44893199715) SUCCESS; full original body/title/excerpt backup artifact **14703275490** (run retained 90 days) uploaded BEFORE exactly one WordPress POST; authenticated and public updated-content readback `PUBLIC_VERIFIED`, **1 existing post changed, 0 new posts, 0 redirects**. Main [CI](https://github.com/Rastty/xfit-growth-os/actions/runs/44893199645) SUCCESS. No evidence yet of new Google traffic, merchant orders or commissions. External search/read cache may show a previously captured version; compare fresh direct ordinary/cached public GET if this persists.
- Source-backed editorial corrections are local to this old post. Do not rerun onepost without read-only reconciliation; all source mismatches fail closed. No Prometheus Core changes needed to perform the onepost; consider reusable hash-lease only after proven multi-project benefit.

## Next priorities
1. Evidence-backed acquisition: revisit only genuinely underperforming, source-safe entry pages from fresh GSC, and improve qualified topical navigation without filler or #3394 edits.
2. End-to-end verified measurement: install prepared analytics on first-party WordPress when owner-authorized access is ready; test WebToffee consent states and GA4 DebugView, reconcile Affial approved vs paid.
3. Existing adviser product quality and price freshness: source-based catalog checks and accessible decision UX, verified by public/mobile readback.

Reporting: https://github.com/Rastty/xfit-growth-os/issues/1 . Keep GitHub CI/merge, WP deployment, public verification and actual earnings strictly separate.
