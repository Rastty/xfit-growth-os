"""Read-only GSC-backed Pilates entry-page and topical inlink preflight.

No WordPress writes, no consent interaction, no affiliate clicks, no indexing
claims. Source-backed priority: Prometheus XFIT GSC 2026-10-21..11-17 (final),
103 impressions on the exact classic-vs-power Pilates URL. The metrics are
NOT fetched or recomputed here and never authorize an automatic release.
"""
import json
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from scripts.wp_publish import PublishError
from scripts.xfit_pilates_gsc_title_release import (
    OLD_TITLE, NEW_TITLE, SLUG, URL, classify, get_post,
)

RELATED = (
    "pilates-vs-klasicke-cviceni-jake-jsou-hlavni-rozdily-a-ktere-cviceni-je-pro-vas-lepsi",
    "jak-pilates-pro-zada-muze-pomoci-pri-rehabilitaci-po-urazu-nebo-operaci-zad",
)
ALLOWED = frozenset(("xfit.cz", "www.xfit.cz"))
MAX_BYTES = 2_000_000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def canonical_path(url, slug):
    if not isinstance(url, str):
        return False
    try:
        p = urlsplit(url)
    except ValueError:
        return False
    return (p.scheme == "https" and p.hostname in ALLOWED
            and p.port is None and not p.username and not p.password
            and p.path == "/" + slug + "/" and not p.query and not p.fragment)


class Signals(HTMLParser):
    """Extract head metadata and genuine anchors, not untrusted inline scripts."""
    SKIP = frozenset(("script", "style", "template", "noscript", "svg"))

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.head_depth = 0
        self.h1_depth = 0
        self.title_depth = 0
        self.skipped = 0
        self.h1_texts = []
        self.title_parts = []
        self.canonicals = []
        self.robots = []
        self.hrefs = []
        self._current_h1 = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.SKIP:
            self.skipped += 1
        if tag == "head":
            self.head_depth += 1
        if tag == "h1" and not self.skipped:
            self.h1_depth += 1
            if self.h1_depth == 1:
                self._current_h1 = []
        if tag == "title" and self.head_depth and not self.skipped:
            self.title_depth += 1
        if self.head_depth and tag == "link" and (
                "canonical" in (attrs.get("rel") or "").lower().split()):
            self.canonicals.append(attrs.get("href") or "")
        if self.head_depth and tag == "meta" and (
                (attrs.get("name") or "").lower() in ("robots", "googlebot")):
            self.robots.append((attrs.get("content") or "").lower())
        if tag == "a" and not self.skipped:
            href = attrs.get("href")
            if isinstance(href, str):
                self.hrefs.append(href)

    def handle_data(self, value):
        if self.skipped:
            return
        if self.h1_depth:
            self._current_h1.append(value)
        if self.title_depth:
            self.title_parts.append(value)

    def handle_endtag(self, tag):
        if tag == "h1" and self.h1_depth:
            self.h1_depth -= 1
            if not self.h1_depth:
                self.h1_texts.append(_collapse("".join(self._current_h1)))
        if tag == "title" and self.title_depth:
            self.title_depth -= 1
        if tag == "head" and self.head_depth:
            self.head_depth -= 1
        if tag in self.SKIP and self.skipped:
            self.skipped -= 1


def _collapse(text):
    return " ".join(unescape(text).split())


def parse_public(slug, html, *, robot_header=""):
    if slug not in (SLUG,) + RELATED:
        raise ValueError("Unreviewed Pilates URL")
    if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Missing or oversized public HTML")
    parsed = Signals()
    parsed.feed(html)
    robots = parsed.robots + [robot_header.lower()]
    return {
        "slug": slug,
        "h1": parsed.h1_texts,
        "document_title": _collapse("".join(parsed.title_parts))[:220],
        "canonical": ("SELF_CANONICAL" if len(parsed.canonicals) == 1
                      and canonical_path(parsed.canonicals[0], slug)
                      else "MISSING_CANONICAL" if not parsed.canonicals
                      else "MULTIPLE_CANONICALS" if len(parsed.canonicals) != 1
                      else "OTHER_CANONICAL"),
        "robots": "NOINDEX_OBSERVED" if any(
            "noindex" in x.replace(" ", "").split(",") for x in robots
        ) else "NO_NOINDEX_OBSERVED",
        "links_to_primary": any(
            canonical_path(href, SLUG) for href in parsed.hrefs
        ),
    }


def read_public(slug):
    if slug not in (SLUG,) + RELATED:
        raise ValueError("Unapproved URL")
    target = "https://xfit.cz/" + slug + "/"
    request = Request(target, headers={
        "User-Agent": "XfitGSCReadOnlyPilates/1.0",
        "Accept": "text/html",
    }, method="GET")
    with build_opener(NoRedirect()).open(request, timeout=25) as response:
        if response.status != 200 or not canonical_path(response.geturl(), slug):
            raise PublishError("Unexpected Pilates public URL response")
        payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise PublishError("Oversized public Pilates page")
        return payload.decode("utf-8", errors="replace"), (
            response.headers.get("X-Robots-Tag") or ""
        )


def audit(*, post_get=get_post, public_get=read_public):
    # Only one exact canonical WP identity. No editorial content is logged.
    source = classify(post_get())
    observed = {}
    for slug in (SLUG,) + RELATED:
        body, robots = public_get(slug)
        observed[slug] = parse_public(slug, body, robot_header=robots)
    primary = observed[SLUG]
    source_title = source["old_title"]
    h1_matches_source = primary["h1"] == [source_title]
    if (source_title == NEW_TITLE and h1_matches_source
            and primary["canonical"] == "SELF_CANONICAL"
            and primary["robots"] == "NO_NOINDEX_OBSERVED"):
        state = "TITLE_ALREADY_LIVE_NO_WRITE"
    elif (source_title == OLD_TITLE and h1_matches_source
            and primary["canonical"] == "SELF_CANONICAL"
            and primary["robots"] == "NO_NOINDEX_OBSERVED"):
        state = "OLD_TITLE_CONFIRMED_REVIEW_ONEPOST"
    else:
        state = "HOLD_SOURCE_PUBLIC_MISMATCH"

    return {
        "state": state,
        "source": "2026-11-20 Prometheus XFIT GSC 28-day finalized report",
        "gsc_period": "2026-10-21..2026-11-17",
        "observed_source_title": "NEW" if source_title == NEW_TITLE else "OLD",
        "public_h1_matches_source": h1_matches_source,
        "primary": primary,
        "related": [observed[slug] for slug in RELATED],
        "related_pages_linking_to_primary": sum(
            observed[slug]["links_to_primary"] for slug in RELATED
        ),
        "wp_posts_changed": 0,
        "wp_post_attempts": 0,
        "seo_mutations": 0,
        "release_approved": False,
        "limitations": "Public H1/canonical are not Google indexing or CTR uplift.",
    }


def main():
    try:
        print(json.dumps(audit(), ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, PublishError, KeyError, TypeError):
        print(json.dumps({
            "state": "READ_ONLY_PILATES_PREFLIGHT_INCOMPLETE",
            "wp_post_attempts": 0, "release_approved": False,
        }))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
