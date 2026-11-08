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
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

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
    post_id = doc.get("wp_post_id")
    if post_id is not None and (type(post_id) is not int or post_id <= 0):
        raise PublishError("wp_post_id must be a positive integer")
    result = {"slug": slug, "title": title.strip(), "content": MARKER + "\n" + content, "excerpt": excerpt}
    if post_id is not None:
        result["wp_post_id"] = post_id
    return result


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
    # Read-only GET may be retried after transient WEDOS handshake failures.
    # Never automatically retry POST: a timed-out write may already have
    # committed, and repeating it could create duplicate posts/redirects.
    attempts = 3 if payload is None else 1
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as ex:
            if payload is None and attempt < attempts - 1 and ex.code in (429, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            # Do not echo server response: it may contain sensitive data.
            raise PublishError("WordPress REST API returned HTTP " + str(ex.code)) from ex
        except (OSError, ValueError) as ex:
            if payload is None and attempt < attempts - 1 and isinstance(ex, OSError):
                time.sleep(2 * (attempt + 1))
                continue
            raise PublishError("WordPress REST request failed (" + type(ex).__name__ + ")") from ex
    raise PublishError("WordPress REST GET retries exhausted")


def existing_content(post):
    content = post.get("content", {})
    return (str(content.get("raw", "")) + str(content.get("rendered", ""))) if isinstance(content, dict) else ""


def plain(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip().lower()


# Public source freshness: the title alone can match a stale cached release.
# Extract rendered text from all meaningful editorial blocks, preserving inline
# links/strong elements, and check it against a real public HTML readback.
class VisibleArticle(HTMLParser):
    BLOCKS = {"p", "li", "h2", "h3", "h4", "blockquote", "td", "th", "caption"}
    IGNORED = {"script", "style", "noscript", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.segments = []
        self.capture = []
        self.ignore_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORED:
            self.ignore_depth += 1
        elif not self.ignore_depth and tag in self.BLOCKS:
            self.parts.append(" ")
            self.capture.append((tag, []))

    def handle_data(self, data):
        if self.ignore_depth:
            return
        self.parts.append(data)
        for _tag, buffer in self.capture:
            buffer.append(data)

    def handle_endtag(self, tag):
        if tag in self.IGNORED:
            self.ignore_depth = max(0, self.ignore_depth - 1)
            return
        if self.ignore_depth or tag not in self.BLOCKS:
            return
        self.parts.append(" ")
        if self.capture and self.capture[-1][0] == tag:
            _, buffer = self.capture.pop()
            segment = normalize_visible("".join(buffer))
            if len(segment) >= 32:
                self.segments.append(segment)


# WordPress wptexturize changes cosmetic punctuation when rendering source
# HTML. Never normalize numbers, products, prices, URLs or actual words.
_TYPOGRAPHY = str.maketrans({
    "–": "-", "—": "-", "−": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
})


def normalize_visible(value):
    # Unescape entities and unify whitespace and narrowly specified
    # typographic transformations. All substantive body segments still
    # have to be visible in the same public page.
    return " ".join(html.unescape(value).casefold().translate(_TYPOGRAPHY).split())


def article_visible(source):
    parser = VisibleArticle()
    parser.feed(source)
    return normalize_visible("".join(parser.parts)), parser.segments


def verify_public(url, title, expected_content):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ("xfit.cz", "www.xfit.cz")
            or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment or parsed.path.rstrip("/") in ("", "/")):
        raise PublishError("Unexpected public URL identity; refusing verification")
    # A same-host redirect to another post or homepage is NOT proof this
    # specific owned article was published. Minor trailing slash and www
    # canonicalization are acceptable; never accept changed path or query.
    expected_path = parsed.path.rstrip("/")
    expected_text, segments = article_visible(expected_content)
    if len(expected_text) < 250 or len(segments) < 3:
        raise PublishError("No usable editorial body evidence for public freshness check")
    expected_title = normalize_visible(title)
    # New text must be verifiable, not just an old page with the same title.
    for attempt in range(3):
        req = urllib.request.Request(url, headers={
            "User-Agent": "XfitGrowthOS/0.2",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                target = urllib.parse.urlsplit(response.geturl())
                if (response.status != 200 or target.scheme != "https"
                        or target.hostname not in ("xfit.cz", "www.xfit.cz")
                        or target.username or target.password or target.port
                        or target.query or target.fragment
                        or target.path.rstrip("/") != expected_path):
                    raise PublishError("Public verification returned different canonical page")
                # Fail on truncated HTML rather than treating partial text
                # as a complete published page.
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise PublishError("Public verification page too large")
                public_html = data.decode("utf-8", errors="replace")
        except (OSError, ValueError) as ex:
            if attempt == 2:
                raise PublishError("Public verification failed (" + type(ex).__name__ + ")") from ex
            time.sleep(2)
            continue
        public_text, _ = article_visible(public_html)
        if expected_title in public_text and all(chunk in public_text for chunk in segments):
            return True
        if attempt < 2:
            time.sleep(2)
    raise PublishError("Public page still shows old/incomplete article body; cache or renderer stale")


def publish(doc, *, live=False):
    # Hard gate: a successful WP API call must never substitute for quality.
    try:
        try:
            from scripts.xfit_editorial_gate import check_document
        except ModuleNotFoundError:
            from xfit_editorial_gate import check_document
        check_document(doc)
    except ValueError as exc:
        raise PublishError("Editorial quality gate failed: " + str(exc)) from exc
    base = normalized_base()
    slug = doc["slug"]
    post_id = doc.get("wp_post_id")
    if post_id:
        # A pinned ID prevents duplicate articles if WordPress excludes draft posts
        # from its default list query or if a slug becomes temporarily unavailable.
        existing = wp_request(base, "posts/" + str(post_id) + "?context=edit&_fields=id,slug,status,content,link")
        if existing.get("id") != post_id or existing.get("slug") != slug:
            raise PublishError("Pinned wp_post_id does not match article slug; refusing update")
    else:
        posts = wp_request(base, "posts?" + urllib.parse.urlencode({
            "slug": slug, "context": "edit", "status": "any", "per_page": 10,
            "_fields": "id,slug,status,content,link",
        }))
        if not isinstance(posts, list):
            raise PublishError("Unexpected WordPress API listing")
        matched = [p for p in posts if p.get("slug") == slug]
        if len(matched) > 1:
            raise PublishError("Multiple WordPress posts share owned slug; refusing write")
        existing = matched[0] if matched else None
    if existing and MARKER not in existing_content(existing):
        raise PublishError("Collision with an existing post not owned by Xfit Growth OS; refusing overwrite")
    status = "publish" if live else "draft"
    body = {k: v for k, v in doc.items() if k != "wp_post_id"}
    body["status"] = status
    route = "posts/" + str(int(existing["id"])) if existing else "posts"
    saved = wp_request(base, route, payload=body)
    post_id = saved.get("id")
    if not isinstance(post_id, int):
        raise PublishError("WP write API did not return post id")
    # Authenticated API read-back is mandatory, even for drafts.
    read = wp_request(base, "posts/" + str(post_id) + "?context=edit&_fields=id,slug,status,content,link")
    if read.get("slug") != slug or read.get("status") != status or MARKER not in existing_content(read):
        raise PublishError("WP write was accepted but draft/publish read-back verification FAILED")
    raw = read.get("content", {}).get("raw") if isinstance(read.get("content"), dict) else None
    if not isinstance(raw, str) or article_visible(raw)[0] != article_visible(doc["content"])[0]:
        raise PublishError("WP edit-context raw body differs from approved published text")
    link = read.get("link")
    result = {"state": "api_accepted", "post_id": post_id, "slug": slug, "status": status, "url": link}
    print(json.dumps(result, ensure_ascii=False))
    if live:
        if not isinstance(link, str):
            raise PublishError("Public URL missing")
        verify_public(link, doc["title"], doc["content"])
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
