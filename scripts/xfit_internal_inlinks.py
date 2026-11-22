"""Read-only, bounded evidence of XFIT guide links in public post bodies.

An absent link here does NOT mean an orphan URL: navigation, pages, external
links and crawlers are outside the scope of a WordPress post-body inventory.
"""

from collections import defaultdict
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit


GUIDE_SLUGS = (
    "xfit-os-doplnky-pro-zacatecniky",
    "xfit-os-protein-guide",
    "xfit-os-kreatin-poradce",
    "xfit-os-syrovatkovy-protein-porovnani",
    "xfit-os-kreatin-nebo-protein",
    "xfit-os-cena-proteinu-podle-etikety",
    "xfit-os-protein-bez-laktozy",
    "xfit-os-jak-vybrat-rostlinny-protein",
)
ALLOWED_HOSTS = frozenset(("xfit.cz", "www.xfit.cz"))
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,179}\Z")
MAX_SOURCE_EXAMPLES = 12


class BodyAnchors(HTMLParser):
    """Only genuine post-body anchors, not comments or template/script markup."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []
        self.inactive = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self.inactive += 1
        if tag == "a" and not self.inactive:
            href = dict(attrs).get("href")
            if isinstance(href, str):
                self.urls.append(href)

    def handle_startendtag(self, tag, attrs):
        if tag == "a" and not self.inactive:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template") and self.inactive:
            self.inactive -= 1


def target_from_href(href, source_url):
    """Match exact guide paths only, without emitting query or affiliate IDs."""
    if not isinstance(href, str) or not isinstance(source_url, str):
        return None
    href = href.strip()
    if not href or href.startswith("#"):
        return None
    try:
        source = urlsplit(source_url)
        if (source.scheme != "https" or source.hostname not in ALLOWED_HOSTS
                or source.username or source.password or source.port is not None):
            return None
        destination = urlsplit(urljoin(source_url, href))
        if (destination.scheme not in ("https", "http")
                or destination.hostname not in ALLOWED_HOSTS
                or destination.username or destination.password
                or destination.port is not None):
            return None
    except ValueError:
        return None
    slug = destination.path.strip("/")
    # Queries may be present on old links, but are never recorded or followed.
    return slug if slug in GUIDE_SLUGS else None


def build_coverage(posts):
    """Build a deterministic, deduplicated source-post-to-guide coverage report."""
    referring = defaultdict(dict)
    scanned = 0
    for post in posts:
        if not isinstance(post, dict) or type(post.get("id")) is not int or post["id"] <= 0:
            continue
        scanned += 1
        slug, source_url = post.get("slug"), post.get("link")
        if not isinstance(slug, str) or not SLUG.fullmatch(slug):
            continue
        if not isinstance(source_url, str):
            continue
        body = (post.get("content") or {}).get("rendered")
        if not isinstance(body, str):
            continue
        anchors = BodyAnchors()
        anchors.feed(body)
        linked = {target_from_href(href, source_url) for href in anchors.urls}
        linked.discard(None)
        for target in linked:
            if target == slug:
                continue
            referring[target][post["id"]] = {"id": post["id"], "slug": slug}
    guides = []
    for slug in GUIDE_SLUGS:
        sources = sorted(referring[slug].values(), key=lambda source: source["id"])
        guides.append({
            "slug": slug,
            "source_post_count": len(sources),
            "sample_source_posts": sources[:MAX_SOURCE_EXAMPLES],
            "source_sample_truncated": len(sources) > MAX_SOURCE_EXAMPLES,
            "no_post_body_inlink_observed": len(sources) == 0,
        })
    return {
        "scope": "published_post_body_anchor_tags_only",
        "posts_examined": scanned,
        "guide_count": len(GUIDE_SLUGS),
        "guides": guides,
        "not_covered": "menus_pages_widgets_external_backlinks_google_indexing",
        "no_wordpress_writes": True,
    }
