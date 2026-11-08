# XFIT — six-guide technical indexability preflight (2026-11-08)

## Actual Google evidence
The owner-directed, credential-isolated Prometheus read-only [GSC source run 42470121265](https://github.com/Rastty/prometheus-growth-os/actions/runs/42470121265) confirmed five indexed-property URLs as `Discovered - currently not indexed` and the newest one as `URL is unknown to Google`. These are official URL Inspection states, not assumptions from missing performance rows.

Scope: owned XFIT slugs `xfit-os-doplnky-pro-zacatecniky`, `xfit-os-protein-guide`, `xfit-os-kreatin-poradce`, `xfit-os-syrovatkovy-protein-porovnani`, `xfit-os-kreatin-nebo-protein`, `xfit-os-cena-proteinu-podle-etikety`.

## Read-only test now added
`scripts/xfit_indexability_preflight.py` independently fetches just those six public HTML pages plus the established Pilates comparison as an inlink reference, and the three public entry points `/robots.txt`, `/wp-sitemap.xml` and `/sitemap_index.xml`. No arbitrary external links followed. It inspects:
- HTTP 200 and final same-origin exact permalink; redirect mismatch is UNKNOWN_FETCH, never guessed success.
- Public HTML meta `robots` / `googlebot`, `X-Robots-Tag` and explicit `noindex`.
- Exactly one self-referencing canonical link; missing/different/multiple status separated.
- Number of H1 headings, sampled internal links from seven explicitly reviewed pages.
- Mere availability of sitemap entrypoints. **Do not infer whether specific post URL appears in a child sitemap, or that Google successfully crawled the page.**

The report is a sanitized JSON object. No raw HTML, external product/affiliate URLs, credentials, private sitemap content, visitor events, crawled URL query strings or personal data emitted. Output statuses separate observed technical signals from UNKNOWN caused by WEDOS/cache/network response issues. Daily GitHub Actions read-only monitoring; no new plugins, no WP API auth, no indexing push request.

## Interpretation and next effect-oriented step
- If a real `NOINDEX_DIRECTIVE_OBSERVED`, wrong canonical or HTTP error is found, fix only that narrowly verified technical issue with a rollback-backed release.
- If all pages are public 200/self-canonical and have no explicit noindex, the Search Console decision **still remains** discovered/not-indexed; next evaluate current sitemap child URL inclusion, content uniqueness and crawl prioritization, plus meaningful internal links from relevant existing high-performing articles.
- Do not promise indexed status or Google impressions from this code change alone.

Rollback: revert only the preflight script, tests and GitHub Actions workflow. Zero WordPress writes and zero indexing side effects.
