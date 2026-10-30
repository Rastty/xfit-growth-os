# Xfit Growth OS

**Independent Xfit.cz development / publishing system** — outside Prometheus, without WPVibe or similar WordPress publishing plugins.

## Actual state — 2026-10-30

| Area | State |
|---|---|
| Independent GitHub repository | ✅ Connected, write access |
| Safety tests and CI | ✅ [XFIT Code Checks](../../actions/workflows/xfit-checks.yml) |
| WordPress native API publisher | ✅ Implemented — NOT authenticated to live site yet |
| Scheduled read-only sample audit | ✅ [Workflow installed](../../actions/workflows/xfit-audit.yml); first live audit not yet verified |
| Direct publish on ready-content change | ✅ [Workflow installed](../../actions/workflows/xfit-publish.yml), inactive until WP Secrets configured |
| Live site deployment verified | ⏳ Not yet |
| Affiliate feeds and IDs | ⏳ Not yet provided |
| Interactive on-site engine | ⏳ Planned — frontend deployment method not established |

**GitHub commit ≠ published web page.** Do not claim live release before REST write and public URL verification.

## First action to unlock publishing

1. In WordPress create a separate **Editor** account for Xfit automation and an **Application Password** in its Profile.
2. In this repo open **Settings → Secrets and variables → Actions**. Add:
   - \`WP_USERNAME\`: the WordPress automation user's login
   - \`WP_APP_PASSWORD\`: the newly generated *Application Password*
   - \`WP_BASE_URL\`: optional (\`https://xfit.cz\` is the default in the workflow)
3. Run [XFIT Direct Publish](../../actions/workflows/xfit-publish.yml) in **draft** mode with slug \`xfit-os-protein-guide\`. First validate write and read-back.
4. Once successful, publish the same page in **publish** mode, check the resulting public URL. Future content changed under \`content/ready/\` will publish automatically on push.

**Never put secrets in a chat message, GitHub commit, pull request or issue.** Set them in encrypted GitHub Actions Secrets.

## Architecture

- \`scripts/wp_publish.py\`: safe native WP REST content publisher. Own \`xfit-os-\` namespace; no overwriting unrelated URLs; draft by default; read-back and public title verification.
- \`scripts/wp_audit.py\`: read-only public post sample audit, reports candidate duplicates, short content and external domains; no automatic removal.
- \`content/ready/*.json\`: approved content for publishing.
- \`tests/\`: basic content validation tests.
- \`.github/workflows/\`: code checks, scheduled audit, and direct publisher.
- \`docs/ROADMAP.md\`: roadmap and growth feedback loop.
- \`docs/ACCESS_SETUP.md\`: access and security guidance.

## Rules

- Never update/delete the existing archive without GSC inventory + backup.
- Never fabricate affiliate offers or efficacy claims.
- No shared production credentials, queue, governance or repo with Prometheus.
- Implement → test → deploy → verify public URL → measure; prioritize real visitors and affiliate revenue.
