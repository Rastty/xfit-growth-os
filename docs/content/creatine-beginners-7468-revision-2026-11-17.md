# XFIT legacy creatine beginner page — distinct editorial safety correction

**Target:** WordPress ID 7468, existing canonical
`https://xfit.cz/kreatin-pro-zacatecniky-v-fitness-kdy-zacit-a-jakymi-davkami-zacinat/`.

## Why this post, not another article

- The live public 2023 page on 17 Nov 2026 repeated essentially identical
  headings and prescribed contradictory regimens: 5 g, 20–30 g, 5–10 g,
  inconsistent timing and a blanket eight-week cycle claim.
- The XFIT GSC captured window ending 13 Nov 2026 reports **29 impressions,
  0 clicks, average position 22.66** for the source-backed query opportunity.
  These are prior observations, not a promised improvement.
- This post was not among the recently revised advisor or handoff articles.
  Preserve its existing permalink and full legacy traffic identity; correct
  one URL, not generate competing pages.

## Review choices

- First screen gives a clear, optional no-purchase answer for new exercisers.
- Describe study regimens rather than prescribe personal medication-like doses.
- Remove conflicting legacy dose, timing and forced cycling claims. Avoid
  discussing specific medical conditions beyond recommending individualized
  clinical advice where appropriate.
- Cite independent NIH ODS and OPSS sources and one 2025 research paper,
  distinguish evidence from editorial conclusions. Explicitly do not claim
  hands-on product tests or current stock/prices.
- Link to the existing XFIT creatine selection advisor and beginner opt-out
  guide, with disclosure that target comparisons can carry affiliate links.

## Release guard

Manual `workflow_dispatch` only. Exact ID/slug/canonical/status and original
contradictory text must match immediately before the single POST. Snapshot
includes the *complete authenticated raw body* and WordPress `modified_gmt`;
upload to GitHub Actions as immutable 90-day rollback artifact first. If raw
SHA, modification timestamp or revision SHA drifts, **zero writes**. Do not
blindly retry an ambiguous POST. Require authenticated raw readback, public
WordPress rendered post and independent public permalink proof.

Rollback: use the immutable `original_raw` from the matching run artifact in
an isolated exact-one-post restoration with fresh drift checking; never restore
blindly over later edits.

**No article or traffic lift is claimed on code merge.** Live release is
complete only with a `PUBLIC_VERIFIED` receipt from its manual workflow.
