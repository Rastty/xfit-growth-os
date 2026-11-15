# XFIT 11945 — exact Czech title correction, 15 November 2026

Public mobile Chromium run `43696267488` proved the reviewed article body,
its sources, FAQ, no-buy option and internal advice link work on 375px.
The existing public H1 was still **Jak kreatin může pomoci získat svalový objem v fitness**.
The final phrase is awkward Czech, and the new evidence-led body refers to
studies rather than a general promise. One title-only copy correction:

- Old: `Jak kreatin může pomoci získat svalový objem v fitness`
- New: `Jak kreatin může pomoci získat svalový objem: co říkají studie`
- Preserve **WP ID 11945**, URL, slug, article HTML byte for byte, excerpt,
  existing internal/affiliate/source links, publication status and all other fields.
- This is editorial clarity, **not** a supported claim of SEO, CTR or revenue uplift.

Release `.github/workflows/xfit-creatine-11945-title-release.yml` uses the
existing native WP REST credentials and never installs plugins. It verifies
the exact old/new title transition and a clean source-body signature,
uploads a 90-day immutable rollback manifest of original title, canonical
identity, content and excerpt SHA-256 **before** an at-most-one POST, then
checks authenticated original-body hashes and exact public H1. If WordPress
commits the title but public cache is slow, do **not** retry the POST; use
`python -m scripts.xfit_creatine_title_release_11945 verify` in a separate
read-only workflow or authorized environment. If the source or identity has
drifted, stop and investigate.

Rollback is a separately reviewed exact title restoration only after a fresh
authenticated identity/body hash comparison. No redirects, deletions or new
posts. A live/SEO outcome is UNKNOWN until independently verified.
