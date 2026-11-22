"""Single legacy creatine safety editorial rescue, 100% source-backed and rollback-first.

No post creation, no health form, no external affiliate click, no redirect,
no retry on ambiguous write. The owner-published legacy source must still
contain the *observed* duplicated 2022 coupon content before a write.
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

POST_ID = 2212
SLUG = "bezpecnostni-aspekty-kreatinu-monohydratu-a-jak-minimalizovat-rizika"
URL = "https://xfit.cz/" + SLUG + "/"
SOURCE = Path("content/revisions/creatine-safety-2212-evidence.html")
BACKUP = Path("reports/backups/xfit-creatine-safety-2212-original.json")
FIELDS = "id,slug,status,link,title,modified_gmt,content,featured_media"
REVISED_MARKERS = (
    "Rychlá odpověď:",
    "Ledviny a kreatinin:",
    "Dehydratace, křeče a změna hmotnosti",
    "Kdo by měl rozhodnutí probrat",
    "aktualizováno 22. 11. 2026",
)
REQUIRED_EVIDENCE_URLS = (
    "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC5469049/",
    "https://pubmed.ncbi.nlm.nih.gov/42035842/",
)
OWNED_HANDOFFS = (
    "https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",
    "https://xfit.cz/kreatin-a-jeho-vliv-na-ledviny-a-jatra/",
    "https://xfit.cz/xfit-os-kreatin-poradce/",
)


def visible(text):
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", text or "")).split()).casefold()


def revised(body):
    if not isinstance(body, str):
        return False
    norm = visible(body)
    return (
        len(body.encode("utf-8")) >= 6000
        and all(word.casefold() in norm for word in REVISED_MARKERS)
        and "5nm2022" not in norm
        and all(body.count(url) == 1 for url in REQUIRED_EVIDENCE_URLS)
        and all(body.count(url) == 1 for url in OWNED_HANDOFFS)
        and not re.search(
            r"<\s*(?:html|head|body|script|iframe|form|meta|base)\b|"
            r"\bon(?:click|load|error|submit)\s*=", body, re.I,
        )
    )


def reviewed_body():
    body = SOURCE.read_text(encoding="utf-8")
    if not revised(body):
        raise PublishError("Reviewed creatine safety revision failed source bounds")
    try:
        quality = check_document({"content": body}, commercial=False)
    except EditorialError as exc:
        raise PublishError("Creatine safety editorial gate blocked release") from exc
    if quality["word_count"] < 700 or quality["h2_count"] < 6:
        raise PublishError("Creatine safety revision needs substantive answer")
    return body


def pinned(post):
    if (not isinstance(post, dict)
            or type(post.get("id")) is not int or post["id"] != POST_ID
            or post.get("slug") != SLUG or post.get("status") != "publish"
            or post.get("link") != URL):
        raise PublishError("Pinned creatine safety WP ID/slug/status changed")
    address = urlsplit(post["link"])
    if (address.scheme != "https" or address.netloc != "xfit.cz"
            or address.username or address.password or address.port
            or address.query or address.fragment):
        raise PublishError("Unexpected canonical source identity")
    raw = (post.get("content") or {}).get("raw")
    title = (post.get("title") or {}).get("raw")
    modified = post.get("modified_gmt")
    featured = post.get("featured_media")
    if (not isinstance(raw, str) or not 4000 <= len(raw.encode("utf-8")) <= 500000
            or not isinstance(title, str) or len(title) > 220
            or "bezpečnostní aspekty kreatinu monohydrátu" not in visible(title)
            or not isinstance(modified, str)
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", modified)
            or type(featured) is not int):
        raise PublishError("Incomplete editable legacy source metadata")
    return raw, title, modified, featured


def source_state(post):
    raw, title, modified, featured = pinned(post)
    if revised(raw):
        return "already_revised", raw, title, modified, featured
    norm = visible(raw)
    if (norm.count("5nm2022") < 2
            or norm.count("bezpečnostní aspekty kreatinu monohydrátu") < 2
            or "minimalizovat rizika" not in norm):
        raise PublishError("Old unsupported/duplicated page signature changed")
    return "needs_revision", raw, title, modified, featured


def remote():
    result = wp_request(
        normalized_base(), f"posts/{POST_ID}?context=edit&_fields={FIELDS}"
    )
    pinned(result)
    return result


def snapshot():
    proposal = reviewed_body()
    state, raw, title, modified, featured = source_state(remote())
    if BACKUP.exists():
        raise PublishError("Prewrite rollback artifact must never be overwritten")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG, "url": URL,
        "mode": state, "original_raw": raw, "original_title": title,
        "original_sha256": sha(raw), "modified_gmt": modified,
        "featured_media": featured, "after_sha256": sha(proposal),
        "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "SAFETY_2212_BACKUP_READY", "post_id": POST_ID,
        "needs_post": state == "needs_revision", "remote_writes": 0,
    }))


def deploy():
    if not BACKUP.is_file():
        raise PublishError("Mandatory immutable rollback artifact is missing")
    record = json.loads(BACKUP.read_text(encoding="utf-8"))
    proposal = reviewed_body()
    state, raw, title, modified, featured = source_state(remote())
    if (record.get("schema") != 1 or record.get("post_id") != POST_ID
            or record.get("slug") != SLUG or record.get("url") != URL
            or record.get("remote_writes") != 0
            or record.get("mode") != state
            or record.get("original_raw") != raw
            or record.get("original_title") != title
            or record.get("original_sha256") != sha(raw)
            or record.get("modified_gmt") != modified
            or record.get("featured_media") != featured
            or record.get("after_sha256") != sha(proposal)):
        raise PublishError("Concurrent WordPress editor changed source since snapshot")
    if state == "already_revised":
        if not revised(raw):
            raise PublishError("Already-revised state no longer verified")
        verify_public(URL, title, proposal)
        print(json.dumps({
            "state": "ALREADY_VERIFIED_NO_WRITE",
            "post_id": POST_ID, "post_attempts": 0, "posts_changed": 0,
        }))
        return
    uncertain = False
    try:
        response = wp_request(
            normalized_base(), f"posts/{POST_ID}", payload={"content": proposal}
        )
        if (not isinstance(response, dict) or response.get("id") != POST_ID
                or response.get("status") != "publish"):
            uncertain = True
    except (PublishError, OSError, ValueError, TypeError):
        uncertain = True

    # No retry, ever. An ambiguous POST may already have been committed.
    try:
        after = remote()
        actual, actual_title, _, actual_featured = pinned(after)
    except (PublishError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "state": "UNKNOWN_NO_RETRY", "post_id": POST_ID, "post_attempts": 1,
        }))
        raise PublishError("Post-write authenticated readback unavailable") from exc
    before_expected, _ = article_visible(proposal)
    after_visible, _ = article_visible(actual)
    if (not revised(actual) or before_expected != after_visible
            or editorial_links(proposal) != editorial_links(actual)
            or actual_title != title or actual_featured != featured):
        print(json.dumps({
            "state": "AUTH_READBACK_NOT_MATCHED_NO_RETRY",
            "post_id": POST_ID, "post_attempts": 1,
        }))
        raise PublishError("WordPress content or identity differs after single POST")
    verify_public(URL, title, proposal)
    print(json.dumps({
        "state": "PUBLIC_VERIFIED", "post_id": POST_ID,
        "url": URL, "post_attempts": 1, "posts_changed": 1,
        "new_posts": 0, "deletes": 0, "redirects": 0,
        "2022_coupon_removed": True, "public_site_modified": True,
        "write_response_uncertain": uncertain,
    }))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "deploy"):
            raise PublishError("Usage: snapshot|deploy")
        (snapshot if sys.argv[1] == "snapshot" else deploy)()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_CREATINE_SAFETY_2212_ERROR: " + type(exc).__name__,
              file=sys.stderr)
        raise SystemExit(2)
