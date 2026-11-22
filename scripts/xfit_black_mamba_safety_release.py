"""Evidence-led single existing WordPress Black Mamba correction.

No generic product recommendations or commissions. Discover exact unique slug
under authenticated WP REST; freeze the ID and original HTML in immutable
rollback; CAS guard before one possible POST; auth + public readback; no retry
on uncertain POST. Original title and featured media remain untouched.
"""
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from scripts.wp_publish import (
    PublishError, normalized_base, wp_request, verify_public,
    article_visible, editorial_links,
)
from scripts.xfit_coupon_cleanup import sha
from scripts.xfit_editorial_gate import check_document, EditorialError

SLUG = "black-mamba-co-to-je"
URL = "https://xfit.cz/" + SLUG + "/"
SOURCE = Path("content/revisions/black-mamba-evidence-20261122.html")
BACKUP = Path("reports/backups/xfit-black-mamba-before-20261122.json")
FIELDS = "id,slug,status,link,title,modified_gmt,content,featured_media"
OLD_SIGNATURES = (
    "sida cordifolia",
    "bezpečné pro tělo",
    "nezpůsobují vedlejší účinky",
    "zrychluje metabolismus o 22",
)
NEW_MARKERS = (
    "rychlá odpověď:",
    "co je black mamba a proč nestačí název produktu",
    "stimulanty, kofein a synefrin",
    "těhotenství a kojení",
    "zdroje a redakční metodika",
    "aktualizace 22. 11. 2026",
)
EVIDENCE_URLS = (
    "https://ods.od.nih.gov/factsheets/WeightLoss-HealthProfessional/",
    "https://www.nccih.nih.gov/health/tips/tips-know-the-facts-about-supplements-marketed-for-weight-loss",
    "https://ods.od.nih.gov/factsheets/Pregnancy-HealthProfessional/",
)
INTERNAL_URLS = (
    "https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",
    "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
)


def visible(text):
    if not isinstance(text, str):
        return ""
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", text)).split()).casefold()


def revised(body):
    if not isinstance(body, str):
        return False
    norm = visible(body)
    return (
        len(body.encode("utf-8")) >= 4500
        and all(term in norm for term in NEW_MARKERS)
        and all(body.count(link) == 1 for link in EVIDENCE_URLS + INTERNAL_URLS)
        and "us-supplements.to" not in body.casefold()
        and "5nm2022" not in norm
        and not re.search(
            r"<\s*(?:html|head|body|base|meta|script|iframe|form)\b|"
            r"\bon(?:click|error|load|submit)\s*=", body, re.I,
        )
    )


def reviewed_body():
    body = SOURCE.read_text(encoding="utf-8")
    if not revised(body):
        raise PublishError("Black Mamba revision does not match reviewed evidence")
    try:
        inspection = check_document({"content": body}, commercial=False)
    except EditorialError as exc:
        raise PublishError("Black Mamba editorial quality gate failed") from exc
    if inspection["word_count"] < 700 or inspection["h2_count"] < 6:
        raise PublishError("Black Mamba safety revision lacks substantial value")
    return body


def source_identity(post, *, expected_id=None):
    if (not isinstance(post, dict)
            or type(post.get("id")) is not int or post["id"] <= 0
            or post.get("slug") != SLUG or post.get("status") != "publish"
            or post.get("link") != URL
            or (expected_id is not None and post["id"] != expected_id)):
        raise PublishError("Pinned Black Mamba article identity has changed")
    parsed = urlsplit(post["link"])
    if (parsed.scheme != "https" or parsed.netloc != "xfit.cz"
            or parsed.query or parsed.fragment or parsed.username
            or parsed.password or parsed.port is not None):
        raise PublishError("Unsafe Black Mamba canonical URL")
    raw = (post.get("content") or {}).get("raw")
    title = (post.get("title") or {}).get("raw")
    modified = post.get("modified_gmt")
    featured = post.get("featured_media")
    if (not isinstance(raw, str) or not 950 <= len(raw.encode("utf-8")) <= 500000
            or not isinstance(title, str)
            or "black mamba" not in title.casefold()
            or "co to je" not in title.casefold()
            or not isinstance(modified, str)
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", modified)
            or type(featured) is not int):
        raise PublishError("Missing or altered edit-context original metadata")
    return raw, title, modified, featured


def source_state(post, *, expected_id=None):
    raw, title, modified, featured = source_identity(
        post, expected_id=expected_id
    )
    if revised(raw):
        return "already_revised", raw, title, modified, featured
    content = visible(raw)
    if not all(value in content for value in OLD_SIGNATURES):
        raise PublishError("Old dangerous Black Mamba source signature drifted")
    if not any("us-supplements.to" in u for u in editorial_links(raw)):
        raise PublishError("Expected old unverified product merchant link absent")
    return "needs_revision", raw, title, modified, featured


def discover():
    result = wp_request(normalized_base(), (
        "posts?slug=" + SLUG
        + "&context=edit&status=any&per_page=10&_fields=" + FIELDS
    ))
    if not isinstance(result, list) or len(result) != 1:
        raise PublishError("Expected exactly one published Black Mamba WP article")
    source_identity(result[0])
    return result[0]


def remote(post_id):
    if type(post_id) is not int or post_id <= 0:
        raise PublishError("Invalid exact frozen Black Mamba post ID")
    result = wp_request(
        normalized_base(), f"posts/{post_id}?context=edit&_fields={FIELDS}"
    )
    source_identity(result, expected_id=post_id)
    return result


def snapshot():
    body = reviewed_body()
    post = discover()
    state, raw, title, modified, featured = source_state(post)
    if BACKUP.exists():
        raise PublishError("Immutable Black Mamba rollback already exists")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1,
        "post_id": post["id"], "slug": SLUG, "url": URL,
        "mode": state, "original_raw": raw, "original_title": title,
        "original_sha256": sha(raw), "original_title_sha256": sha(title),
        "modified_gmt": modified, "featured_media": featured,
        "revised_sha256": sha(body), "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "BLACK_MAMBA_ROLLBACK_READY",
        "post_id": post["id"], "needs_write": state == "needs_revision",
        "remote_writes": 0,
    }))


def deploy():
    if not BACKUP.is_file():
        raise PublishError("Missing pre-uploaded complete original rollback")
    record = json.loads(BACKUP.read_text(encoding="utf-8"))
    body = reviewed_body()
    if (not isinstance(record, dict) or record.get("schema") != 1
            or type(record.get("post_id")) is not int
            or record.get("slug") != SLUG or record.get("url") != URL
            or record.get("remote_writes") != 0
            or record.get("revised_sha256") != sha(body)):
        raise PublishError("Black Mamba rollback identity or revision drift")
    post_id = record["post_id"]
    state, raw, title, modified, featured = source_state(
        remote(post_id), expected_id=post_id
    )
    if (state != record.get("mode")
            or raw != record.get("original_raw")
            or title != record.get("original_title")
            or sha(raw) != record.get("original_sha256")
            or sha(title) != record.get("original_title_sha256")
            or modified != record.get("modified_gmt")
            or featured != record.get("featured_media")):
        raise PublishError("Concurrent edit since backup; zero WordPress POSTs")
    if state == "already_revised":
        # Do not overwrite another editor's already-repaired article.
        verify_public(URL, title, body)
        print(json.dumps({
            "state": "ALREADY_VERIFIED_NO_WRITE", "post_id": post_id,
            "post_attempts": 0, "posts_changed": 0,
        }))
        return
    uncertain = False
    try:
        response = wp_request(
            normalized_base(), f"posts/{post_id}", payload={"content": body}
        )
        uncertain = (not isinstance(response, dict)
                     or response.get("id") != post_id
                     or response.get("status") != "publish")
    except (PublishError, OSError, ValueError, TypeError):
        uncertain = True
    # Never retry an unclear POST. Re-read before calling any write successful.
    try:
        after = remote(post_id)
        current, current_title, _, current_featured = source_identity(
            after, expected_id=post_id
        )
    except (PublishError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "state": "UNKNOWN_NO_RETRY", "post_id": post_id,
            "post_attempts": 1,
        }))
        raise PublishError("Black Mamba post-write auth readback unavailable") from exc
    expected_text, _ = article_visible(body)
    actual_text, _ = article_visible(current)
    if (not revised(current) or expected_text != actual_text
            or editorial_links(body) != editorial_links(current)
            or current_title != title or current_featured != featured):
        print(json.dumps({
            "state": "AUTH_READBACK_MISMATCH_NO_RETRY",
            "post_id": post_id, "post_attempts": 1,
        }))
        raise PublishError("Black Mamba auth readback did not match reviewed article")
    verify_public(URL, title, body)
    print(json.dumps({
        "state": "PUBLIC_VERIFIED",
        "post_id": post_id, "url": URL,
        "post_attempts": 1, "posts_changed": 1,
        "public_site_modified": True, "old_merchant_link_removed": True,
        "new_posts": 0, "deletes": 0, "redirects": 0,
        "write_response_uncertain": uncertain,
    }))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "deploy"):
            raise PublishError("Usage: snapshot|deploy")
        (snapshot if sys.argv[1] == "snapshot" else deploy)()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_BLACK_MAMBA_RELEASE_ERROR: " + type(exc).__name__,
              file=sys.stderr)
        raise SystemExit(2)
