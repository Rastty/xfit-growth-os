# XFIT / WordPress 11945 — coherent evidence-led article repair

## Why this exact URL

Public WordPress REST showed four nested `<!DOCTYPE html>` / `<html>`
documents, duplicate claims/headings and advice presenting creatine after
training and mandatory cycling as if uniquely correct. This is a visible
reader-trust defect, not evidence of missing Google rankings.

The same post's three expired `5NM2022` promotions were independently
removed and verified first: [run 43694168389](https://github.com/Rastty/xfit-growth-os/actions/runs/43694168389).
Only the existing post 11945 at its canonical HTTPS URL is in scope.

## Editorial decisions

- Lead with a meaningful answer and explicit option not to buy.
- Explain exercise performance, water-weight changes and lean-body-mass
  evidence without promising identical results or claiming 1.14 kg of pure
  contractile muscle for every reader.
- Clearly distinguish a researched 3–5 g adult maintenance approach from
  loading/cycling as mandatory rituals.
- Replace invalid full-document HTML and repeated sections with six distinct
  decision-oriented headings, native keyboard-accessible details, no
  proprietary images, no embedded tracking and no direct merchant click.
- Internal navigation guides interested users to the existing feed-backed
  creatine selector, where affiliate disclosure is explicit.

Sources read on 15 Nov 2026:

1. NIH ODS exercise performance professional fact sheet:
   https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/
2. 2024 systematic review/meta-analysis (12 resistance-training studies):
   https://pubmed.ncbi.nlm.nih.gov/39074168/

The new article passes `scripts/xfit_editorial_gate.py` at 789 words and
six H2s. This does not itself establish clinical correctness, rankings,
conversion improvement or author expertise.

## Production release contract

Workflow: `.github/workflows/xfit-creatine-muscle-11945-revision.yml`.
Snapshot requires authenticated exact published ID/slug/link, a malformed
legacy signature, absence of the old promo code, a full original HTML
body and SHA-256 hashes. Upload complete immutable 90-day rollback before
any write. Re-read the same original content/hash, permit **at most one
content-only POST**, reconcile ambiguous HTTP by authenticated readback,
and verify both canonical live URL and public WP REST rendered body.
No new posts, redirects, unpublishing, affiliate ID changes or plugins.

On failed/uncertain state, stop and investigate; do not retry or overwrite
subsequent legitimate editor changes. A rollback must compare the stored
original against the then-current production document before restoration.

## Real deployment reconciliation

The original live workflow [43695394920](https://github.com/Rastty/xfit-growth-os/actions/runs/43695394920)
uploaded the original rollback artifact and attempted the exact one-post
revision, then failed its immediate final verification. Subsequent independent
public REST readback showed the new introduction, sources and all six sections,
with zero legacy nested `DOCTYPE` fragments and zero coupon code. The public
permalink also displayed the new text. A standalone read-only verifier now
checks both authenticated raw and public HTML/REST, without a new POST.

Follow-up workflow: `.github/workflows/xfit-creatine-11945-readonly-confirm.yml`.
Its success is the post-deploy confirmation, not a second deployment.
