"""Fail-closed, one-POST rescue of damaged legacy creatine post #10953.

The exact current authenticated source and public source must agree before a
single content-only POST. A mandatory rollback snapshot is stored as an Actions
artifact before the write. Unknown results never trigger another POST.
"""
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_public_coupon_watch import classify_html, exact_article_url

POST_ID = 10953
SLUG = "kreatin-jako-podpora-energetickeho-metabolismu-pri-intenzivnim-treninku-v-ramci-fitness-diety"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "Kreatin jako podpora energetického metabolismu při intenzivním tréninku v rámci fitness diety"
# The previously documented coupon run 44794583745 changed this post at this
# exact moment. A subsequent edit must require a new editorial review.
REVIEWED_MODIFIED_GMT = "2026-11-20T18:38:52"
SOURCE = Path("content/revisions/creatine-metabolism-10953.html")
BACKUP = Path("reports/backups/xfit-creatine-10953-original.json")
MARK = 'data-xfit-creatine-10953="v1"'
SIGNATURE = "Kreatin může mít smysl, pokud jako zdravý dospělý pravidelně"
TARGETS = (
    "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
    "https://xfit.cz/xfit-os-kreatin-poradce/",
    "https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",
)
SOURCES = (
    "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC5469049/",
)
BAD_LINK = "https://www.example.com/fitness-diet-post"
OLD_SENTENCES = (
    "kreatin může způsobit mírné odvápnění",
    "Nejvhodnější dobou pro užívání kreatinu je před tréninkem",
    "Snížení možnosti svalové únavy a křečí",
)
MAX_BYTES = 350_000


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def post_title(post):
    field = post.get("title") or {}
    if not isinstance(field, dict):
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", field.get("raw") or field.get("rendered") or "")).strip()


def identity(post, *, authenticated=True):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish"
            or not exact_article_url(post.get("link"), SLUG)
            or post_title(post) != TITLE
            or not isinstance(post.get("modified_gmt"), str)
            or not post["modified_gmt"]):
        raise PublishError("Unexpected WordPress article identity")
    field = (post.get("content") or {}).get("raw" if authenticated else "rendered")
    if not isinstance(field, str) or len(field) < 1000 or len(field.encode()) > MAX_BYTES:
        raise PublishError("WordPress article body missing or oversized")
    return field


def revision():
    source = SOURCE.read_text(encoding="utf-8")
    if (len(source) < 7000 or source.count(MARK) != 1
            or source.count("<nav ") != 1
            or source.count("min-height:48px") != 3
            or any(source.count('href="' + target + '"') < 1 for target in TARGETS)
            or any(source.count('href="' + link + '"') < 1 for link in SOURCES)
            or any(term in source.lower() for term in (
                "5nm2022", "example.com", "<!doctype", "<html", "<head", "<body",
                "<link", "<script", "<iframe", "<form", "<style"))
            or re.search(r"\bon\w+\s*=", source, re.I)):
        raise PublishError("Reviewed revision structure changed")
    report = check_document({"content": source})
    if (report["word_count"] < 800 or report["h2_count"] < 7
            or len(report["source_hosts"]) < 2):
        raise PublishError("Insufficient editorial depth or independent sourcing")
    return source


def old_source(raw):
    # The exact damaged four-document source currently visible on the public
    # permalink. No relaxed matching after source or coupon drift.
    plain = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return (len(raw) > 5000 and raw.lower().count("<!doctype html>") == 4
            and raw.count(BAD_LINK) == 2
            and "script.js" in raw and "styles.css" in raw
            and all(fragment.casefold() in plain.casefold() for fragment in OLD_SENTENCES)
            and "5nm2022" not in raw.casefold() and MARK not in raw)


def classify(post):
    raw = identity(post)
    after = revision()
    if raw == after:
        mode = "already_applied"
    elif post["modified_gmt"] == REVIEWED_MODIFIED_GMT and old_source(raw):
        mode = "update"
    else:
        print(json.dumps({"state": "REVIEWED_SOURCE_MISMATCH", "post_id": POST_ID,
                          "modified_gmt": post.get("modified_gmt"), "old_markup": old_source(raw),
                          "remote_writes": 0}))
        raise PublishError("Legacy post changed since reviewed coupon cleanup")
    return {"mode": mode, "raw_sha": sha(raw), "after_sha": sha(after),
            "modified_gmt": post["modified_gmt"]}


def remote():
    return wp_request(normalized_base(), "posts/" + str(POST_ID)
                      + "?context=edit&_fields=id,slug,status,title,link,modified_gmt,content")


def public_rest():
    endpoint = "https://xfit.cz/wp-json/wp/v2/posts/" + str(POST_ID) \
               + "?_fields=id,slug,status,title,link,modified_gmt,content"
    req = Request(endpoint, headers={"User-Agent": "XFITOnepost10953/1.0",
                                     "Cache-Control": "no-cache"})
    with urlopen(req, timeout=25) as response:
        parsed = urlsplit(response.geturl())
        if (response.status != 200 or parsed.scheme != "https" or parsed.hostname != "xfit.cz"
                or parsed.path != "/wp-json/wp/v2/posts/10953"
                or parsed.username or parsed.password or parsed.port or parsed.fragment):
            raise PublishError("Unexpected public REST location")
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise PublishError("Oversized public REST")
    return json.loads(payload)


def public_page():
    req = Request(URL, headers={"User-Agent": "XFITOnepost10953/1.0",
                                "Cache-Control": "no-cache"})
    with urlopen(req, timeout=25) as response:
        if response.status != 200 or not exact_article_url(response.geturl(), SLUG):
            raise PublishError("Unexpected public article URL")
        data = response.read(3_000_001)
    if len(data) > 3_000_000:
        raise PublishError("Oversized public article")
    return data.decode("utf-8", "strict")


def old_public_fingerprint():
    post = public_rest()
    rendered = identity(post, authenticated=False)
    page = public_page()
    if (post["modified_gmt"] != REVIEWED_MODIFIED_GMT or not old_source(rendered)
            or not old_source(page)
            or page.count('rel="canonical"') != 2
            or "postid-10953" not in page):
        raise PublishError("Public damaged source changed before snapshot")
    return {"rendered_sha": sha(rendered), "modified_gmt": post["modified_gmt"]}


def verify_public():
    for attempt in range(3):
        try:
            post = public_rest()
            rendered = identity(post, authenticated=False)
            page = public_page()
            state, count = classify_html(page, POST_ID, SLUG)
            if (SIGNATURE in rendered and SIGNATURE in page
                    and rendered.count(MARK) == 1 and page.count(MARK) == 1
                    and all(target in rendered and target in page for target in TARGETS + SOURCES)
                    and state == "PUBLIC_NO_COUPON_OBSERVED" and count == 0
                    and page.count('rel="canonical"') == 1
                    and "<!DOCTYPE html><br" not in page
                    and BAD_LINK not in rendered and BAD_LINK not in page
                    and "script.js" not in rendered and "styles.css" not in rendered):
                return True
        except (PublishError, OSError, TypeError, ValueError, UnicodeError):
            pass
        if attempt < 2:
            time.sleep(4)
    return False


def snapshot():
    if BACKUP.exists():
        raise PublishError("Immutable backup already exists")
    post = remote()
    state = classify(post)
    preflight = old_public_fingerprint() if state["mode"] == "update" else None
    if state["mode"] == "already_applied" and not verify_public():
        raise PublishError("Already applied but public article could not be proved")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({"schema": 1, "post_id": POST_ID, "slug": SLUG,
                                  "original_authenticated_post": post,
                                  "mode": state["mode"], "raw_sha": state["raw_sha"],
                                  "after_sha": state["after_sha"], "modified_gmt": state["modified_gmt"],
                                  "public_before": preflight, "remote_writes": 0},
                                 ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY", "post_id": POST_ID,
                      "mode": state["mode"], "remote_writes": 0}))


def apply():
    if not BACKUP.exists():
        raise PublishError("Required rollback archive missing")
    doc = json.loads(BACKUP.read_text(encoding="utf-8"))
    after = revision()
    if (doc.get("schema") != 1 or doc.get("post_id") != POST_ID
            or doc.get("slug") != SLUG or doc.get("remote_writes") != 0
            or doc.get("after_sha") != sha(after)):
        raise PublishError("Rollback manifest mismatch")
    original = doc.get("original_authenticated_post")
    baseline = classify(original)
    current = classify(remote())
    if (baseline != current or doc.get("raw_sha") != baseline["raw_sha"]
            or doc.get("modified_gmt") != baseline["modified_gmt"]
            or doc.get("mode") != baseline["mode"]):
        raise PublishError("Authenticated source changed after snapshot; no write")
    if current["mode"] == "already_applied":
        if not verify_public():
            raise PublishError("Already applied but public proof unavailable")
        print(json.dumps({"state": "ALREADY_APPLIED_NO_WRITE", "post_id": POST_ID,
                          "public_site_modified": False}))
        return
    if doc.get("public_before") != old_public_fingerprint():
        raise PublishError("Public source changed after snapshot; no write")

    response_uncertain = False
    try:
        response = wp_request(normalized_base(), "posts/" + str(POST_ID),
                              payload={"content": after})
        response_uncertain = not isinstance(response, dict) or response.get("id") != POST_ID
    except (PublishError, OSError, ValueError, TypeError):
        response_uncertain = True
    try:
        saved = identity(remote())
        if saved != after:
            raise PublishError("Authenticated readback body mismatch")
    except (PublishError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"state": "UNRESOLVED_NO_RETRY", "post_id": POST_ID,
                          "post_attempts": 1, "response_uncertain": response_uncertain}))
        raise PublishError("Ambiguous WordPress write; manual review required") from exc
    if not verify_public():
        print(json.dumps({"state": "AUTH_VERIFIED_PUBLIC_UNVERIFIED", "post_id": POST_ID,
                          "post_attempts": 1, "response_uncertain": response_uncertain}))
        raise PublishError("WordPress saved, independent public proof unavailable")
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID, "url": URL,
                      "post_attempts": 1, "posts_changed": 1, "public_site_modified": True,
                      "canonical_count": 1, "coupon_mentions": 0}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        print(json.dumps({"state": "FAIL_CLOSED", "post_id": POST_ID,
                          "reason": str(error), "retry_post": False}))
        sys.exit(2)
