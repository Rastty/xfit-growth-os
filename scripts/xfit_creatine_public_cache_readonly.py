"""Read-only ordinary-cache versus bypass-cache proof for live WP #11304.

The prior onepost #44893199715 verified WP and a no-cache public response.
This checks what an ordinary browser and a cache-bypassing client actually see,
without editing the post, purging caches, indexing URLs or clicking offers.
"""
from html.parser import HTMLParser
import json
import sys
import urllib.parse
import urllib.request

from scripts.wp_publish import (
    PublishError, article_visible, editorial_links, normalize_visible,
)
from scripts.xfit_creatine_disadvantages_onepost import (
    URL, NEW_TITLE, OLD_TITLE, MARKER, PINNED_POST_ID,
    LEGACY_CLAIMS, APPROVED_LINKS, Headlines, classify, reviewed_document,
    source_get,
)

MAX_BYTES = 2_000_000
HEADERS_TO_LOG = ("Age", "Cache-Control", "X-Cache", "CF-Cache-Status")


class PublicMeta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.canonicals = []
        self.robots = []
        self._in_head = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "head":
            self._in_head = True
        if tag == "link" and self._in_head:
            if "canonical" in (attrs.get("rel") or "").lower().split():
                self.canonicals.append(attrs.get("href"))
        if tag == "meta" and self._in_head:
            if (attrs.get("name") or "").lower() in ("robots", "googlebot"):
                self.robots.append((attrs.get("content") or "").lower())

    def handle_endtag(self, tag):
        if tag == "head":
            self._in_head = False


def public_read(*, bypass_cache=False):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; XFITProductionReadOnly/1.0)",
        "Accept": "text/html",
    }
    if bypass_cache:
        headers.update({"Cache-Control": "no-cache", "Pragma": "no-cache"})
    req = urllib.request.Request(URL, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=25) as response:
        final = urllib.parse.urlsplit(response.geturl())
        requested = urllib.parse.urlsplit(URL)
        if (response.status != 200 or final.scheme != "https" or
                final.hostname not in ("xfit.cz", "www.xfit.cz") or
                final.username or final.password or final.port or
                final.path != requested.path or final.query or final.fragment):
            raise PublishError("Wrong public URL, redirect or status; not verified")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise PublishError("Public response too large")
        return (
            raw.decode("utf-8", errors="replace"),
            {k.lower().replace("-", "_"): (response.headers.get(k) or "")[:100]
             for k in HEADERS_TO_LOG},
        )


def inspect_html(page, *, expected):
    if not isinstance(page, str) or len(page) < 500:
        raise PublishError("Missing ordinary public HTML")
    heading = Headlines()
    heading.feed(page)
    metadata = PublicMeta()
    metadata.feed(page)
    visible_text, _ = article_visible(page)
    _body_text, segments = article_visible(expected)
    source_links = editorial_links(page)
    complete = bool(segments) and all(s in visible_text for s in segments)
    title_ok = heading.h1 == [NEW_TITLE]
    required_links = all(link in source_links for link in APPROVED_LINKS)
    claims = [
        claim.casefold() in visible_text
        for claim in LEGACY_CLAIMS
    ]
    new_marker = MARKER in page
    canonical = metadata.canonicals == [URL]
    noindex = any("noindex" in r.replace(" ", "").split(",") for r in metadata.robots)
    return {
        "new_h1_exact": title_ok,
        "old_title_h1_seen": OLD_TITLE in heading.h1,
        "content_segments_matched": sum(s in visible_text for s in segments),
        "content_segments_expected": len(segments),
        "all_new_article_segments_visible": complete,
        "all_five_reviewed_links_visible": required_links,
        "legacy_unsupported_claims_visible": claims,
        "revision_marker_in_html": new_marker,
        "single_self_canonical": canonical,
        "noindex_seen": noindex,
        "state": (
            "PUBLIC_EDITORIAL_FRESH" if title_ok and complete and
            required_links and canonical and not noindex and not any(claims)
            else "PUBLIC_STALE_OR_DIFFERENT"
        ),
    }


def audit(*, source_reader=source_get, public_reader=public_read):
    expected = reviewed_document()
    post, mode = classify(source_reader(), new_body=expected)
    if post["id"] != PINNED_POST_ID or mode != "already_applied":
        raise PublishError("WordPress authenticated source not the approved version")
    readings = {}
    for name, bypass in (("ordinary_browser", False), ("no_cache", True)):
        try:
            page, headers = public_reader(bypass_cache=bypass)
            readings[name] = {**inspect_html(page, expected=expected),
                              "cache_headers": headers}
        except (OSError, ValueError, TypeError, PublishError):
            readings[name] = {"state": "PUBLIC_GET_UNKNOWN",
                              "cache_headers": {}}
    both = all(r["state"] == "PUBLIC_EDITORIAL_FRESH"
               for r in readings.values())
    return {
        "mode": "read_only_wp_source_vs_public_views",
        "post_id": PINNED_POST_ID, "url": URL,
        "wp_source_state": "AUTHENTICATED_UPDATED_SOURCE_VERIFIED",
        "views": readings,
        "conclusion": ("ORDINARY_AND_BYPASS_PUBLIC_FRESH" if both
                       else "PUBLIC_VIEW_DIVERGENCE_OR_UNAVAILABLE"),
        "wordpress_writes": 0, "affiliate_clicks": 0,
        "limitations": "One runner and two requests; external search index and all CDN locations not proven.",
    }


def main():
    try:
        result = audit()
    except (OSError, ValueError, TypeError, KeyError, PublishError):
        print(json.dumps({"conclusion": "SOURCE_GET_UNKNOWN_OR_DRIFTED",
                          "wordpress_writes": 0,
                          "affiliate_clicks": 0}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["conclusion"] == "ORDINARY_AND_BYPASS_PUBLIC_FRESH" else 2


if __name__ == "__main__":
    sys.exit(main())
