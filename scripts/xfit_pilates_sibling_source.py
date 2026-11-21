"""One read-only source audit of the GSC-visible supporting Pilates page.

The page received 41 impressions, zero Google clicks in Prometheus' finalized
2026-10-21..2026-11-17 XFIT baseline. Read its authenticated WordPress source
and current public document before considering any context-sensitive inlink.
Never print raw content, author identities, credentials, or affiliate URLs.
"""
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlencode

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_pilates_gsc_preflight import canonical_path, read_public, parse_public
from scripts.xfit_pilates_gsc_title_release import SLUG as PRIMARY_SLUG

SLUG = ("pilates-vs-klasicke-cviceni-jake-jsou-hlavni-rozdily-a-"
        "ktere-cviceni-je-pro-vas-lepsi")
URL = "https://xfit.cz/" + SLUG + "/"
PRIMARY = "https://xfit.cz/" + PRIMARY_SLUG + "/"
MAX_RAW_BYTES = 250_000
DANGEROUS_EMBED = re.compile(
    r"<!doctype\b|<html\b|<head\b|<title\b|<link\b[^>]*\bcanonical\b",
    re.I,
)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.head = 0
        self.body = 0
        self.head_title_count = 0
        self.body_title_count = 0
        self.h2_count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.head += 1
        elif tag == "body":
            self.body += 1
        elif tag == "title":
            if self.head:
                self.head_title_count += 1
            else:
                self.body_title_count += 1
        elif tag == "h2":
            self.h2_count += 1

    def handle_endtag(self, tag):
        if tag == "head" and self.head:
            self.head -= 1
        if tag == "body" and self.body:
            self.body -= 1


def source_get():
    # Slug lookup only; exact identity and cardinality still required below.
    query = urlencode({
        "slug": SLUG, "status": "publish", "context": "edit",
        "_fields": "id,slug,status,link,title,content,modified_gmt",
        "per_page": 2,
    })
    return wp_request(normalized_base(), "posts?" + query)


def source_assess(rows):
    if not isinstance(rows, list) or len(rows) != 1:
        raise PublishError("Supporting Pilates source is missing or ambiguous")
    post = rows[0]
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] <= 0 or post.get("slug") != SLUG
            or post.get("status") != "publish"
            or not canonical_path(post.get("link"), SLUG)):
        raise PublishError("Supporting Pilates source identity mismatch")
    title = (post.get("title") or {}).get("raw")
    raw = (post.get("content") or {}).get("raw")
    modified = post.get("modified_gmt")
    if (not isinstance(title, str) or "pilates" not in unescape(title).casefold()
            or not isinstance(raw, str) or len(raw) < 500
            or len(raw.encode("utf-8")) > MAX_RAW_BYTES
            or not isinstance(modified, str) or not modified):
        raise PublishError("Supporting Pilates source unavailable or unsafe")
    signals = parse_public(SLUG, raw)
    embedded = bool(DANGEROUS_EMBED.search(raw))
    # Diagnostic counts only. No raw HTML, hidden offer URLs, IDs, user data
    # or secret-like query parameters are emitted to public issue receipts.
    structure = {
        name: len(re.findall(pattern, raw, flags=re.I))
        for name, pattern in (
            ("doctype", r"<!\s*doctype\b"),
            ("html_start", r"<\s*html\b"),
            ("head_start", r"<\s*head\b"),
            ("body_start", r"<\s*body\b"),
            ("title_start", r"<\s*title\b"),
            ("title_end", r"</\s*title\s*>"),
            ("body_canonical", r"<\s*link\b[^>]*\bcanonical\b"),
            ("script_start", r"<\s*script\b"),
            ("style_start", r"<\s*style\b"),
            ("h2_start", r"<\s*h2\b"),
            ("paragraph_start", r"<\s*p(?:\s|>)"),
        )
    }
    first_doctype = re.search(r"<!\s*doctype\b[^>]*>", raw, re.I)
    closing_html = list(re.finditer(r"</\s*html\s*>", raw, re.I))
    if first_doctype and len(closing_html) == 1:
        before = raw[:first_doctype.start()]
        after = raw[closing_html[0].end():]
        only_comments = lambda text: bool(re.fullmatch(
            r"(?:\s|<!--.*?-->)*", text, flags=re.S
        ))
        shell_boundaries = {
            "prefix_chars": len(before),
            "suffix_chars": len(after),
            "prefix_only_whitespace_or_html_comments": only_comments(before),
            "suffix_only_whitespace_or_html_comments": only_comments(after),
            "starts_immediately_with_doctype": not before.strip(),
            "ends_immediately_after_html": not after.strip(),
            "html_closing_tag_count": 1,
        }
    else:
        shell_boundaries = {
            "prefix_chars": None,
            "suffix_chars": None,
            "prefix_only_whitespace_or_html_comments": False,
            "suffix_only_whitespace_or_html_comments": False,
            "html_closing_tag_count": len(closing_html),
        }
    return {
        "post_id": post["id"],
        "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "modified_gmt": modified,
        "raw_length": len(raw),
        "title_contains_pilates": True,
        "raw_embedded_complete_document_markers": embedded,
        "source_structure": structure,
        "shell_boundaries": shell_boundaries,
        "raw_contains_power_pilates": "power pilates" in unescape(raw).casefold(),
        "source_h1_count": len(signals["h1"]),
        "source_link_to_primary": signals["links_to_primary"],
    }


def evidence(*, authenticated_reader=source_get, public_reader=read_public):
    source = source_assess(authenticated_reader())
    body, robots_header = public_reader(SLUG)
    public = parse_public(SLUG, body, robot_header=robots_header)
    parsed = Structure()
    parsed.feed(body)
    issue = (
        source["raw_embedded_complete_document_markers"] or
        parsed.head_title_count != 1 or parsed.body_title_count > 0 or
        public["canonical"] != "SELF_CANONICAL" or
        public["robots"] != "NO_NOINDEX_OBSERVED" or
        len(public["h1"]) != 1
    )
    state = (
        "HOLD_LEGACY_MARKUP_REVIEW" if issue else
        "ALREADY_LINKED_NO_WRITE" if source["source_link_to_primary"]
        else "SOURCE_VERIFIED_LINK_REVIEW_CANDIDATE"
    )
    return {
        "state": state,
        "source": source,
        "public": {
            "canonical": public["canonical"],
            "robots": public["robots"],
            "h1_count": len(public["h1"]),
            "head_title_tag_count": parsed.head_title_count,
            "body_title_tag_count": parsed.body_title_count,
            "links_to_primary": public["links_to_primary"],
        },
        "gsc_evidence": "41 impressions, 0 clicks, 2026-10-21..2026-11-17",
        "wordpress_post_attempts": 0,
        "release_permitted": False,
        "note": "Source eligibility alone is NOT editorial or publication approval.",
    }


def main():
    try:
        print(json.dumps(evidence(), ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, PublishError, KeyError, TypeError, AttributeError):
        print(json.dumps({
            "state": "READ_ONLY_SIBLING_SOURCE_INCOMPLETE",
            "wordpress_post_attempts": 0,
            "release_permitted": False,
        }))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
