# XFIT protein-label price calculator — prepared, NOT published

## User problem

The public indexed article `https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/`
(WordPress post ID 25541) explains the arithmetic but has no fields where a
reader can compare two real package labels. Adding more prose won't solve that
interaction gap. A compact calculator does.

## Current implementation

- `assets/tools/protein-price/index.html`: standalone Czech, mobile-first demo,
  deliberately `noindex` until approved production hosting.
- `calculator.js`: no dependencies, no storage, no cookies, no analytics, no
  tracking, no remote calls. Strict numeric validation (Czech commas supported),
  exact haler rounding, required label data, optional second package, optional
  per-purchase shipping, and a prominent no-purchase path.
- `calculator.css`: scoped styles, responsive layout, visible focus, 44px+
  controls; no external assets.
- Shipping comparison safety: if the visitor specifies delivery for just one
  of two packs, the tool still shows arithmetic but **does not declare a
  cheaper winner**. Both fields must be present (including 0 for free shipping),
  or both empty (clearly labelled as shipping-excluded).
- Node unit tests and real Chromium viewports 320/375/768, including no outbound
  requests and error/reset behavior. Workflow runs tests on PR and main.

The comparison is cost per declared protein mass only, not a product quality
ranking. If shipping is unknown, the result says it is excluded; there are no
fake current prices, product recommendations or affiliate links.

## Deployment gate (not yet satisfied)

1. Establish and verify an **owner-approved first-party static asset path** on
   `xfit.cz` (WEDOS/theme-managed asset publishing), or an equivalent approved
   hosted path with stable URL and appropriate Content Security Policy. Do NOT
   create a new WordPress plugin or try an inline `<script>` bypass.
   Once the owner has published the reviewed files in that exact directory,
   run the read-only byte/MIME/redirect gate:

   ```bash
   python -m scripts.xfit_protein_price_host_preflight \
     --base-url https://xfit.cz/OWNER_APPROVED_ASSET_DIRECTORY/
   ```

   A green result verifies both hosted files against local SHA-256 bytes, but
   **does not authorize or perform a WordPress post edit**. Missing files,
   redirect, HTML response or unexpected bytes block the next stage.
2. Serve the reviewed JS and CSS by versioned URL; include the semantic HTML
   markup in the existing WP post 25541 **only** through a separately reviewed,
   backed-up exact-one-post release. Do not publish this demo URL as another
   competing SEO article.
3. Before writing: verify authenticated post identity, exact full raw-body
   backup, existing ownership marker, current GMT revision and no remote edit
   drift. A failed API write must be reconciled via readback; never blind retry.
4. After writing: prove WP REST raw readback preserves labels/data attributes,
   public page contains exactly one calculator, verified JS/CSS load without
   blocked CSP or unsafe third-party requests, and real 320/375px browser use
   with correct 899/900/75 calculation and accessible error/reset flows.
5. On failure, restore from the full prewrite backup with drift protection.
   The current page stays untouched until the entire deploy path exists.

## Evidence and status

- Public XFIT article examined on 2026-11-17: no form inputs in its content.
- Code completion/CI **does not mean WordPress deployed**.
- No GA4 attribution, real clicks, orders, commissions or lift claimed.
- Pending next step: owner-approved first-party asset deployment/access, then
  exact-one-post release and live mobile QA. Reuse the same source for a future
  XFIT training/nutrition decision tool rather than another article rewrite.
