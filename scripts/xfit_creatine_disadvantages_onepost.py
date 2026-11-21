"""Source-pinned onepost factual revision of GSC-visible creatine disadvantages.

Legacy editorial source contains unsupported categorical claims about creatine.
Never create a post, change slug/canonical/status, delete a post, or retry a
possibly committed POST. Backup raw body, title and excerpt before the one POST.
Only this exact reviewed post slug is eligible, never the wider archive.
"""
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import (
    PublishError, article_visible, editorial_links, normalized_base,
    normalize_visible, wp_request, verify_public,
)

DOC = Path("content/revisions/creatine-disadvantages-20261121.json")
BACKUP = Path("reports/backups/xfit-creatine-disadvantages-onepost.json")
SLUG = ("kreatin-a-jeho-nevyhody-co-byste-meli-vedet-"
        "nez-ho-zacnete-uzivat-v-fitness")
URL = "https://xfit.cz/" + SLUG + "/"
OLD_TITLE = "Kreatin a jeho nevýhody – co byste měli vědět, než ho začnete užívat v fitness"
NEW_TITLE = "Kreatin a jeho nevýhody: vedlejší účinky podle studií"
EXCERPT = ("Kreatin a jeho nevýhody podle výzkumu: zažívání, voda ve svalech, "
           "ledviny, dehydratace a kdy není důvod doplněk kupovat.")
MARKER = 'data-xfit-revision="creatine-disadvantages-evidence-20261121"'
PRIMARY_SAFETY = "https://xfit.cz/kreatin-a-jeho-vliv-na-ledviny-a-jatra/"
PRIMARY_BUYER = "https://xfit.cz/xfit-os-kreatin-poradce/"
APPROVED_LINKS = (
    PRIMARY_SAFETY, PRIMARY_BUYER,
    "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/",
    "https://www.opss.org/article/creatine-monohydrate-dietary-supplement-performance",
    "https://pubmed.ncbi.nlm.nih.gov/40198156/",
)
LEGACY_CLAIMS = (
    "Kreatin může způsobit dehydrataci",
    "zvýšený krevní tlak",
    "krční křeče",
)
UNSAFE_SOURCE = re.compile(
    r"<!\s*doctype\b|<\s*(?:html|head|body|title|script|iframe|form)\b",
    re.IGNORECASE,
)
UNSAFE_NEW = re.compile(
    r"<\s*(?:script|iframe|form|style)\b|on[a-z]+\s*=",
    re.IGNORECASE,
)


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def reviewed_document():
    data = json.loads(DOC.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema") != 1
            or data.get("mode") != "guarded_existing_post_content_only"
            or data.get("slug") != SLUG or data.get("public_url") != URL
            or data.get("expected_title") != OLD_TITLE):
        raise PublishError("Unapproved editorial target identity")
    raw = data.get("content")
    if (not isinstance(raw, str) or len(raw) < 4000 or len(raw) > 14000
            or MARKER not in raw or UNSAFE_NEW.search(raw)):
        raise PublishError("Incomplete or unsafe reviewed article")
    if raw.count("<h1") or raw.count("<h2") < 6:
        raise PublishError("Updated article must have one WordPress H1 and structured sections")
    if (list(editorial_links(raw)) != list(APPROVED_LINKS[:2]) +
            list(APPROVED_LINKS[2:])):
        raise PublishError("Unreviewed/missing article links or duplicate offer")
    if not all(term in normalize_visible(raw) for term in (
            "není nezbytný", "dehydrataci", "ledvin", "tlak",
            "nemusíte kupovat nic", "neznamená bezpečnost pro každého")):
        raise PublishError("Critical no-buy and safety context missing")
    return raw


def source_get():
    query = urlencode({
        "slug": SLUG, "status": "publish", "context": "edit",
        "_fields": "id,slug,status,link,title,excerpt,content,modified_gmt",
        "per_page": 2,
    })
    return wp_request(normalized_base(), "posts?" + query)


def classify(rows, *, new_body=None):
    if not isinstance(rows, list) or len(rows) != 1:
        raise PublishError("Legacy post missing or duplicate slug")
    item = rows[0]
    if (not isinstance(item, dict) or type(item.get("id")) is not int
            or item["id"] < 1 or item.get("slug") != SLUG
            or item.get("status") != "publish" or item.get("link") != URL):
        raise PublishError("Live article identity/status/canonical mismatch")
    title = (item.get("title") or {}).get("raw")
    raw = (item.get("content") or {}).get("raw")
    excerpt = (item.get("excerpt") or {}).get("raw")
    modified = item.get("modified_gmt")
    if (not isinstance(title, str) or not isinstance(raw, str)
            or not isinstance(excerpt, str) or not isinstance(modified, str)
            or not modified or not (700 <= len(raw) <= 60000)):
        raise PublishError("Missing WordPress edit-context fields")
    if title == NEW_TITLE:
        if (new_body is None or
                article_visible(raw)[0] != article_visible(new_body)[0] or
                editorial_links(raw) != editorial_links(new_body) or
                normalize_visible(excerpt) != normalize_visible(EXCERPT)):
            raise PublishError("Partial or externally modified new article")
        return item, "already_applied"
    if (unescape(title) != OLD_TITLE or UNSAFE_SOURCE.search(raw)
            or not all(phrase.casefold() in unescape(raw).casefold()
                       for phrase in LEGACY_CLAIMS)
            or MARKER in raw or len(raw) > 30000):
        raise PublishError("Source does not match unique reviewed outdated article")
    return item, "update"


def fingerprint(item):
    return {
        "post_id": item["id"], "slug": item["slug"], "url": item["link"],
        "original_raw": item["content"]["raw"],
        "title": item["title"]["raw"], "excerpt": item["excerpt"]["raw"],
        "modified_gmt": item["modified_gmt"],
    }


class Headlines(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1 = []
        self._inside = False
        self._current = []
    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self._inside = True
            self._current = []
    def handle_data(self, text):
        if self._inside:
            self._current.append(text)
    def handle_endtag(self, tag):
        if tag == "h1" and self._inside:
            self._inside = False
            self.h1.append(" ".join("".join(self._current).split()))


def verify_existing_public(*, reader=None):
    if reader is None:
        req = Request(URL, headers={"User-Agent": "XfitCreatineDisadvantagesOnepost/1.0",
                                    "Cache-Control": "no-cache"}, method="GET")
        with urlopen(req, timeout=25) as result:
            final = urlsplit(result.geturl())
            if (result.status != 200 or final.scheme != "https"
                    or final.hostname not in ("xfit.cz", "www.xfit.cz")
                    or final.path != "/" + SLUG + "/" or final.port
                    or final.username or final.password or final.query or final.fragment):
                raise PublishError("Public article origin redirected or changed")
            data = result.read(2_000_001)
            if len(data) > 2_000_000:
                raise PublishError("Public document too large")
            html = data.decode("utf-8", errors="replace")
    else:
        html = reader(URL)
    parsed = Headlines()
    parsed.feed(html)
    return bool(parsed.h1 and parsed.h1[0] == OLD_TITLE and
                all(phrase in html for phrase in ("Kreatin a jeho nevýhody",
                                                   "dehydrataci", "krevní tlak")))



def diagnose_source():
    """Sanitized GET-only identity/content structure; no article text is printed."""
    rows = source_get()
    report = {"state": "GET_ONLY_CREATINE_DISADVANTAGES_STRUCTURE",
              "wordpress_writes": 0, "post_attempts": 0,
              "source_listing_type": "list" if isinstance(rows, list) else "other",
              "matching_wp_rows": len(rows) if isinstance(rows, list) else None}
    if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict):
        p = rows[0]
        title = (p.get("title") or {}).get("raw")
        raw = (p.get("content") or {}).get("raw")
        excerpt = (p.get("excerpt") or {}).get("raw")
        report.update({
            "post_id": p.get("id") if type(p.get("id")) is int else None,
            "slug_exact": p.get("slug") == SLUG,
            "status_published": p.get("status") == "publish",
            "canonical_url_exact": p.get("link") == URL,
            "raw_title_is_old": isinstance(title, str) and unescape(title) == OLD_TITLE,
            "raw_title_is_new": title == NEW_TITLE,
            "title_raw_length": len(title) if isinstance(title, str) else None,
            "title_expected_length": len(OLD_TITLE),
            "raw_body_length": len(raw) if isinstance(raw, str) else None,
            "excerpt_is_text": isinstance(excerpt, str),
            "modified_gmt_present": bool(p.get("modified_gmt")),
            "source_full_document_marker": bool(UNSAFE_SOURCE.search(raw)) if isinstance(raw, str) else None,
            "reviewed_claims": [
                bool(claim.casefold() in unescape(raw).casefold())
                for claim in LEGACY_CLAIMS
            ] if isinstance(raw, str) else None,
            "new_revision_marker_present": MARKER in raw if isinstance(raw, str) else None,
            "raw_sha256": sha(raw) if isinstance(raw, str) else None,
            "source_heading_counts": {
                "h1": len(re.findall(r"<h1\\b", raw, flags=re.I)),
                "h2": len(re.findall(r"<h2\\b", raw, flags=re.I)),
                "title": len(re.findall(r"<title\\b", raw, flags=re.I)),
                "html": len(re.findall(r"<html\\b", raw, flags=re.I)),
            } if isinstance(raw, str) else None,
        })
    print(json.dumps(report, ensure_ascii=False))

def snapshot():
    new_body = reviewed_document()
    post, mode = classify(source_get(), new_body=new_body)
    if mode == "update" and not verify_existing_public():
        raise PublishError("Target public article is not same reviewed legacy page")
    if BACKUP.exists():
        raise PublishError("Existing prewrite backup cannot be overwritten")
    before = fingerprint(post)
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "mode": mode, "prewrite": before,
        "original_hash": sha(before["original_raw"]),
        "replacement_hash": sha(new_body), "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY_NO_WRITE", "mode": mode,
                      "post_id": post["id"], "remote_writes": 0}))


def validate_public_release(*, reader=None):
    if reader is not None:
        html = reader(URL)
        h1 = Headlines()
        h1.feed(html)
        if h1.h1 != [NEW_TITLE] or MARKER not in html:
            raise PublishError("Public new title or revision marker not verified")
        return True
    return verify_public(URL, NEW_TITLE, reviewed_document())


def apply():
    if not BACKUP.is_file():
        raise PublishError("Mandatory rollback backup missing")
    doc = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (doc.get("schema") != 1 or doc.get("mode") not in ("update", "already_applied")
            or doc.get("remote_writes") != 0):
        raise PublishError("Unexpected rollback contract")
    before = doc.get("prewrite") or {}
    if (before.get("slug") != SLUG or before.get("url") != URL
            or type(before.get("post_id")) is not int
            or not isinstance(before.get("original_raw"), str)
            or sha(before["original_raw"]) != doc.get("original_hash")):
        raise PublishError("Invalid prewrite backup identity")
    approved = reviewed_document()
    if sha(approved) != doc.get("replacement_hash"):
        raise PublishError("Reviewed content changed after snapshot")
    current, mode = classify(source_get(), new_body=approved)
    if fingerprint(current) != before or mode != doc.get("mode"):
        raise PublishError("WordPress source changed between backup and write")
    if mode == "already_applied":
        validate_public_release()
        print(json.dumps({"state": "ALREADY_LIVE_NO_WRITE", "post_id": current["id"],
                          "posts_changed": 0, "post_attempts": 0}))
        return
    # At most one POST; a timeout or invalid response may already have committed.
    try:
        wp_request(normalized_base(), "posts/" + str(current["id"]), payload={
            "title": NEW_TITLE, "content": approved, "excerpt": EXCERPT,
        })
    except (PublishError, OSError, ValueError, TypeError):
        pass  # Only GET reconciliation is allowed, never a second POST.
    try:
        final, final_mode = classify(source_get(), new_body=approved)
    except (PublishError, OSError, ValueError, TypeError) as exc:
        raise PublishError("POST result uncertain; no automatic retry") from exc
    if final["id"] != current["id"] or final_mode != "already_applied":
        raise PublishError("WordPress revision not proven by source GET; no retry")
    validate_public_release()
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": current["id"],
                      "posts_changed": 1, "post_attempts": 1,
                      "new_posts": 0, "redirects": 0, "url": URL}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply", "diagnose"):
            raise PublishError("Usage snapshot|apply|diagnose")
        (snapshot if sys.argv[1] == "snapshot" else
         diagnose_source if sys.argv[1] == "diagnose" else apply)()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_CREATINE_DISADVANTAGES_ERROR: " + type(exc).__name__ +
              ("_SOURCE_GUARD" if isinstance(exc, PublishError) else "_OTHER"), file=sys.stderr)
        sys.exit(2)
