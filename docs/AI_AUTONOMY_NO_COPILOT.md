# Xfit — OpenAI Codex parallel development, without paid GitHub Copilot

Updated: 2026-10-30. This supersedes the earlier Gemini CLI plan.

## Installed implementation

- Main orchestrator: `.github/workflows/xfit-codex-parallel.yml`
- Reusable isolated coding lane: `.github/workflows/xfit-codex-lane.yml`
- Official agent execution: `openai/codex-action@v1`, secure Responses API key proxy, `permission-profile: ":workspace"`, default `drop-sudo` hardening.
- Four lanes execute concurrently: `ux` (issue #2), `archive` (#3), `editor` (#4), `revenue` (#5). Each reads its local `.github/agents/xfit-<lane>.agent.md`, `AGENTS.md` and `docs/EDITORIAL_STANDARD.md`.
- Schedule: twice daily (`39 0,12 * * *` UTC), up to **8 agent coding calls per day** if there is no existing open PR. This is a deliberately cost-aware start; manual `workflow_dispatch` remains available.
- Existing open `xfit/codex-<lane>-*` PR blocks more model calls in that lane until handled.
- No automatic PR merge and no direct WordPress publication by Codex. The agent cannot access WP credentials, affiliate tokens, or a GitHub write token.
- A read-only first job creates patch and runs scope and unit tests. A separate job applies the patch on an immutable source SHA, rechecks file ownership/tests and creates the PR using its limited GitHub token.
- A patch is rejected for edits outside the lane's allowlist (`scripts/xfit_agent_scope.py`) or if tests fail. No write access is granted to model-generated code.

## One-time owner setup

1. Create/use an **OpenAI API key** at https://platform.openai.com/api-keys (for a project with API billing/credits enabled). **ChatGPT subscription or interactive Codex sign-in alone does not supply a CI API key.**
2. Open https://github.com/Rastty/xfit-growth-os/settings/secrets/actions and create repository **Secret** `OPENAI_API_KEY` with the key. Do not paste the value into chat, issues or source.
3. Under **Variables** set `XFIT_CODEX_AGENTS_ENABLED` to `true`. Optional: `XFIT_CODEX_MODEL`, else the official Codex Action selects its current default model.
4. If GitHub blocks PR creation by Actions, use Settings → Actions → General to allow Actions to create pull requests and grant required permissions. No repository settings are silently changed by this script.
5. Run https://github.com/Rastty/xfit-growth-os/actions/workflows/xfit-codex-parallel.yml manually once, check four lane jobs and candidate PRs. If one fails, capture exact job run; success is not inferred from workflow creation.

**Pricing:** OpenAI API use is billed separately from ChatGPT subscriptions and can become expensive with repeated coding runs. Before enabling, set an API budget/usage alert in the OpenAI project, monitor first-run token consumption and lower cadence/model if needed. Main goal is meaningful benefit per paid token, not number of AI jobs.

**Safety:** Never add `OPENAI_API_KEY` as a job-level environment variable for repository-controlled tests. The official action uses a secret proxy. Job paths and custom GPT prompts are reviewed through the Xfit ownership gate. Keep PR review before merge. API and GitHub usage are both subject to the provider's limits, availability and service terms.

## Prometheus patterns reused, not shared runtime

Reviewed `Rastty/prometheus-growth-os/AGENTS.md`, `ARCHITECTURE.md`, `PROMETHEUS-MULTI-AGENT-BEST-PRACTICES-01.md`, and economic prioritization notes. Adapted their **one orchestrator, disjoint file ownership, bounded tasks, independent review and evidence → decision → release → measurement → learning** patterns to Xfit.

Files: `config/xfit-growth-graph.json`, `scripts/xfit_growth_graph.py`, `config/xfit-priority-candidates.json`. Economic values remain `UNKNOWN` unless verified by actual revenue reports. No Prometheus tokens, queues, portfolio governance or publishing permissions are copied into Xfit.

## Human- and AI-friendly web

- Original Czech user-benefit-first information and useful tools — do not generate thousands of templated articles.
- Publish indexable HTML with clear concise answers, accessible page navigation, consistent titles and canonicals, strong cited evidence and real internal links.
- `scripts/xfit_ai_visibility.py` audits live content, headings, meta descriptions, canonical URLs, and crawlability with `.github/workflows/xfit-ai-readiness.yml`.
- Only use valid structured data describing visible verified content. No fabricated Product/Review/FAQ ratings. `llms.txt` is not a special requirement for Google AI results.
- Supplement health claims need scientific and applicable EU law review; product comparisons must carry truthful source data and explicit affiliate disclosure.
- Close the economic loop: source/medium landing traffic → useful advisor interactions → genuinely attributed affiliate click → verified commission → measured learning.

## Current evidence boundaries

The Codex workflow files are committed but **the AI coding agents have not run successfully** until the OpenAI API key and enabled variable are set and a real GitHub Actions job succeeds.

Deterministic WordPress catalog/guide refresh and four-hour GitHub issue status remain independent of the new AI coding workflow.
