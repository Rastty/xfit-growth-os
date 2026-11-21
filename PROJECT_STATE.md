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

## Next priorities
1. Evidence-backed organic acquisition: improve qualified entry pages and true topical internal paths; no filler and no repeat #3394.
2. End-to-end verified measurement: approve/install analytics package on first-party WordPress, test WebToffee 3 consent states and GA4 DebugView, reconcile Affial approved vs paid.
3. Existing adviser product quality and price freshness: source-based catalog checks and accessible decision UX, verified by public/mobile readback.

Reporting: https://github.com/Rastty/xfit-growth-os/issues/1 . Keep GitHub CI/merge, WP deployment, public verification and actual earnings strictly separate.
