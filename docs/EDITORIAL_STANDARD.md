# Xfit Editorial Standard — zero tolerance for filler

**Promise:** “Pomůžeme vám udělat správné rozhodnutí. I když je nejlepší nic nekoupit.”

## What a top-tier piece must do
- First screen: answer the exact reader question in 1–3 sentences; show who it is for, exceptions and what to do next.
- One clear intent per URL. Combine duplicate articles into the strongest truthful destination, preserve valuable traffic and internal links. Rewrites improve usefulness, not just length.
- Provide a usable decision flow: beginner/advanced, budget, restrictions, goal, real choices, transparent tradeoffs, opt-out.
- Reference 1–3 high-authority *independent* medical/scientific sources where relevant (NIH ODS, EFSA, European Commission, Cochrane etc), note the date and distinguish data from editorial interpretation. One vague “studies say” claim does not pass.
- Have obvious navigation, short paragraphs, descriptive H2, tables or cards that work at 375px, meaningful images with alt and rights, and no nonfunctional controls.
- The article should add practical value not easily replaced by a generic answer: calculations, clear exclusions, comparisons, repeatable method or genuine original workflow.
- Where product listings are used, show what the feed proves and what it does NOT. Price for 100g of powder is NOT price for 100g of protein; exclude unknown composition instead of guessing.
- State “when you do not need supplements” prominently. Affiliate links are disclosed adjacent to choices and have rel=sponsored.
- Avoid personally targeting or collecting sensitive health conditions through analytics, ads or third-party scripts.

## Strict reject criteria
- Unsupported medical outcome, claims to cure disease, “miracle”, or hormonal transformations.
- Fake product testing, invented expert, false “best rated” or order-dependent ranking.
- Thin boilerplate, repeated sections, mechanically generated city/product variations, no independent references.
- Unsupported images, missing alt, inaccessible mobile layout, tables so narrow they become illegible, intrusive newsletter gates.
- Unverified affiliate links, Heureka CPC links treated as affiliate, stale stock or unrealistic prices.
- Mass deletion without recorded evidence, immutable target list, backup and a credible destination/rollback.

## Clinical boundaries
Articles about symptoms, injury, chronic illnesses, pregnancy, children and medication interaction need especially conservative wording and clearly mark urgent symptoms requiring medical assessment when appropriate. Never diagnose readers or recommend supplements as treatment for a serious medical problem. EU supplement claims are regulated; do not copy merchant claims unquestioningly.

## Site-specific rollout and acceptance
1. Fact-check sources; remove duplicated content and ensure unique intent.
2. Run Python unit tests and editorial gate; validate product feed & merchant.
3. Use native WP REST readback and public permalink smoke.
4. Run mobile real Chrome QA on representative devices and capture screenshot; investigate the theme's oversized mobile menu and cookie banner rather than falsely declaring the UX solved.
5. Track outbound clicks and eventually orders only with correctly configured GA4 and Affial; the absence of measured revenue is UNKNOWN.
6. At four-hour status report show live proof, customer value, UX failures, unanswered risks and next concrete work. Do not claim project “autonomous” without an actual executing AI worker.

## Archive cleanup policy
The owner authorized rapid pruning, redirects and deletions. Be aggressive **in selecting unhelpful content**, but precise about irreversibility:
- Safe first wave: unrelated e-bike posts with 0 GA4 landing sessions and 0 GSC impressions/clicks during supplied 90-day windows; exact allowlist and rollback; start by unpublishing as WordPress drafts, not hard deleting. Preserve the five observed-traffic pages.
- For actual 301 redirection a supported server routing layer (WEDOS/.htaccess, WP redirects API etc.) is needed; do not invent a redirect from a draft status change.
- Thin on-topic fitness recipes could be worth rewriting; don't treat under 350 characters alone as permission to delete.
- Google and GA4 exports are slow/partial; absence of GSC clicks does not prove a page has zero value in Seznam or from backlinks.

## Quality gate automation
Minimum machine checks live in scripts/xfit_editorial_gate.py; it can reject obvious failure but **cannot grade world-leading helpfulness**. Continue human-readable source verification and browser QA. User trust, not test pass count, is the goal.
