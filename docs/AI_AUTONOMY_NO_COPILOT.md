# Xfit: Parallel AI Development Without Paid Copilot

## Real implementation, as of 2026-10-30

- Four independent **Gemini CLI** coding jobs under `.github/workflows/xfit-gemini-parallel.yml`:
  UX, archive, editor, revenue. They run a bounded coding pass on their own branches, verify file ownership and Python tests, and propose a **pull request**, not a direct WordPress write.
- Scheduled at `39 0,6,12,18 * * *` UTC (four times/day per lane; up to 16 coding jobs/day). Manually runnable via Actions / Run workflow.
- Built on Google's official `google-github-actions/run-gemini-cli@v1`, with default model `gemini-3.8-flash`. New projects should not use deprecated Gemini 2.5 by default.
- No paid Copilot subscription, no model invented by a ChatGPT conversation, and **no AI job starts until owner provisions a free model key and enables the lane**.

### Owner setup: once

1. Create a free Gemini API key at https://aistudio.google.com/apikey and check currently available quota/pricing at https://ai.google.dev/gemini-api/docs/pricing .
2. Repo Settings → Secrets and variables → Actions → **Secrets**: `GEMINI_API_KEY` = the API key. Do **not** put the key into chat, issues or Git.
3. Same screen → **Variables**: `XFIT_GEMINI_AGENTS_ENABLED` = `true`.
4. In Settings → Actions → General, allow the workflow token the necessary repository write and PR creation permissions if GitHub blocks it; permission changes remain owner-only.
5. Inspect Actions → `XFIT Free Gemini Parallel Development` and the four agent PRs. Github-hosted jobs are best effort; schedule is not a hard SLA.

### Additional options

- OpenRouter free API models with OpenCode/Aider/OpenHands are alternatives and can be added as a second backend, but free APIs have quota and availability limits. Do not commit provider keys.
- Running Ollama locally removes provider API fees but requires an always-on compute host; a normal GitHub-hosted runner cannot guarantee an always-on self-hosted Ollama service.
- **GitHub Models is retired (July 30, 2026)** and not a viable plan.
- ChatGPT Plus does not automatically provide a standalone developer API key for GitHub Actions.

## Where the security boundary is

1. The Gemini step gets `GEMINI_API_KEY` only; it is **not** given `WP_USERNAME`, `WP_APP_PASSWORD`, affiliate feed secrets or `GH_TOKEN` in step environment.
2. The checkout has `persist-credentials: false`. A separate post-agent publishing step gets GitHub token only after exact file-scope, source-secret and unit-test checks.
3. Allowed edits are hardcoded in `scripts/xfit_agent_scope.py`: each lane has its own paths. No direct modification to `content/ready`, deployment workflows or other lanes.
4. PRs are **not merged automatically**. Reviewed merges can trigger existing guarded WordPress release workflows; actual site changes require authenticated readback + public verification.
5. An unexpected model response/no changes/failed scope checks result in no PR, no live mutation. If an issue has an existing open bot PR, new jobs skip to limit flooding.
6. See `AGENTS.md`, `docs/EDITORIAL_STANDARD.md`, and `.github/agents/xfit-*.agent.md`.

## Prometheus lessons adopted

Source: `Rastty/prometheus-growth-os/AGENTS.md`, `ARCHITECTURE.md`, `PROMETHEUS-MULTI-AGENT-BEST-PRACTICES-01.md`.

- One orchestration architecture owner, parallel independent analysis, bounded single-writer implementations, independent review, verified release; avoid multiple agents writing the same file set.
- Objective chain: **real evidence → priority → implement → test → deploy → public verification → measured business outcome → learn**.
- Use the largest feasible read-only discovery batch; keep risky production changes bounded and backed up.
- `config/xfit-growth-graph.json`, `config/xfit-priority-candidates.json` and `scripts/xfit_growth_graph.py` turn that chain into an Xfit-specific, revenue-aware priority queue. UNKNOWN economics is never silently treated as zero or potential sales.
- No copy/paste of portfolio-level secrets, WP tokens, or other sites' business policies from Prometheus.

## AI-friendly site, not artificial AEO

Google Search Central states Google AI Overviews/AI Mode use core Search indexing and helpful-content requirements: original grounded useful information, crawlable indexable HTML, correct canonical, navigable internal links, mobile readability and truthful structured data matching visible information. **There is no extra AI SEO file or required `llms.txt`.**

- `scripts/xfit_ai_visibility.py` runs read-only checks for canonical, meta description, H1, headings, noindex, text navigation, images and optional JSON-LD, plus `robots.txt` and sitemaps.
- `.github/workflows/xfit-ai-readiness.yml` runs this audit twice daily, produces evidence, and generates the growth priority queue.
- For supplement and medical content, citations and nuance matter more than fabricated schema `Rating`, fake reviews or unverified health claims.
- Structured data should describe real page types. Do **not** inject fake Product, AggregateRating, FAQPage or HowTo JSON-LD merely to make a green SEO score.
- Real browser agents also need accessible labels, meaningful buttons, functional interactive advisors and stable navigation — not only HTML text.

## Economic reality

The model can propose and test code once authorized. Profit requires validated conversion attribution; missing Affial orders, clicks or GA4 events means `UNKNOWN`, not `0` or success. Focus on **qualified visitors × advisor completion × legitimate merchant clicks × verified commission**, while preserving reader-first recommendations and opt-out choices.
