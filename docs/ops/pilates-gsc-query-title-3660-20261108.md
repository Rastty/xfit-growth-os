# XFIT WP 3660 — GSC-backed title-only intervention, 2026-11-08

## Evidence
Prometheus [GSC source run 42470121265](https://github.com/Rastty/prometheus-growth-os/actions/runs/42470121265) used the existing owner-authorized `https://xfit.cz/` Search Console property. GSC final 28-day window 2026-10-09 to 2026-11-05: the current existing Pilates comparison article [WP 3660](https://xfit.cz/jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates/) had **88 impressions, 1 click, CTR 1.14%, mean position 7.01**.

Page-filtered search queries (not an exhaustive query sample):
- `power pilates co to je`: 16 impressions, 0 clicks, mean position 4.75.
- `co je power pilates`: 14 impressions, 1 click, mean position 6.57.
- `power pilates`: 11 impressions, 0 clicks, mean position 4.64.
- `pilates power`: 3 impressions, 0 clicks, mean position 3.0.

## Bounded reader benefit / hypothesis
Topical searchers are asking `co je power pilates` rather than only asking which class type is different. The current public article already contains a useful comparison, a practical pre-class checklist, FAQ and expert limitations; **do not rewrite that live HTML**.

One reversible title-only change:
- Before: **Jaký je rozdíl mezi klasickým pilates a power pilates**
- After: **Co je power pilates? Rozdíl oproti klasickému pilates**
- Preserve WP post ID 3660, original canonical slug, page body byte-for-byte, excerpt, author, all links, affiliate disclosure, images, status and all other WP fields.

This is a GSC-informed editorial hypothesis, not a proven SEO uplift. No claim that Search Console traffic/CTR will improve; follow a comparable 28-day final GSC window after indexing and title recrawl with position/query mix caveats.

## Exact release gates
`.github/workflows/xfit-pilates-gsc-title-onepost.yml` is one-off on merge or explicit manual dispatch. It runs full repository tests, fetches exact published WP 3660 source and old title via authenticated REST, refuses source drift, saves the original title plus body/excerpt SHA256 and canonical identity, uploads 90-day rollback artifact before the single REST POST, and updates only `title`.

After POST, including ambiguous network errors, readback must prove the new title and **unchanged** HTML/excerpt SHA256/status/slug/URL. An independent exact public HTTPS URL read must find the new visible H1. Never retry WP POST without fresh source reconciliation, never overwrite a concurrent editor. No plugins, new URLs, redirects or deletions.

## Reality and next measurement
- `PUBLIC_VERIFIED`: genuinely updated existing WP title and visible H1; exact run receipt required.
- `ALREADY_APPLIED_NO_WRITE`: already matches and public verified, no new WP intervention.
- Any failed source, immutable snapshot or public verification: **not live-verified**. Do not report a successful title change.
- The six new owned XFIT decision guides were simultaneously inspected: five show `Discovered - currently not indexed`, one `URL is unknown to Google`. Investigate crawl/index eligibility and internal links separately; changing this Pilates title will not by itself resolve all indexing blockers.

Rollback only via a separately reviewed exact title restoration after confirming that current live content/body hashes have not changed. An existing WordPress revision should not be blindly overwritten.

Owner request: continue independently without WordPress plugin installations; no action needed from owner for this one bounded release.
