# XFIT — WordPress public readback must verify the exact article URL

## Risk and source

The existing central publisher `scripts/wp_publish.py` already
checks authenticated WordPress raw HTML and verifies visible
editorial body sections on the public page. However its public
redirect gate accepted **any path on xfit.cz**. A move to a
different slug, homepage or another approved post could theoretically
pass if the returned content shared the expected title and text.
This must not count as a successful publication of the requested URL.

Issue [#19](https://github.com/Rastty/xfit-growth-os/issues/19)
documents a real earlier case of stale public content after an
otherwise green WordPress REST write. This fix closes an additional
identity gap; it is not a claim of resolved cache flushing.

## New invariants

- Preflight public URL must be HTTPS on xfit.cz or www.xfit.cz,
  without username, password, explicit port, query, fragment or root path.
- A returned HTTP 200 must have **exactly the same canonical path**
  (trailing slash differences acceptable), same permitted HTTPS host,
  no query, port, credentials or fragment.
- Returning the expected HTML via a different post/homepage is never
  proof that the originally requested article is public.
- Limit the public HTML download to 2 MB, detecting truncation
  and refusing to label partial HTML as full page confirmation.
- Content/body verification and three bounded public GET attempts
  remain unchanged; never retry a WordPress POST.

## Acceptance

Full test suite and explicit tests for wrong permalink, site-root,
query suffix, unauthorized port, external redirect, cross-host
www canonicalization and oversized public body.
No plugins, cookies, analytics calls or WordPress writes from
this PR. Future direct publications will continue to verify
their actual visible content at the requested canonical URL.

Rollback: revert only the new URL check and related regression
tests. This returns the earlier weaker, not recommended readback.
