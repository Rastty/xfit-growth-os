# XFIT catalog identity gate — 2026-11-17

## Problem and invariant

The XML importer previously substituted an XML row number whenever `ITEM_ID`
was absent. A row number is not a merchant product identity. Public product
cards carry the feed ID in `data-xfit-product-id`, while their destination
may point to a specific `?variant=` on the merchant. These must agree.

The importer now accepts a product only when:

- its item URL belongs to the existing NaMaximum merchant allowlist;
- its authentic `ITEM_ID` / `ITEMID` / `ID` is a positive canonical decimal
  integer within `2^31 - 1` (same bound as public click metadata);
- if `variant=` is present, it occurs exactly once and exactly equals the
  authentic feed ID;
- a product URL without `variant` is allowed, but never creates an ID.

Invalid rows are counted under `invalid_or_mismatched_catalog_identity`
without logging raw URLs or private partner identifiers. The selector checks
the same invariant independently for cached or hand-built catalogs.

## Release safety and evidence

- No price, availability, commission, product identity or tracked purchase is
  inferred. Affiliate link verification remains separate.
- If too few eligible products remain after filtering, existing advisor
  publishers fail before the WordPress write.
- Tests cover missing IDs, wrong/duplicate variants, out-of-range/nonnumeric
  IDs, a canonical URL without variant, and direct selector bypass.
- On merge the existing creatine and whey workflows perform full tests,
  live-feed checks, original WordPress backup and public verification.
  Do not claim a successful live refresh before inspecting Actions/readback.

## Rollback

If the merchant feed legitimately uses a different identity scheme, revert the
merge commit before the next scheduled refresh. For a WordPress update already
made, retrieve the individual workflow's original-post backup artifact and
perform the existing single-post rollback with a public readback check.

No private feed URL, raw product list or affiliate account ID belongs here.
