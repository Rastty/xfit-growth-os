"""One-post evidence-backed rewrite of legacy BCAA/whey article #2502.

Snapshot -> immutable artifact -> revalidate exact source -> one possible POST
-> authenticated and independent public readback. No other article or metadata
can change; a timeout never triggers another POST.
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

POST_ID = 2502
SLUG = "bcaa-vs-whey-protein-jake-jsou-rozdily-a-ktere-doplneni-je-pro-vas-nejlepsi"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "BCAA vs. whey protein: Jaké jsou rozdíly a které doplnění je pro vás nejlepší?"
SOURCE = Path("content/revisions/bcaa-vs-whey-2502.html")
BACKUP = Path("reports/backups/xfit-bcaa-whey-2502-original.json")
MARK = 'data-xfit-bcaa-choice="v1"'
SIGNATURE = "Pokud potřebujete doplnit bílkoviny, je zpravidla praktičtější"
TARGETS = (
    "https://xfit.cz/xfit-os-protein-guide/",
    "https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/",
    "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
)
SOURCE_LINKS = (
    "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC5477153/",
)
OLD_FINGERPRINTS = (
    "What are BCAAs and whey protein?",
    "BCAA zvyšují anabolické hormony",
    "ketleiové aminokyseliny",
)
MAX_BYTES = 350_000


def sha(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def exact_permalink(link):
    if not isinstance(link, str):
        return False
    parsed = urlsplit(link)
    return (parsed.scheme == "https" and parsed.hostname in ("xfit.cz", "www.xfit.cz")
            and parsed.username is None and parsed.password is None
            and parsed.port is None and not parsed.query and not parsed.fragment
            and parsed.path == "/" + SLUG + "/")


def title_of(post):
    title = post.get("title") or {}
    if not isinstance(title, dict):
        return ""
    raw = title.get("raw") or title.get("rendered") or ""
    return html.unescape(re.sub(r"<[^>]*>", "", raw)).strip()


def identity(post, *, authenticated=True):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish" or not exact_permalink(post.get("link"))
            or title_of(post) != TITLE or not isinstance(post.get("modified_gmt"), str)
            or not post["modified_gmt"]):
        raise PublishError("Unexpected WordPress post identity, title, or status")
    content = post.get("content")
    if not isinstance(content, dict):
        raise PublishError("Unexpected WordPress post content")
    field = "raw" if authenticated else "rendered"
    body = content.get(field)
    if (not isinstance(body, str) or len(body) < 1000
            or len(body.encode("utf-8")) > MAX_BYTES):
        raise PublishError("Missing or oversized WordPress " + field)
    return body


def revision():
    body = SOURCE.read_text(encoding="utf-8")
    if (len(body) < 7000 or body.count(MARK) != 1
            or body.count("<nav ") != 1 or body.count("min-height:48px") != 3
            or any(body.count('href="' + link + '"') != (2 if link == TARGETS[1] else 1)
                   for link in TARGETS)
            or any(body.count(link) != 2 for link in SOURCE_LINKS)
            or "5NM2022" in body or any(x in body for x in OLD_FINGERPRINTS)
            or re.search(r"<\s*(script|iframe|form)\b|\bon\w+\s*=", body, re.I)):
        raise PublishError("Reviewed replacement body unexpectedly changed")
    quality = check_document({"content": body})
    if quality["word_count"] < 700 or quality["h2_count"] < 6 or len(quality["source_hosts"]) < 2:
        raise PublishError("Insufficient independent quality or sourcing")
    return body


def remote():
    return wp_request(normalized_base(), "posts/" + str(POST_ID)
                      + "?context=edit&_fields=id,slug,status,title,link,modified_gmt,content")


def public_rest():
    endpoint = "https://xfit.cz/wp-json/wp/v2/posts/" + str(POST_ID) \
               + "?_fields=id,slug,status,title,link,modified_gmt,content"
    req = Request(endpoint, headers={"User-Agent": "XFITBCAAOnepost/1.0",
                                     "Cache-Control": "no-cache"})
    with urlopen(req, timeout=25) as response:
        final = urlsplit(response.geturl())
        if (response.status != 200 or final.scheme != "https"
                or final.hostname not in ("xfit.cz", "www.xfit.cz")
                or final.username or final.password or final.port
                or final.path != "/wp-json/wp/v2/posts/" + str(POST_ID)
                or final.fragment):
            raise PublishError("Unexpected public REST response")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise PublishError("Oversized public REST response")
    return json.loads(data)


def public_page():
    request = Request(URL, headers={"User-Agent": "XFITBCAAOnepost/1.0",
                                    "Cache-Control": "no-cache", "Pragma": "no-cache"})
    with urlopen(request, timeout=25) as response:
        if response.status != 200 or not exact_permalink(response.geturl()):
            raise PublishError("Unexpected public permalink")
        data = response.read(2_500_001)
    if len(data) > 2_500_000:
        raise PublishError("Oversized public page")
    return data.decode("utf-8", "replace")


def old_source(raw):
    # High-specificity fingerprints from the independently reviewed live article.
    # Any extra editorial edit or changed coupon footprint requires new review.
    return (len(raw) >= 5000 and raw.upper().count("5NM2022") == 3
            and all(x in html.unescape(re.sub(r"<[^>]+>", " ", raw))
                    for x in OLD_FINGERPRINTS))


def classify(post):
    before = identity(post)
    after = revision()
    if before == after:
        mode = "already_applied"
    elif old_source(before) and MARK not in before:
        mode = "update"
    else:
        visible = html.unescape(re.sub(r"<[^>]+>", " ", before))
        print(json.dumps({"state": "LEGACY_AUTH_SOURCE_MISMATCH",
                          "post_id": POST_ID, "bytes": len(before.encode("utf-8")),
                          "coupon_mentions": before.upper().count("5NM2022"),
                          "old_reviewed_fingerprints_present":
                          [fingerprint in visible for fingerprint in OLD_FINGERPRINTS],
                          "revision_marker_present": MARK in before,
                          "remote_writes": 0}))
        raise PublishError("Unreviewed legacy source; refusal to overwrite")
    return {"mode": mode, "raw": before, "raw_sha": sha(before),
            "after_sha": sha(after), "modified_gmt": post["modified_gmt"]}


def public_old_fingerprint():
    post = public_rest()
    rendered = identity(post, authenticated=False)
    if not old_source(rendered):
        raise PublishError("Public REST article no longer matches reviewed legacy content")
    page = public_page()
    if page.count("5NM2022") < 3 or "<h1" not in page.lower():
        raise PublishError("Public page no longer displays reviewed coupon footprint")
    return {"rendered_sha": sha(rendered), "modified_gmt": post["modified_gmt"]}


def verify_public():
    for attempt in range(3):
        try:
            post = public_rest()
            rendered = identity(post, authenticated=False)
            page = public_page()
            if (SIGNATURE in rendered and SIGNATURE in page
                    and page.count(MARK) == 1 and rendered.count(MARK) == 1
                    and all(link in page and link in rendered for link in TARGETS + SOURCE_LINKS)
                    and "5NM2022" not in page and "5NM2022" not in rendered
                    and not any(x in page or x in rendered for x in OLD_FINGERPRINTS)):
                return True
        except (OSError, PublishError, ValueError, TypeError, UnicodeError):
            pass
        if attempt < 2:
            time.sleep(4)
    return False


def snapshot():
    if BACKUP.exists():
        raise PublishError("Backup archive already exists; no overwrite")
    post = remote()
    state = classify(post)
    print(json.dumps({"state": "LEGACY_AUTH_SOURCE_ACCEPTED", "post_id": POST_ID,
                      "mode": state["mode"], "remote_writes": 0}))
    previous = public_old_fingerprint() if state["mode"] == "update" else None
    print(json.dumps({"state": "LEGACY_PUBLIC_SOURCE_ACCEPTED", "post_id": POST_ID,
                      "mode": state["mode"], "remote_writes": 0}))
    if state["mode"] == "already_applied" and not verify_public():
        raise PublishError("Already-applied article cannot be verified publicly")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG,
        "mode": state["mode"], "modified_gmt": state["modified_gmt"],
        "original_sha": state["raw_sha"], "original_authenticated_post": post,
        "revision_sha": state["after_sha"], "public_before": previous,
        "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY", "post_id": POST_ID,
                      "mode": state["mode"], "remote_writes": 0}))


def apply():
    if not BACKUP.exists():
        raise PublishError("Mandatory immutable rollback artifact missing")
    manifest = json.loads(BACKUP.read_text(encoding="utf-8"))
    body = revision()
    old = manifest.get("original_authenticated_post")
    if (manifest.get("schema") != 1 or manifest.get("post_id") != POST_ID
            or manifest.get("slug") != SLUG or manifest.get("remote_writes") != 0
            or not isinstance(old, dict) or manifest.get("revision_sha") != sha(body)):
        raise PublishError("Untrusted rollback manifest")
    baseline = classify(old)
    current = classify(remote())
    if (manifest.get("original_sha") != baseline["raw_sha"]
            or manifest.get("modified_gmt") != baseline["modified_gmt"]
            or manifest.get("mode") != baseline["mode"] or current != baseline):
        raise PublishError("Concurrent edit since snapshot; no write")
    if current["mode"] == "already_applied":
        if not verify_public():
            raise PublishError("Already applied but public proof failed")
        print(json.dumps({"state": "ALREADY_APPLIED_NO_WRITE", "post_id": POST_ID,
                          "public_site_modified": False}))
        return
    if manifest.get("public_before") != public_old_fingerprint():
        raise PublishError("Public article changed since snapshot")

    uncertain = False
    try:
        response = wp_request(normalized_base(), "posts/" + str(POST_ID),
                              payload={"content": body})
        if not isinstance(response, dict) or response.get("id") != POST_ID:
            uncertain = True
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        uncertain = True
    try:
        after = remote()
        readback = identity(after)
        if readback != body:
            raise PublishError("Authenticated content mismatch")
    except (PublishError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"state": "UNRESOLVED_NO_RETRY", "post_id": POST_ID,
                          "post_attempts": 1, "response_uncertain": uncertain}))
        raise PublishError("Ambiguous WordPress result; manual review required") from exc
    if not verify_public():
        print(json.dumps({"state": "API_VERIFIED_PUBLIC_STALE", "post_id": POST_ID,
                          "post_attempts": 1, "response_uncertain": uncertain}))
        raise PublishError("Authenticated rewrite saved, public cache not verified")
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID, "url": URL,
                      "post_attempts": 1, "posts_changed": 1,
                      "public_site_modified": True, "expired_coupon_removed": True}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        # PublishError messages are authored here or in wp_publish and do not
        # include URLs with affiliate query params, article bodies or tokens.
        reason = str(exc) if isinstance(exc, PublishError) else type(exc).__name__
        print("XFIT_BCAA_2502_RELEASE_ERROR: " + reason, file=sys.stderr)
        raise SystemExit(2)
