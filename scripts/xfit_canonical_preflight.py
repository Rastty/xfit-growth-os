"""Read-only WordPress canonical/source preflight for XFIT's 13 reviewed archive IDs.

No POST, PATCH, PUT, DELETE, backup mutation or publishing action. Only GET.
Results contain public metadata, hashes and markup counters, never raw body or credentials.
"""
import hashlib
from html.parser import HTMLParser
import json
import os
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import normalized_base, wp_request

REVIEW_IDS = frozenset((9462, 9371, 8713, 9008, 9544, 6959, 7268, 8531,
                        9923, 7305, 9765, 5804, 6558))
FIELDS = "id,slug,status,title,link,modified_gmt,content"
MAX_PAGE_BYTES = 2_000_000


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def exact_site_url(value):
    if not isinstance(value, str):
        return False
    p = urlsplit(value)
    return (p.scheme == "https" and p.hostname in {"xfit.cz", "www.xfit.cz"}
            and p.port is None and p.path not in ('', '/') and not p.username and not p.password
            and not p.query and not p.fragment)


class CanonicalLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "link":
            return
        a = dict(attrs)
        if "canonical" in (a.get("rel") or "").lower().split():
            self.hrefs.append(a.get("href") or "")

    handle_startendtag = handle_starttag


def canonical_links(source):
    parser = CanonicalLinks()
    parser.feed(source)
    return parser.hrefs


def canonical_destinations(links):
    """Only destinations' hosts and hashes, never query strings/tokens."""
    return [{"host": urlsplit(href).hostname or "relative", "sha256": digest(href)}
            for href in links[:15]]


def source(post, field, expected_id):
    if not isinstance(post, dict) or type(post.get("id")) is not int:
        raise ValueError("Unrecognized WordPress response")
    if post["id"] != expected_id or post.get("status") != "publish":
        raise ValueError("Wrong WordPress post ID or publication state")
    if not isinstance(post.get("slug"), str) or not exact_site_url(post.get("link")):
        raise ValueError("Unexpected WordPress permalink or slug")
    raw = (post.get("content") or {}).get(field)
    if not isinstance(raw, str) or not raw:
        raise ValueError("Missing WordPress content")
    return raw


def summarize(auth, fresh, public, permalink_html, expected_id):
    raw = source(auth, "raw", expected_id)
    fresh_raw = source(fresh, "raw", expected_id)
    rendered = source(public, "rendered", expected_id)
    if (auth.get("slug") != fresh.get("slug") or auth.get("slug") != public.get("slug")
            or auth.get("link") != fresh.get("link")
            or auth.get("link") != public.get("link")):
        raise ValueError("Authenticated/public permalink identity mismatch")
    if not isinstance(permalink_html, str) or len(permalink_html) < 200:
        raise ValueError("Missing public permalink HTML")
    if raw != fresh_raw or auth.get("modified_gmt") != fresh.get("modified_gmt"):
        raise ValueError("Authenticated source changed between reads")
    body_links = canonical_links(raw)
    public_links = canonical_links(permalink_html)
    return {
        "state": "READ_ONLY_SOURCE_STABLE",
        "post_id": expected_id,
        "slug": auth["slug"],
        "url": auth["link"],
        "modified_gmt": auth.get("modified_gmt"),
        "public_modified_gmt": public.get("modified_gmt"),
        "auth_raw_sha256": digest(raw),
        "public_rendered_sha256": digest(rendered),
        "same_authenticated_source": True,
        "raw_bytes": len(raw.encode("utf-8")),
        "nested_doctype_count": len(re.findall(r"<!doctype\b", raw, re.I)),
        "raw_body_canonical_count": len(body_links),
        "raw_body_canonical_destinations": canonical_destinations(body_links),
        "raw_coupon_5nm2022_count": raw.upper().count("5NM2022"),
        "public_page_canonical_count": len(public_links),
        "public_page_canonical_destinations": canonical_destinations(public_links),
        "public_coupon_5nm2022_count": permalink_html.upper().count("5NM2022"),
        "remote_post_attempts": 0,
    }


def wp_authenticated(post_id, cache_bust=False):
    suffix = "&xfit_preflight=" + str(time.time_ns()) if cache_bust else ""
    return wp_request(normalized_base(), "posts/" + str(post_id)
                      + "?context=edit&_fields=" + FIELDS + suffix)


def public_get(url):
    if not exact_site_url(url.split("?", 1)[0]):
        raise ValueError("Unexpected public retrieval URL")
    req = Request(url, headers={"User-Agent": "XFITCanonicalPreflight/1.0",
                                "Cache-Control": "no-cache"}, method="GET")
    with urlopen(req, timeout=25) as response:
        if not exact_site_url(response.geturl().split("?", 1)[0]):
            raise ValueError("Unexpected public redirect")
        body = response.read(MAX_PAGE_BYTES + 1)
    if len(body) > MAX_PAGE_BYTES:
        raise ValueError("Oversized public response")
    return body.decode("utf-8")


def run():
    post_id = int(os.environ.get("XFIT_PREFLIGHT_POST_ID", "9371"))
    if post_id not in REVIEW_IDS:
        raise ValueError("Post ID not in source-reviewed canonical queue")
    auth = wp_authenticated(post_id)
    fresh = wp_authenticated(post_id, cache_bust=True)
    rest = json.loads(public_get(
        "https://xfit.cz/wp-json/wp/v2/posts/" + str(post_id)
        + "?_fields=" + FIELDS))
    page = public_get(rest["link"])
    print(json.dumps(summarize(auth, fresh, rest, page, post_id),
                     ensure_ascii=False))


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        # Do not log exception bodies from WordPress; only the failure class.
        print(json.dumps({"state": "READ_ONLY_PREFLIGHT_FAILED",
                          "error_type": type(exc).__name__,
                          "remote_post_attempts": 0}))
        raise SystemExit(2) from None
