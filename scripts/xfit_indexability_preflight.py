#!/usr/bin/env python3
"""Bounded public XFIT technical indexability preflight for six GSC-flagged guides.

This is NOT a Google indexation decision. No credentials, WP writes, plugins,
indexing API requests, ranking claims, affiliate clicks or tracking requests.
Only exact xfit.cz public pages, robots.txt, and two sitemap entrypoints.
"""
import json
import sys
from xml.etree import ElementTree
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler

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


class NoRedirect(HTTPRedirectHandler):
    """Never request a second host or path when public endpoints redirect."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def sitemap_fetch_failure(exc):
    """Public, redacted diagnostic classification; never expose exception URLs."""
    if isinstance(exc, HTTPError):
        if exc.code in (301, 302, 303, 307, 308):
            return "HTTP_REDIRECT_" + str(exc.code)
        if exc.code in (400, 401, 403, 404, 405, 410, 429, 500, 502, 503, 504):
            return "HTTP_" + str(exc.code)
        return "HTTP_OTHER"
    return "UNKNOWN_UNAVAILABLE"


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
    with build_opener(NoRedirect()).open(req, timeout=25) as response:
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



def _xml_locs(body, root_type):
    """Read only bounded XML; reject DTD/entities and non-sitemap documents."""
    if (not isinstance(body, str) or len(body.encode("utf-8")) > MAX_BYTES
            or "<!DOCTYPE" in body.upper() or "<!ENTITY" in body.upper()):
        return None
    try:
        tree = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return None
    if tree.tag.rsplit("}", 1)[-1] != root_type:
        return None
    return [(el.text or "").strip() for el in tree.iter()
            if el.tag.rsplit("}", 1)[-1] == "loc"]


def _safe_post_sitemap_child(url):
    if not isinstance(url, str):
        return None
    try:
        p = urlsplit(url)
    except ValueError:
        return None
    if (p.scheme != "https" or p.netloc != "xfit.cz"
            or p.username or p.password or p.port is not None
            or p.query or p.fragment):
        return None
    if not re.fullmatch(r"/wp-sitemap-posts-post-[0-9]{1,4}\.xml", p.path):
        return None
    return p.path


def post_sitemap_inclusion(root_body, *, reader, max_children=20):
    """Check only exact first-level XFIT post maps, never outbound URLs."""
    empty = {slug: "UNKNOWN_NOT_PROVEN" for slug in OWNED}
    root_locs = _xml_locs(root_body, "sitemapindex")
    if root_locs is None:
        return {"state": "ROOT_NOT_PARSEABLE_INDEX", "post_maps_declared": 0,
                "post_maps_checked": 0, "post_maps_failed": 0,
                "unsafe_or_irrelevant_locs_ignored": 0, "per_slug": empty}
    candidates = sorted(set(filter(None, (_safe_post_sitemap_child(x)
                                           for x in root_locs))))
    ignored = len(root_locs) - len(candidates)
    seen = set()
    checked = 0
    failed = 0
    for path in candidates[:max_children]:
        try:
            child, _ = reader(path, max_bytes=MAX_BYTES)
            locs = _xml_locs(child, "urlset")
            if locs is None:
                failed += 1
                continue
            checked += 1
            for slug in OWNED:
                if SITE + "/" + slug + "/" in locs:
                    seen.add(slug)
        except (OSError, ValueError, UnicodeError, TypeError):
            failed += 1
    complete = (len(candidates) > 0 and
                len(candidates) <= max_children and failed == 0 and
                checked == len(candidates))
    state = ("ALL_POST_MAPS_READ" if complete else
             "PARTIAL_OR_NO_POST_MAPS_READ")
    return {
        "state": state,
        "post_maps_declared": len(candidates),
        "post_maps_checked": checked,
        "post_maps_failed": failed,
        "unsafe_or_irrelevant_locs_ignored": max(0, ignored),
        "per_slug": {
            slug: ("INCLUDED_IN_POST_SITEMAP" if slug in seen else
                   "NOT_OBSERVED_IN_ALL_POST_MAPS" if complete else
                   "UNKNOWN_NOT_PROVEN")
            for slug in OWNED
        },
    }


def robots_evidence(body):
    """Return only bounded same-origin sitemap paths and observed root disallow."""
    if not isinstance(body, str) or len(body) > 500000:
        raise ValueError("Unexpected robots text")
    declared = set()
    agents = set()
    root_disallow = False
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            if value.lower() in ("*", "googlebot"):
                agents.add(value.lower())
            else:
                agents.clear()
        elif key == "disallow" and value == "/" and agents:
            root_disallow = True
        elif key == "sitemap" and len(declared) < 2:
            parsed = urlsplit(value)
            if (parsed.scheme == "https" and parsed.hostname == "xfit.cz"
                    and not parsed.username and not parsed.password
                    and parsed.port is None and not parsed.query and not parsed.fragment
                    and re.fullmatch(r"/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*\.xml", parsed.path)):
                declared.add(parsed.path)
    return {
        "safe_same_origin_sitemap_paths": sorted(declared),
        "observed_general_or_googlebot_root_disallow": root_disallow,
    }


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
    wp_sitemap_root = None
    robots_details = {"safe_same_origin_sitemap_paths": [],
                      "observed_general_or_googlebot_root_disallow": None}
    for path, name in (
        ("/robots.txt", "robots_txt"),
        ("/wp-sitemap.xml", "wordpress_sitemap"),
        ("/sitemap_index.xml", "seo_sitemap_index"),
        ("/sitemap.xml", "generic_sitemap"),
    ):
        try:
            body, headers = reader(path, max_bytes=MAX_BYTES)
            if name == "robots_txt":
                status = "ACCESSIBLE" if "user-agent" in body.casefold() else "UNKNOWN_UNEXPECTED_RESPONSE"
                robots_details = robots_evidence(body)
            else:
                status = "ACCESSIBLE_XML" if (
                    "<sitemapindex" in body.casefold() or "<urlset" in body.casefold()
                    or "<ns0:sitemapindex" in body.casefold()
                ) else "UNKNOWN_UNEXPECTED_RESPONSE"
                if name == "wordpress_sitemap" and status == "ACCESSIBLE_XML":
                    wp_sitemap_root = body
        except (OSError, ValueError, UnicodeError, TypeError) as exc:
            status = sitemap_fetch_failure(exc)
        infrastructure[name] = status
    declared_status = {}
    # Only verified exact same-origin XML paths from the public robots file.
    for path in robots_details["safe_same_origin_sitemap_paths"]:
        if path in ("/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml"):
            # Previous GET already determined the exact status.
            existing = {
                "/wp-sitemap.xml": "wordpress_sitemap",
                "/sitemap_index.xml": "seo_sitemap_index",
                "/sitemap.xml": "generic_sitemap",
            }[path]
            declared_status[path] = infrastructure[existing]
            continue
        try:
            body, _ = reader(path, max_bytes=MAX_BYTES)
            declared_status[path] = "ACCESSIBLE_XML" if (
                "<sitemapindex" in body.casefold() or "<urlset" in body.casefold()
            ) else "UNKNOWN_UNEXPECTED_RESPONSE"
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            declared_status[path] = sitemap_fetch_failure(exc)
    child_membership = post_sitemap_inclusion(wp_sitemap_root, reader=reader)
    for page in pages:
        target = SITE + "/" + page["slug"] + "/"
        page["observed_internal_inlinks_from_seven_reviewed_articles"] = sum(
            target in links for links in internal.values())
    return {
        "site": SITE, "mode": "public_read_only",
        "page_count": len(pages), "pages": pages,
        "infrastructure": infrastructure,
        "robots_details": robots_details,
        "declared_sitemap_probes": declared_status,
        "post_sitemap_inclusion": child_membership,
        "observed_gsc_state": {
            "five": "DISCOVERED_NOT_INDEXED_2026_11_08",
            "one": "UNKNOWN_TO_GOOGLE_2026_11_08",
            "source_run": 42470121265,
        },
        "limitations": [
            "Public 200 and self-canonical do not prove Google indexing or quality",
            "Sitemap root availability does NOT prove an individual URL is included",
            "Sitemap XML membership is not proof of Google discovery or indexation",
            "NOT_OBSERVED means only that a bounded current public post map lacked a URL",
            "Root Disallow observation alone needs complete robots precedence interpretation",
            "Only seven reviewed public articles are sampled for inlinks, not full site graph",
            "UNKNOWN_FETCH is not a 404, noindex or proof of deindexation",
            "HTTP_4XX/5XX is the exact observed status at probe time, not persistent absence",
            "HTTP_REDIRECT_3XX is a no-follow redirect observation; target was not fetched",
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
