#!/usr/bin/env python3
"""Read-only source-versus-public freshness probe for XFIT decision funnel.

No uploads, retries of POST, user events, cookies, or full WP content in logs.
Helps distinguish a successful WP write from public cache/render staleness.
"""
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.wp_publish import PublishError, normalized_base, wp_request

TARGETS = (
    ("xfit-os-doplnky-pro-zacatecniky", 25458, "Nejste si jistí, zda potřebujete protein, kreatin"),
    ("xfit-os-kreatin-nebo-protein", 25504, "Jak poznat, co je skutečně levnější?"),
    ("xfit-os-kreatin-poradce", 25455, "Dvě cesty k výběru podle ceny"),
    ("xfit-os-syrovatkovy-protein-porovnani", 25456, "Dvě cesty k výběru podle ceny"),
)
ALLOWED_CACHE_HEADERS = ("Age", "Cache-Control", "X-Cache", "X-LiteSpeed-Cache", "CF-Cache-Status", "X-Proxy-Cache")
REPORT = Path("reports/xfit-public-freshness.json")


def owns_public_url(url, slug):
    u = urllib.parse.urlsplit(url or "")
    return (u.scheme == "https" and u.hostname in ("xfit.cz", "www.xfit.cz")
            and not u.username and not u.password and not u.port and not u.query
            and not u.fragment and u.path.rstrip("/") == "/" + slug)


def visible_has(html_source, phrase):
    text = html.unescape(re.sub(r"<[^>]+>", " ", html_source))
    return " ".join(phrase.casefold().split()) in " ".join(text.casefold().split())


def public_get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "XfitPublicFreshnessMonitor/1.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=25) as response:
        final = response.geturl()
        if not owns_public_url(final, urllib.parse.urlsplit(url).path.strip("/")) or response.status != 200:
            raise PublishError("Unexpected public page response/redirect")
        page = response.read(2000000).decode("utf-8", errors="replace")
        cache = {k: response.headers.get(k) for k in ALLOWED_CACHE_HEADERS if response.headers.get(k)}
        return page, cache


def probe(target, *, read_post=None, read_public=None):
    slug, post_id, marker = target
    read_post = read_post or (lambda ident: wp_request(
        normalized_base(), "posts/" + str(ident) +
        "?context=edit&_fields=id,slug,status,content,link"))
    read_public = read_public or public_get
    post = read_post(post_id)
    if post.get("id") != post_id or post.get("slug") != slug or post.get("status") != "publish":
        raise PublishError("WordPress identity/status drift for " + slug)
    if not owns_public_url(post.get("link"), slug):
        raise PublishError("WordPress returned a noncanonical URL for " + slug)
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str) or "<!-- xfit-growth-os:v1 -->" not in raw:
        raise PublishError("Missing controlled WordPress source for " + slug)
    source_has = marker.casefold() in html.unescape(raw).casefold()
    try:
        page, headers = read_public(post["link"])
    except (OSError, ValueError, PublishError) as exc:
        return {"slug": slug, "post_id": post_id, "status": "PUBLIC_READ_ERROR",
                "wp_source_has_target": source_has, "reason": type(exc).__name__}
    public_has = visible_has(page, marker)
    status = ("PUBLIC_FRESH" if source_has and public_has
              else "SOURCE_NOT_UPDATED" if not source_has
              else "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
    return {"slug": slug, "post_id": post_id, "status": status,
            "wp_source_has_target": source_has, "public_has_target": public_has,
            "cache_headers": headers}


def main():
    rows = []
    for target in TARGETS:
        try:
            rows.append(probe(target))
        except (PublishError, OSError, ValueError) as exc:
            rows.append({"slug": target[0], "post_id": target[1],
                         "status": "BLOCKED_MANUAL_REVIEW", "reason": type(exc).__name__})
    report = {"site": "https://xfit.cz", "mode": "read_only_freshness",
              "wordpress_writes": 0, "results": rows}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if all(row.get("status") == "PUBLIC_FRESH" for row in rows) else 2


if __name__ == "__main__":
    sys.exit(main())
