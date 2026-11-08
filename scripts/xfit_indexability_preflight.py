#!/usr/bin/env python3
"""Bounded public XFIT technical indexability preflight for six GSC-flagged guides.

This is NOT a Google indexation decision. No credentials, WP writes, plugins,
indexing API requests, ranking claims, affiliate clicks or tracking requests.
Only exact xfit.cz public pages, robots.txt, and two sitemap entrypoints.
"""
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SITE = "https://xfit.cz"
OWNED = (
    "xfit-os-doplnky-pro-zacatecniky",
    "xfit-os-protein-guide",
    "xfit-os-kreatin-poradce",
    "xfit-os-syrovatkovy-protein-porovnani",
    "xfit-os-kreatin-nebo-protein",
    "xfit-os-cena-proteinu-podle-etikety",
)
REFERERS = ("jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates",)
REPORT = Path("reports/xfit-indexability-readonly.json")
MAX_BYTES = 2_500_000
ALLOWED = frozenset(("xfit.cz", "www.xfit.cz"))


class HeadAndLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.canonicals = []
        self.robot_policies = []
        self.links = set()
        self.h1_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "head":
            self.in_head = True
        elif tag == "h1":
            self.h1_count += 1
        elif self.in_head and tag == "link" and "canonical" in (
                a.get("rel") or "").lower().split():
            self.canonicals.append(a.get("href") or "")
        elif self.in_head and tag == "meta" and (
                a.get("name") or "").lower() in ("robots", "googlebot"):
            self.robot_policies.append((a.get("content") or "").lower())
        elif tag == "a":
            link = a.get("href") or ""
            if link.startswith(SITE + "/"):
                self.links.add(link.split("#", 1)[0].split("?", 1)[0])

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False


def exact_owned_url(value, slug):
    if not isinstance(value, str):
        return False
    p = urlsplit(value)
    return (p.scheme == "https" and p.hostname in ALLOWED
            and p.username is None and p.password is None and p.port is None
            and not p.query and not p.fragment and p.path == "/" + slug + "/")


def has_noindex(values):
    return any("noindex" in (v or "").replace(" ", "").split(",")
               for v in values)


def assess_html(slug, body, headers=None):
    """Pure parser. Inspect only what is actually returned, no SEO speculation."""
    if slug not in OWNED:
        raise ValueError("Unexpected XFIT owned target")
    if not isinstance(body, str) or not 100 <= len(body) <= MAX_BYTES:
        raise ValueError("No usable public HTML")
    p = HeadAndLinks()
    p.feed(body)
    headers = headers or {}
    robots_header = headers.get("x-robots-tag", "") or ""
    policies = p.robot_policies + [robots_header.lower()]
    policy = "NOINDEX_DIRECTIVE_OBSERVED" if has_noindex(policies) else "NO_NOINDEX_DIRECTIVE_OBSERVED"
    if not p.canonicals:
        canonical = "NO_CANONICAL_TAG_OBSERVED"
    elif len(p.canonicals) != 1:
        canonical = "MULTIPLE_CANONICAL_TAGS"
    elif exact_owned_url(p.canonicals[0], slug):
        canonical = "SELF_CANONICAL"
    else:
        canonical = "DIFFERENT_OR_UNTRUSTED_CANONICAL"
    return {
        "slug": slug,
        "html_access": "PUBLIC_HTTP_200",
        "robots_meta_or_header": policy,
        "canonical_status": canonical,
        "visible_h1_count": p.h1_count,
        # A link in static HTML, not a Google crawl signal.
        "_internal_links": sorted(p.links),
    }


def read_xfit_path(path, *, max_bytes=MAX_BYTES):
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        raise ValueError("Unexpected XFIT path")
    if any(x in path for x in ("?", "#", "@", "\\")):
        raise ValueError("Untrusted path")
    req = Request(SITE + path, headers={
        "User-Agent": "XFITIndexabilityReadOnly/1.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    with urlopen(req, timeout=25) as response:
        final = urlsplit(response.geturl())
        if (response.status != 200 or final.scheme != "https"
                or final.hostname not in ALLOWED or final.path != path
                or final.query or final.fragment or final.username
                or final.password or final.port):
            raise ValueError("Unexpected HTTP status or redirect")
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError("Oversized public source")
        selected = {name.lower(): response.headers.get(name, "")
                    for name in ("X-Robots-Tag", "Content-Type")}
        return content.decode("utf-8", errors="replace"), selected


def run(*, reader=read_xfit_path):
    pages, internal = [], {}
    for slug in OWNED + REFERERS:
        try:
            body, headers = reader("/" + slug + "/")
            if slug in OWNED:
                row = assess_html(slug, body, headers)
                internal[slug] = row.pop("_internal_links")
                pages.append(row)
            else:
                parser = HeadAndLinks()
                parser.feed(body)
                internal[slug] = sorted(parser.links)
        except (OSError, ValueError, UnicodeError):
            if slug in OWNED:
                pages.append({"slug": slug, "html_access": "UNKNOWN_FETCH",
                              "robots_meta_or_header": "UNKNOWN",
                              "canonical_status": "UNKNOWN",
                              "visible_h1_count": None})
    # Read-only diagnostics. Do not infer sitemap inclusion of any URL.
    infrastructure = {}
    for path, name in (
        ("/robots.txt", "robots_txt"),
        ("/wp-sitemap.xml", "wordpress_sitemap"),
        ("/sitemap_index.xml", "seo_sitemap_index"),
    ):
        try:
            body, headers = reader(path, max_bytes=MAX_BYTES)
            if name == "robots_txt":
                status = "ACCESSIBLE" if "user-agent" in body.casefold() else "UNKNOWN_UNEXPECTED_RESPONSE"
            else:
                status = "ACCESSIBLE_XML" if (
                    "<sitemapindex" in body.casefold() or "<urlset" in body.casefold()
                    or "<ns0:sitemapindex" in body.casefold()
                ) else "UNKNOWN_UNEXPECTED_RESPONSE"
        except (OSError, ValueError, UnicodeError, TypeError):
            status = "UNKNOWN_UNAVAILABLE"
        infrastructure[name] = status
    for page in pages:
        target = SITE + "/" + page["slug"] + "/"
        page["observed_internal_inlinks_from_seven_reviewed_articles"] = sum(
            target in links for links in internal.values())
    return {
        "site": SITE, "mode": "public_read_only",
        "page_count": len(pages), "pages": pages,
        "infrastructure": infrastructure,
        "observed_gsc_state": {
            "five": "DISCOVERED_NOT_INDEXED_2026_11_08",
            "one": "UNKNOWN_TO_GOOGLE_2026_11_08",
            "source_run": 42470121265,
        },
        "limitations": [
            "Public 200 and self-canonical do not prove Google indexing or quality",
            "Sitemap root availability does NOT prove an individual URL is included",
            "Only seven reviewed public articles are sampled for inlinks, not full site graph",
            "UNKNOWN_FETCH is not a 404, noindex or proof of deindexation",
            "Google URL Inspection source remains authoritative for live GSC status",
        ],
        "wordpress_writes": 0, "plugins_installed": 0,
        "external_affiliate_clicks": 0, "seo_mutations": 0,
    }


def main():
    result = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    # This is a diagnostic job; a blocked/unknown page is a real observation,
    # not a failed write or an excuse to misreport indexation.
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_INDEX_PREFLIGHT_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
