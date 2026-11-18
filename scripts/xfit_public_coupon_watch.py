#!/usr/bin/env python3
"""Read-only public-page proof for two unresolved expired-coupon incidents.

This deliberately does not use authenticated WP REST, secrets or a write route.
Missing/ambiguous public evidence is UNKNOWN, never counted as a clean page.
"""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


TARGETS = (
    (11110, "doporucene-davkovani-a-cykly-kreatinu-pro-svalovy-rozvoj"),
    (11090, "5-duvodu-proc-by-mel-byt-kreatin-soucasti-tveho-stravovaciho-planu-pro-fitness"),
)
PROMO_CODE = "5nm2022"
MAX_HTML_BYTES = 3_000_000
REPORT = Path("reports/xfit-public-coupon-watch.json")
IGNORED_TAGS = {"script", "style", "template", "noscript", "svg"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
             "meta", "param", "source", "track", "wbr"}


class NoRedirects(HTTPRedirectHandler):
    """Never follow an unexpected external or moved URL during a public audit."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class PublicArticle(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.body_seen = False
        self.in_body = False
        self.body_post_ids = set()
        self.canonicals = []
        self.stack = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "link" and "canonical" in (values.get("rel") or "").lower().split():
            hrefs = [value for key, value in attrs if key == "href"]
            self.canonicals.append(hrefs[0] if len(hrefs) == 1 else "")
        if tag == "body":
            self.body_seen = True
            self.in_body = True
            self.body_post_ids.update(int(n) for n in re.findall(
                r"(?:^|\s)postid-(\d+)(?=\s|$)", values.get("class") or ""))
        hidden = (tag in IGNORED_TAGS or "hidden" in values
                  or values.get("aria-hidden", "").lower() == "true"
                  or bool(re.search(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\b",
                                    values.get("style") or "", re.I)))
        if self.in_body and tag not in VOID_TAGS:
            self.stack.append((tag, hidden or bool(self.stack and self.stack[-1][1])))

    def handle_endtag(self, tag):
        if self.in_body:
            matching = next((i for i in range(len(self.stack) - 1, -1, -1)
                             if self.stack[i][0] == tag), None)
            if matching is not None:
                del self.stack[matching:]
        if tag == "body":
            self.in_body = False

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, value):
        if self.in_body and not (self.stack and self.stack[-1][1]):
            self.text.append(value)


def expected_url(slug):
    return "https://xfit.cz/" + slug + "/"


def exact_article_url(url, slug):
    try:
        part = urlsplit(url)
        return (part.scheme == "https" and part.hostname in {"xfit.cz", "www.xfit.cz"}
                and not part.username and not part.password and part.port is None
                and not part.query and not part.fragment
                and part.path.rstrip("/") == "/" + slug)
    except ValueError:
        return False


def classify_html(source, post_id, slug):
    parser = PublicArticle()
    parser.feed(source)
    if (not parser.body_seen or
            (parser.canonicals and (len(parser.canonicals) != 1 or
                                    not exact_article_url(parser.canonicals[0], slug))) or
            (not parser.canonicals and post_id not in parser.body_post_ids) or
            (parser.body_post_ids and post_id not in parser.body_post_ids)):
        return "UNVERIFIED_IDENTITY", 0
    text = "".join(parser.text).casefold()
    mentions = text.count(PROMO_CODE)
    return ("EXPIRED_COUPON_VISIBLE" if mentions else "PUBLIC_NO_COUPON_OBSERVED", mentions)


def probe(post_id, slug, opener=None):
    opener = opener or build_opener(NoRedirects())
    url = expected_url(slug)
    try:
        with opener.open(Request(url, headers={"User-Agent": "XFIT-Public-Coupon-Watch/1.0",
                                               "Accept": "text/html"}), timeout=25) as response:
            if response.status != 200 or not response.headers.get("Content-Type", "").lower().startswith("text/html"):
                return {"id": post_id, "url": url, "state": "UNVERIFIED_HTTP_RESPONSE"}
            if not exact_article_url(response.geturl(), slug):
                return {"id": post_id, "url": url, "state": "UNVERIFIED_FINAL_URL"}
            raw = response.read(MAX_HTML_BYTES + 1)
            if len(raw) > MAX_HTML_BYTES:
                return {"id": post_id, "url": url, "state": "UNVERIFIED_RESPONSE_TOO_LARGE"}
            # A damaged byte stream must not produce a falsely clean result.
            source = raw.decode("utf-8", errors="strict")
    except (HTTPError, URLError, TimeoutError, UnicodeError, OSError, ValueError):
        return {"id": post_id, "url": url, "state": "UNVERIFIED_FETCH"}
    state, mentions = classify_html(source, post_id, slug)
    return {"id": post_id, "url": url, "state": state, "visible_mentions": mentions}


def run(opener=None, report=REPORT):
    results = [probe(post_id, slug, opener) for post_id, slug in TARGETS]
    counts = {
        "still_visible": sum(x["state"] == "EXPIRED_COUPON_VISIBLE" for x in results),
        "clean_observed": sum(x["state"] == "PUBLIC_NO_COUPON_OBSERVED" for x in results),
        "unverified": sum(x["state"].startswith("UNVERIFIED") for x in results),
    }
    output = {"state": "PUBLIC_ONLY_CLEAN_OBSERVED" if counts["clean_observed"] == len(TARGETS)
              else "PUBLIC_COUPON_REQUIRES_ATTENTION", "counts": counts,
              "targets": results, "source": "public HTML only", "wordpress_writes": 0,
              "authenticated_wp_verified": False, "affiliate_conversions": "UNKNOWN"}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))
    return 0 if counts["clean_observed"] == len(TARGETS) else 2


if __name__ == "__main__":
    sys.exit(run())
