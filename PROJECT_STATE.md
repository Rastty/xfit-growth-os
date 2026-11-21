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

## Safety and concurrency
- Legacy Pilates #3394 nested shell remains write-quarantined: previous onepost attempts failed before POST; the workflow was disabled in PR #312. Do not retry, weaken guard or discard surrounding content. Primary #3660 already has the correct title.
- WEDOS/host troubleshooting deferred by owner; #9371 and #9462 onepost safety gates remain. Analytics plugin and static protein calculator assets cannot be described as installed until first-party hosting, consent testing and public readback are proven.
- Open independent Codex PRs #248 (UX), #263 (editor), #270 (revenue), #271 (archive) must be reviewed and updated against latest main before considering any merge. No duplicate work.

## Next priorities
1. Evidence-backed organic acquisition: improve qualified entry pages and true topical internal paths; no filler and no repeat #3394.
2. End-to-end verified measurement: approve/install analytics package on first-party WordPress, test WebToffee 3 consent states and GA4 DebugView, reconcile Affial approved vs paid.
3. Existing adviser product quality and price freshness: source-based catalog checks and accessible decision UX, verified by public/mobile readback.

Reporting: https://github.com/Rastty/xfit-growth-os/issues/1 . Keep GitHub CI/merge, WP deployment, public verification and actual earnings strictly separate.
