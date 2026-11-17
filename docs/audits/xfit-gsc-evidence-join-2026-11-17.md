# XFIT: review priorities informed by real search evidence (V1)

**Goal:** promote maintenance of articles that people **actually see or visit**
via Google Search, without mistaking an old article/coupon for a revenue signal.

The public full-archive workflow produces `content_quality_review_queue` in
`xfit-archive-full-audit.json` (max. 70, editorial heuristics, read-only). This
new explicit offline bridge joins those candidates to an owner-controlled,
recent, 90-day GSC *page aggregate* exported from Prometheus Core. It does not
query an API, assume Prometheus already exported the data or change a WP page.

## Required normalized GSC input

Save the private file **outside this public Git checkout**; never commit GSC
metrics, credentials or the joined output. Example *illustrative schema*:

```json
{
  "source": "google_search_console_page_aggregate",
  "property": "sc-domain:xfit.cz",
  "search_type": "web",
  "dimension": "page",
  "start_date": "2026-08-16",
  "end_date": "2026-11-13",
  "rows": [
    {"page": "https://xfit.cz/example/", "clicks": 25, "impressions": 250}
  ]
}
```

These counts are example values, **not observed XFIT traffic**. `property`
also accepts `https://xfit.cz/`. The dates must span 84–100 inclusive days,
end no more than 14 days ago and not be future-dated. `rows` are limited to
25,000. Only exact canonical `https://xfit.cz/<slug>/` URLs are joined;
noncanonical URLs are counted and ignored. Duplicate page keys, invalid counts
and wrong aggregation fail closed.

## Run after obtaining the export

```bash
python -m scripts.xfit_gsc_evidence_join \
  --archive /path/to/xfit-archive-full-audit.json \
  --gsc /private/path/xfit-gsc-90days.json \
  --output /private/path/xfit-gsc-triage-result.json
```

Input/output of GSC must be outside this Git checkout. Existing output is
never overwritten. Review the result privately; only aggregate process status
is printed on the command line.

## Interpretation and boundaries

- `MEASURED_EXISTING_SEARCH_TRAFFIC` means at least 20 observed GSC clicks
  during the supplied period; old/misleading statements deserve attention.
- `MEASURED_SEARCH_EXPOSURE` means at least 200 impressions but fewer than
  20 clicks; this is a candidate for *human* snippet/intent review, not proof
  that changing a title will increase CTR.
- `MEASURED_LOW_SEARCH_EXPOSURE` means a valid row with lower values,
  **including an observed zero**.
- `NO_GSC_ROW_IN_SUPPLIED_EXPORT_NOT_ZERO` means the URL was absent from
  provided rows; GSC exports may be limited. Never call it zero traffic.
- `gsc_export_coverage` explicitly records that the input may omit pages.
- Only the **preselected 70 archive candidates** are reordered; high-traffic
  URLs outside this queue are not discovered by V1. Prometheus Core should
  eventually supply an all-posts measured prioritizer.
- GSC clicks/impressions are **not** GA4 landing sessions, affiliate clicks,
  conversions or revenue. Verify the live source, medical claims, destination
  and user intent before a rollback-safe, one-post editorial proposal.

No automatic publication, unpublication, internal link editing or redirect is
implemented. The workflow and tests may run without private credentials.
