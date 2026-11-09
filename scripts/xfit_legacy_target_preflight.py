"""Read-only, pinned source and public permalink preflight before onepost SEO work.

This does not grant permission to edit an archive post. GitHub Actions logs
only bounded public metadata and headings; never the raw article, WP token,
commerce links, personal data, or outbound query parameters.
"""
from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import wp_request, normalized_base

POST_ID = 10835
SLUG = "kde-koupit-nejlevnejsi-kreatin-pro-fitness"
PUBLIC_URL = "https://xfit.cz/" + SLUG + "/"
ADVISOR = "https://xfit.cz/xfit-os-kreatin-poradce/"
MAX_SOURCE_BYTES = 400_000
MAX_PUBLIC_BYTES = 1_000_000


def exact_public_url(url):
    if not isinstance(url, str):
        return False
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname in ("xfit.cz", "www.xfit.cz")
                and p.username is None and p.password is None and p.port is None
                and not p.query and not p.fragment
                and p.path.rstrip("/") == "/" + SLUG)
    except ValueError:
        return False


class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.buffers = []
        self.headings = []
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if isinstance(href, str):
                self.links.add(unescape(href))
        if tag in ("h1", "h2"):
            self.stack.append(tag)
            self.buffers.append([])

    def handle_data(self, data):
        if self.buffers:
            self.buffers[-1].append(data)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            text = " ".join("".join(self.buffers.pop()).split())
            self.stack.pop()
            if text:
                self.headings.append((tag, text))


def clean_heading(heading):
    # Headings are public, but only a bounded preview is needed for review.
    heading = re.sub(r"https?://\\S+|[\\w.+-]+@[\\w.-]+", "[redacted]", heading)
    return heading[:135]


def get_public(url):
    req = Request(url, headers={"User-Agent": "XfitLegacyPreflight/1.0"})
    with urlopen(req, timeout=18) as response:
        data = response.read(MAX_PUBLIC_BYTES + 1)
        if len(data) > MAX_PUBLIC_BYTES:
            raise ValueError("public HTML too large")
        return response.status, response.geturl(), data.decode("utf-8", "replace")


def review(post, *, public_reader=get_public):
    report = {
        "candidate_wp_id": POST_ID,
        "candidate_slug": SLUG,
        "advisor_link_already_present": None,
        "public_status": "UNKNOWN",
        "decision": "BLOCKED_UNVERIFIED",
        "remote_writes": 0,
    }
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish" or not exact_public_url(post.get("link"))):
        report["source_state"] = "IDENTITY_OR_STATUS_MISMATCH"
        return report
    title = unescape(re.sub(r"<[^>]*>", " ", (post.get("title") or {}).get("raw", "")))
    title = " ".join(title.split())
    raw = (post.get("content") or {}).get("raw")
    if (not title or "kreatin" not in title.casefold() or "koupit" not in title.casefold()
            or not isinstance(raw, str) or not 1500 <= len(raw.encode("utf-8")) <= MAX_SOURCE_BYTES):
        report["source_state"] = "CONTENT_OR_INTENT_UNVERIFIED"
        return report
    visible = Visible()
    visible.feed(raw)
    report.update(
        source_state="PUBLISHED_SOURCE_VERIFIED",
        public_title=clean_heading(title),
        public_h2_preview=[clean_heading(h) for tag, h in visible.headings if tag == "h2"][:6],
        source_chars=len(raw),
        advisor_link_already_present=ADVISOR in visible.links,
    )
    try:
        status, final_url, body = public_reader(PUBLIC_URL)
        public = Visible()
        public.feed(body)
        h1 = [h for tag, h in public.headings if tag == "h1"]
        if (status == 200 and exact_public_url(final_url)
                and any("kreatin" in h.casefold() for h in h1)):
            report["public_status"] = "EXACT_PUBLIC_ARTICLE_CONFIRMED"
        else:
            report["public_status"] = "PUBLIC_IDENTITY_UNVERIFIED"
    except (OSError, ValueError, TypeError, UnicodeError):
        report["public_status"] = "PUBLIC_READ_UNAVAILABLE"
    report["decision"] = (
        "ALREADY_LINKED" if report["advisor_link_already_present"]
        and report["public_status"] == "EXACT_PUBLIC_ARTICLE_CONFIRMED"
        else "ELIGIBLE_FOR_MANUAL_ONEPOST_REVIEW"
        if not report["advisor_link_already_present"]
        and report["public_status"] == "EXACT_PUBLIC_ARTICLE_CONFIRMED"
        else "BLOCKED_UNVERIFIED"
    )
    return report


def main():
    try:
        post = wp_request(
            normalized_base(),
            "posts/" + str(POST_ID)
            + "?context=edit&_fields=id,slug,status,title,content,link"
        )
        result = review(post)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Exception message can contain a token-bearing request URL.
        result = {"candidate_wp_id": POST_ID, "source_state": "READ_UNAVAILABLE",
                  "error_class": type(exc).__name__, "decision": "BLOCKED_UNVERIFIED",
                  "remote_writes": 0}
    print(json.dumps({"state": "XFIT_PINNED_LEGACY_READONLY", **result},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
