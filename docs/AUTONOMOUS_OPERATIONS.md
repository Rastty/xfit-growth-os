# XFIT Autonomous Operations — confirmed configuration (2026-10-30)

## Independent from Prometheus
This is a separate GitHub repository with independent WordPress API secrets and Actions workflows. No shared queues, runners or production keys from Prometheus.

## Actual automated cadences (UTC)

| Job | Schedule | Automatic work | Live impact |
|---|---|---|---|
| XFIT Affiliate Feed Validation | `23 4 * * *` (daily) | Fetch NaMaximum Heureka catalog via private GitHub Secret; validate products, categories, safety filters, Affial sample and selector candidates | No; read-only, artifact summary |
| XFIT Creatine Advisor Live | `37 5 * * *` (daily) | Refresh catalog, filter comparable creatine powders, build campaign-consistent product links, update canonical creatine guide only on changes | Yes, WP post 25455 |
| XFIT Whey Advisor Live | `51 5 * * *` (daily) | Refresh catalog, compare whey powder pack sizes/prices, update canonical whey page only on changes | Yes, WP post 25456 |
| XFIT Read-only Audit | `23 4 * * *` (daily) | Inspect recent public archive sample, generate report | No; audit only |
| XFIT Code Checks | Every applicable push | Syntax, unit tests, validation | Prevent unsafe release |
| XFIT Direct Publish | Push to `content/ready/*.json` | Verify and publish approved content with native WP API | Yes, only changed owned `xfit-os-*` pages |

GitHub-hosted scheduled tasks are best effort and may be delayed, not hard real-time.

## Current live pages

- https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/ — evidence-led beginner supplement guide, WP ID 25458.

- https://xfit.cz/xfit-os-protein-guide/ — evergreen protein selection education, WP ID 25451.
- https://xfit.cz/xfit-os-kreatin-poradce/ — automated current creatine comparison, WP ID 25455.
- https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/ — automated current whey comparison, WP ID 25456.
- https://xfit.cz/jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates/ — improved existing Pilates article, WP ID 3660.

## Critical guardrails

- Feed URL and Affial IDs are encrypted Actions Secrets. Public repo and public workflow artifacts must not expose secrets.
- Product links follow a real owner-generated Affial direct-query product sample and same merchant IDs. This does not prove commission attribution: confirm at least one real tracked click/order in Affial reports.
- Never reuse Heureka CPC attribution as Affial tracking. NaMaximum campaign forbids PPC traffic.
- Do not invent product prices, purity, protein percentages, stock or results. No unsupported medical claims.
- 3h imports are read-only; 6h public refresh only if pricing/offer content changed. If quality/link validation fails, leave last verified live pages unchanged.
- WordPress releases verify authorized API writeback and public URL. New posts should remain within owned slug namespace; existing legacy posts require backup and explicit code path.
- Significant archive changes require a URL inventory and evidence from GSC and analytics; do not mass-delete content purely to increase focus.

## Limits — what is NOT running automatically

- Scheduled GitHub Actions execute **prewritten deterministic code**. They cannot independently conceive and implement new features, rewrite arbitrary legacy articles, or obtain missing affiliate conversion data without additional worker infrastructure.
- No live GA4 or Affial earnings/conversion connector is configured for automated ROI optimization. GA4 CSV exports were manual; product clicks and sales are not yet measured end-to-end.
- There is no dedicated ChatGPT Xfit background agent. Do not tell owner the model is autonomously coding around the clock after the chat ends.

## Prioritized next engineering sprint

1. Verify actual Affial click/commission attribution from campaign reports; avoid using assumed conversion evidence.
2. Instrument reliable affiliate outbound clicks and advisor funnels without personal or health-related data.
3. Add responsive product cards, filtering UX and safer image presentation through hosting-managed CSS/JS after tested deployment access is established.
4. Improve high-intent existing landing pages based on full GA4 source/medium x landing-page data.
5. Build a dedicated ongoing developer worker if autonomous *new feature creation* is desired; don't repurpose other portfolio workers without owner consent.

## Monitoring

- Check https://github.com/Rastty/xfit-growth-os/actions for latest runs and any failed checks.
- Feed artifacts are redacted counts and categories, not full product lists.
- A failed GitHub workflow is a blocker for the corresponding operation, not proof of success; no silent retries or invented deployment states.

## Updated owner policy, 2026-10-30

The owner prioritizes the best Czech trustworthy fitness and supplement decision site, not article volume, and requests an aggressive clean-up of archive clutter. Live WP unpublishing uses exact traffic-backed allowlists and backup, not blind deletes. Existing site theme's mobile navigation and consent banner need UX remediation. The first comprehensive public audit covered 11,814 posts; 34 e-bike URLs with zero sessions and GSC impressions are staged for reversible draft unpublishing (must check final run receipt).

Deterministic GH Actions now run feed and two commercial guide refreshes **daily**. Full-archive audit runs daily, real Chromium mobile QA twice weekly. Four-hour evidence status is posted to GitHub issue https://github.com/Rastty/xfit-growth-os/issues/1. There is **no independent ChatGPT task sending in-app reports** because the account already has 5/5 active automations; owner must subscribe to GitHub issue for GitHub notifications. Existing Prometheus/other task schedules were not altered.

GitHub Actions alone are not an autonomous AI developer: major new UX/content features still require running an AI coding session or a separately provisioned development agent. Do not describe them as being invented and deployed every four hours.

Quality standards: AGENTS.md and docs/EDITORIAL_STANDARD.md. Machine-readable editorial gate enforced in scripts/wp_publish.py; premium usefulness requires visual/manual reading QA too.
