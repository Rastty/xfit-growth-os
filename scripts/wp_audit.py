#!/usr/bin/env python3
"""Read-only public WordPress content sample audit. No WordPress credentials required."""
import argparse
import collections
import datetime
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://xfit.cz/wp-json/wp/v2/posts"
TITLE_TAG_RE = re.compile(r"<[^>]*>")
LINK_RE = re.compile(r'<a\b[^>]*href=["\x27]([^"\x27]+)', re.I)
HOST = "xfit.cz"


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(TITLE_TAG_RE.sub(" ", value or ""))).strip()


def fetch_page(page, size):
    url = API + "?" + urllib.parse.urlencode({"page": page, "per_page": size, "_fields": "id,date,link,slug,title,content"})
    req = urllib.request.Request(url, headers={"User-Agent": "XfitGrowthOS-Audit/0.1"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def audit(pages, size):
    data = []
    failed_page = None
    for page in range(1, pages + 1):
        try:
            batch = fetch_page(page, size)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            failed_page = {"page": page, "error_type": type(exc).__name__}
            break
        if not isinstance(batch, list):
            failed_page = {"page": page, "error_type": "unexpected_response"}
            break
        data.extend(batch)
        if len(batch) < size:
            break
    title_map = collections.defaultdict(list)
    suspected = []
    thin = []
    for p in data:
        ident = p.get("id")
        title = clean((p.get("title") or {}).get("rendered") or "")
        body = (p.get("content") or {}).get("rendered") or ""
        normalized = title.lower()
        if normalized:
            title_map[normalized].append({"id": ident, "url": p.get("link")})
        if len(clean(body)) < 500:
            thin.append({"id": ident, "url": p.get("link"), "chars": len(clean(body))})
        external = set()
        for href in LINK_RE.findall(body):
            parsed = urllib.parse.urlsplit(html.unescape(href))
            if parsed.scheme in ("http", "https") and parsed.hostname and parsed.hostname not in (HOST, "www." + HOST):
                external.add(parsed.hostname.lower())
        if external:
            suspected.append({"id": ident, "url": p.get("link"), "external_hosts": sorted(external)[:20]})
    return {
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "public posts, limited sample; not a full archive audit",
        "scanned": len(data),
        "duplicate_titles": [v for v in title_map.values() if len(v) > 1],
        "thin_content_candidates": thin[:100],
        "posts_with_external_domains": suspected[:100],
        "interrupted_at": failed_page,
        "notes": ["External links are NOT automatically spam.", "Do not delete or redirect from this sample.", "Compare with GSC and full WP export before archive cleanup."]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--size", type=int, default=50)
    parser.add_argument("--output", default="reports/archive-audit.json")
    args = parser.parse_args()
    if not 1 <= args.pages <= 25 or not 1 <= args.size <= 100:
        parser.error("pages must be 1..25 and size 1..100")
    result = audit(args.pages, args.size)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("scanned", "interrupted_at", "scope")}, ensure_ascii=False))
    return 0 if result["scanned"] > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
