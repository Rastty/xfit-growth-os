# XFIT — three bounded high-intent editorial handoffs (2026-11-15)

## Evidence and editorial intent

The most recent completed authenticated WP title-only discovery run
[`42854246737`](https://github.com/Rastty/xfit-growth-os/actions/runs/42854246737)
on 2026-11-10 found 55 short-listed candidate topic/article pairs after
examining 800 creatine and 329 protein source posts. Creatine search coverage
was capped, **not exhaustive**. These are *not* known high-traffic pages:
XFIT-specific current GSC impressions, clicks and ranking were unavailable.

Each of these three published canonical posts had no actual anchor to the
relevant XFIT comparison tool in that read-only snapshot:

| Pinned WP post | Reader's existing question | Relevant owned tool |
| --- | --- | --- |
| 10854 | Choosing inexpensive but appropriate creatine | `/xfit-os-kreatin-poradce/` |
| 10738 | Upfront price versus unit cost of creatine | `/xfit-os-kreatin-poradce/` |
| 7363 | Whether and how to choose whey for exercise | `/xfit-os-syrovatkovy-protein-porovnani/` |

The new handoffs add one genuinely contextual paragraph per post, with
disclosure that the buyer may need no supplement at all and no unsupported
claim of lowest market price, guaranteed efficacy, stock or commission.
Medical-intent content is excluded from this commercial linking wave.

## Release contract

Only these three exact existing IDs/slugs and editorial paragraphs are allowed.
The shared publisher checks WordPress source ID, status, canonical permalink,
relevant title, content length, real existing links and fresh modification
timestamp. It refuses to rewrite if content changes between backup and POST.
No WP posts are created, deleted or redirected; no plugins are installed.

The workflow first saves all **three full original bodies** to a 90-day
rollback artifact, before any write. Then each page is updated at most once;
authenticated WordPress readback and independently fetched public content must
contain the exact editorial sentence and destination anchor.

A failed preflight means no publication. A failure after the first post may
leave an explicitly **partial** rollout; successful earlier posts are
retained and can be independently reverted from their matching originals.
No automated ambiguous POST retry is allowed. A GitHub merge without all
three public readback confirmations is *not* a completed live release.

## What this does and does not measure

It creates three relevant routes to the decision tools. It does **not** prove
growth in SERP position, organic clicks, purchase clicks, approved orders, or
paid commission. All such economic outcomes remain unknown until actual
XFIT GSC and Affial data can be reconciled.
