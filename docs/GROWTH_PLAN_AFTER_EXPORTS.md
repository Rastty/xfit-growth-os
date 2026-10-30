# Xfit Growth OS — priorities after GSC and GA4 exports (2026-10-30)

Independent from Prometheus. No WPVibe.

## Data boundaries
- GSC measures Google, not all organic visits.
- GA4 export includes the dimension Session manual source (utm_source), which is not the same as Session source/medium. Do not attribute manual Seznam data to organic search without the channel x landing-page cross-tab.
- Direct traffic is unusually large and needs source and engagement validation. Do not declare all Direct traffic to be bots.
- Do not commit private user-supplied traffic exports into this PUBLIC repository.

## P0 — attribution and qualified visits
Request GA4 export for Landing page + query string x Session source / medium, with sessions, engaged sessions, average engagement and key events for last 90 days.
Keep Google, Seznam and Direct separate. Use landing-page engagement to decide which old articles to improve.
Measure affiliate_outbound_click with nonpersonal product ID, partner, page and selection engine. Measure advisor_start and advisor_complete; never send sensitive health answers.

## P1 — quality fixes on existing pages
1. Improve existing Pilates comparison article, WP post 3660, same permalink. Read-only API inspection confirmed duplicated sections and external copyright notice. Use pre-write backup and live verification. Files: content/revisions/pilates-difference.json, scripts/wp_revise_pilates.py, .github/workflows/xfit-pilates-revision.yml.
2. Update adjacent Pilates/cardio and beginners articles through internal links and verified information, without competing pages for the same intent.
3. Continue protein guide only with accurate nutritional sources and partner feeds.
4. Assess home gym and men's fitness apparel selection engines after actual session-source landing-page data.

## P2 — medical trust
Audit testosterone, hormone diagnostics, keto diets and supplements for unsupported claims, stale promotions and repeating text. Do not sell unproven health outcomes.

## Affiliate pipeline
Await approved partner IDs, feed URLs and licenses. Keep private tokens in GitHub Secrets. Normalize GTIN/SKU, product title, merchant, VAT-inclusive price, availability, affiliate deep link and last update timestamp. Do not publish imaginary or stale offers.
Possible first partners/categories: Pilates/home workout mats, bands and fitness gear; home gym; protein and creatine; fitness apparel.

## Release truth
Audit → define → code → test → backup → WP REST deploy → authenticated readback → public verification → measure. Never claim a commit alone is a live change.
Do not bulk delete, redirect, or noindex existing URLs until GSC and source-level GA4 inventory plus backups.

## Remaining access
WordPress API credentials already work. Need GA4 correct export, affiliate feeds and eventual hosting asset deployment path for interactive JS/CSS.

## Update — second GA4 landing-page export, 2026-10-30

- A landing-page-only GA4 export was received (2026-08-01 to 2026-10-29). It contains 3,873 unique paths across 7,309 sessions, many one-session long-tail entries. This is descriptive baseline, not proof of traffic quality per source.
- 2,204 paths had one session; 3,183 had one or two sessions. No key events are recorded in the exported landing-page table, so conversions cannot yet be attributed.
- The highest-traffic content areas include muscle-related pain/recovery, hamstring injury, exercise and creatine; some off-topic electric-bike pages also have traffic. **Do not delete unrelated but visited pages without checking attribution and index performance.**
- The export does **not** contain source/medium breakdown: still need GA4 session source/medium x landing-page cross-tab.
- Prioritize consolidating near-duplicate hamstring / injury pages into clear medically responsible content hubs while preserving useful URLs and reviewing crosslinks first.

## Affiliate feed integration status

- Received an eHUB default tracking URL and a private Venalio Heureka XML feed URL in chat. The feed URL contains a secret-like authorization token; it has intentionally NOT been committed, logged or attached as a repository file.
- Installed validation-only importer in `scripts/xfit_feed_ingest.py` and GitHub workflow `.github/workflows/xfit-feed-validation.yml`. It will read secrets `XFIT_GREENMEDICAL_FEED_URL` and `XFIT_EHUB_DEFAULT_LINK`, only when variable `XFIT_AFFIL_FEED_ENABLED=true`.
- **No actual feed product inventory, verified merchant ↔ eHUB mapping, product deep links or live affiliate page yet.** First validate feed privately, assess health-product compliance and then publish relevant selections.
- Setup guide: `docs/AFFIL_ONBOARDING.md`.
