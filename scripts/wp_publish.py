#!/usr/bin/env python3
"""Minimal safe WordPress REST publisher; no external dependencies.

    python scripts/wp_publish.py --file content/ready/xfit-os-protein-guide.json --dry-run
    python scripts/wp_publish.py --file content/ready/xfit-os-protein-guide.json
    python scripts/wp_publish.py --file content/ready/xfit-os-protein-guide.json --publish

Draft is the default; --publish is explicit. All writes require secrets in env.
"""
import argparse
import base64
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MARKER = "<!-- xfit-growth-os:v1 -->"
SLUG_RE = re.compile(r"xfit-os-[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class PublishError(Exception):
    pass


def validate_document(doc):
    if not isinstance(doc, dict):
        raise PublishError("Document must be a JSON object")
    title, slug, content = doc.get("title"), doc.get("slug"), doc.get("content")
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise PublishError("Slug must start with xfit-os- and contain lowercase alphanumerics/hyphens")
    if not isinstance(title, str) or not 8 <= len(title.strip()) <= 180:
        raise PublishError("Title length must be 8..180")
    if not isinstance(content, str) or len(content.strip()) < 300:
        raise PublishError("Content must contain at least 300 characters")
    if re.search(r"<\s*(?:script|iframe|form)\b|on\w+\s*=", content, re.I):
        raise PublishError("Unsafe active HTML detected: no script/iframe/form/inline JS")
    excerpt = doc.get("excerpt", "")
    if not isinstance(excerpt, str) or len(excerpt) > 600:
        raise PublishError("Excerpt must be a string of up to 600 chars")
    return {"slug": slug, "title": title.strip(), "content": MARKER + "\n" + content, "excerpt": excerpt}


def normalized_base():
    url = os.getenv("WP_BASE_URL", "").strip().rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ("xfit.cz", "www.xfit.cz") or parsed.username or parsed.password or parsed.port or parsed.path:
        raise PublishError("WP_BASE_URL must be https://xfit.cz (or www.xfit.cz) without path/credentials")
    return url


def wp_request(base, path, *, payload=None):
    username = os.getenv("WP_USERNAME", "").strip()
    password = os.getenv("WP_APP_PASSWORD", "").strip()
    if not username or not password:
        raise PublishError("Missing WP_USERNAME or WP_APP_PASSWORD (GitHub Actions Secrets)")
    url = base + "/wp-json/wp/v2/" + path
    auth = base64.b64encode((username + ":" + password).encode()).decode()
    headers = {"Authorization": "Basic " + auth, "Accept": "application/json", "User-Agent": "XfitGrowthOS/0.1"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, headers=headers, data=data, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as ex:
        # Do not echo server response: it may contain sensitive data.
        raise PublishError("WordPress REST API returned HTTP " + str(ex.code)) from ex
    except (OSError, ValueError) as ex:
        raise PublishError("WordPress REST request failed (" + type(ex).__name__ + ")") from ex


def existing_content(post):
    content = post.get("content", {})
    return (str(content.get("raw", "")) + str(content.get("rendered", ""))) if isinstance(content, dict) else ""


def plain(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip().lower()


def verify_public(url, title):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ("xfit.cz", "www.xfit.cz"):
        raise PublishError("Unexpected public URL host; refusing verification")
    req = urllib.request.Request(url, headers={"User-Agent": "XfitGrowthOS/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            page = r.read(2_000_000).decode("utf-8", errors="replace")
    except (OSError, ValueError) as ex:
        raise PublishError("Public verification failed (" + type(ex).__name__ + ")") from ex
    if plain(title) not in plain(page):
        raise PublishError("Public URL loads but expected article title is not visible")


def publish(doc, *, live=False):
    base = normalized_base()
    slug = doc["slug"]
    posts = wp_request(base, "posts?" + urllib.parse.urlencode({
        "slug": slug, "context": "edit", "per_page": 1,
        "_fields": "id,slug,status,content,link",
    }))
    if not isinstance(posts, list):
        raise PublishError("Unexpected WordPress API listing")
    existing = next((p for p in posts if p.get("slug") == slug), None)
    if existing and MARKER not in existing_content(existing):
        raise PublishError("Collision with an existing post not owned by Xfit Growth OS; refusing overwrite")
    status = "publish" if live else "draft"
    body = dict(doc, status=status)
    route = "posts/" + str(int(existing["id"])) if existing else "posts"
    saved = wp_request(base, route, payload=body)
    post_id = saved.get("id")
    if not isinstance(post_id, int):
        raise PublishError("WP write API did not return post id")
    # Authenticated API read-back is mandatory, even for drafts.
    read = wp_request(base, "posts/" + str(post_id) + "?context=edit&_fields=id,slug,status,content,link")
    if read.get("slug") != slug or read.get("status") != status or MARKER not in existing_content(read):
        raise PublishError("WP write was accepted but draft/publish read-back verification FAILED")
    link = read.get("link")
    result = {"state": "api_accepted", "post_id": post_id, "slug": slug, "status": status, "url": link}
    print(json.dumps(result, ensure_ascii=False))
    if live:
        if not isinstance(link, str):
            raise PublishError("Public URL missing")
        verify_public(link, doc["title"])
        result["state"] = "live_verified"
    else:
        result["state"] = "draft_verified"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--publish", action="store_true", help="Explicitly publish instead of draft")
    args = parser.parse_args()
    if args.dry_run and args.publish:
        parser.error("Choose dry-run or --publish, not both")
    try:
        source = Path(args.file)
        doc = validate_document(json.loads(source.read_text(encoding="utf-8")))
        if args.dry_run:
            print(json.dumps({"state": "validated_only", "slug": doc["slug"], "no_remote_writes": True}))
            return 0
        result = publish(doc, live=args.publish)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (PublishError, OSError, json.JSONDecodeError) as ex:
        print("XFIT_ERROR: " + str(ex), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
