"""One-post, fail-closed first-screen choices on the existing protein guide.

Preserve the *current* WordPress body (including later editorial releases),
snapshot it before the only permitted POST and verify the public result.
Never replace the article from the older content/ready file.
"""
import hashlib
import html
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import MARKER, PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import Inspector, check_document

POST_ID = 25451
SLUG = "xfit-os-protein-guide"
URL = "https://xfit.cz/" + SLUG + "/"
BACKUP = Path("reports/backups/xfit-protein-early-choices-25451.json")
MARK = 'data-xfit-choice="protein-guide-v1"'
SOURCE = Path("content/ready/xfit-os-protein-guide.json")
MAX_BYTES = 450_000
TARGETS = (
    "https://xfit.cz/kolik-bilkovin-potrebujete-pro-budovani-svalu-pruvodce-spravnym-stravovanim/",
    "https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/",
    "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
)
CHOICES = (
    ("1. Ověřit, zda vůbec potřebuji prášek", "Začněte běžným jídlem a výpočtem celkového příjmu."),
    ("2. Spočítat cenu podle etikety", "Porovnejte skutečné bílkoviny, nejen hmotnost prášku."),
    ("3. Porovnat nabídky syrovátkových proteinů", "Vybraný katalog jednoho prodejce; cenu a sklad ověřte v košíku."),
)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def intro():
    """Pin the already-reviewed first paragraph, not a stale full document."""
    document = json.loads(SOURCE.read_text(encoding="utf-8"))
    if document.get("slug") != SLUG or document.get("wp_post_id") != POST_ID:
        raise PublishError("Unexpected source document identity")
    body = document.get("content")
    if not isinstance(body, str) or not body.startswith("<p><strong>"):
        raise PublishError("Source introduction missing")
    first = body.split("</p>", 1)[0] + "</p>"
    if (len(first) < 200 or len(first) > 1000 or "Nejlepší protein" not in first
            or body.count(first) != 1):
        raise PublishError("Reviewed introduction has changed")
    return first


def panel():
    actions = []
    for (label, explanation), target in zip(CHOICES, TARGETS):
        actions.append(
            '<li style="margin:0 0 10px;padding:0;">'
            '<a href="' + html.escape(target, quote=True) + '" '
            'style="display:block;min-height:48px;box-sizing:border-box;'
            'padding:13px 14px;border:1px solid #b6cdd0;border-radius:8px;'
            'background:#f3f8f8;color:#164f54;font-weight:700;text-decoration:underline;">'
            + html.escape(label) + '</a>'
            '<small style="display:block;margin:4px 0 0 2px;">'
            + html.escape(explanation) + '</small></li>'
        )
    return (
        '<nav ' + MARK + ' aria-label="Rychlé rozhodnutí o proteinu" '
        'style="border:1px solid #dce5e8;border-radius:12px;padding:14px;margin:18px 0;">'
        '<p><strong>Co teď udělat?</strong> Proteinový prášek není povinný. '
        'Vyberte jednu cestu podle toho, co právě řešíte.</p>'
        '<ul style="list-style:none;padding:0;margin:0;">' + ''.join(actions) + '</ul>'
        '<p><small>Poslední možnost vede na srovnání produktů s označenými '
        'partnerskými odkazy. Nejde o přehled celého trhu ani o potvrzení '
        'aktuální skladové dostupnosti.</small></p></nav>'
    )


def read_post():
    return wp_request(normalized_base(), "posts/" + str(POST_ID) +
                      "?context=edit&_fields=id,slug,status,link,content,modified_gmt")


def prepare(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish"):
        raise PublishError("Unexpected WordPress identity or status")
    link = urlsplit(post.get("link") or "")
    if (link.scheme != "https" or link.hostname not in ("xfit.cz", "www.xfit.cz")
            or link.port is not None or link.username or link.password
            or link.query or link.fragment or link.path != "/" + SLUG + "/"):
        raise PublishError("Unexpected WordPress canonical permalink")
    raw = (post.get("content") or {}).get("raw")
    modified = post.get("modified_gmt")
    if (not isinstance(raw, str) or len(raw) < 1500
            or len(raw.encode("utf-8")) > MAX_BYTES
            or not raw.startswith(MARKER) or not isinstance(modified, str)
            or not modified):
        raise PublishError("WordPress source or revision stamp unavailable")
    first, added = intro(), panel()
    if raw.count(first) != 1 or raw.index(first) > 1500:
        raise PublishError("Original introduction changed or duplicated")
    if raw.count(MARK) == 1 and raw.count(added) == 1:
        return {"mode": "already_applied", "before": raw, "after": raw,
                "hash": digest(raw), "modified": modified}
    if MARK in raw or raw.count(added):
        raise PublishError("Partial or conflicting choices already exist")
    updated = raw.replace(first, first + "\n" + added, 1)
    if updated.replace(first + "\n" + added, first, 1) != raw:
        raise PublishError("Panel insertion is not reversible")
    before, after = Inspector(), Inspector()
    before.feed(raw)
    after.feed(updated)
    if before.headers != after.headers or before.images != after.images:
        raise PublishError("Unapproved heading/image change")
    if len(after.links) != len(before.links) + len(TARGETS):
        raise PublishError("Unexpected number of inserted links")
    expected = Inspector()
    expected.feed(added)
    if len(expected.links) != len(TARGETS):
        raise PublishError("Invalid reviewed panel")
    # Inserted nav must be before any pre-existing guide links.
    if after.links != expected.links + before.links:
        raise PublishError("Unexpected link order or destination")
    if not check_document({"content": updated})["passed"]:
        raise PublishError("Editorial gate rejected proposed article")
    return {"mode": "update", "before": raw, "after": updated,
            "hash": digest(raw), "modified": modified}


def public_matches(body):
    if not isinstance(body, str) or body.count(MARK) != 1:
        return False
    marker = body.index(MARK)
    section = body[marker:marker + len(panel()) + 1300]
    title = body.find("Rychlá volba: který typ dává smysl?")
    if title == -1 or marker > title:
        return False
    for (label, _), target in zip(CHOICES, TARGETS):
        if section.count('href="' + target + '"') != 1:
            return False
        if html.escape(label) not in section:
            return False
    return "Proteinový prášek není povinný" in section


def verify_public(*, reader=None):
    if reader is not None:
        return public_matches(reader(URL))
    for attempt in range(3):
        try:
            request = Request(URL, headers={"User-Agent": "XFITEarlyChoices/1.0",
                                            "Cache-Control": "no-cache"})
            with urlopen(request, timeout=25) as response:
                final = urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https"
                        or final.hostname not in ("xfit.cz", "www.xfit.cz")
                        or final.path != "/" + SLUG + "/"
                        or final.query or final.fragment):
                    raise PublishError("Unexpected public response identity")
                raw = response.read(2_500_001)
                if len(raw) > 2_500_000:
                    raise PublishError("Public page size exceeded")
                if public_matches(raw.decode("utf-8", errors="replace")):
                    return True
        except (OSError, UnicodeError) as exc:
            if attempt == 2:
                raise PublishError("Public readback unavailable") from exc
        if attempt < 2:
            time.sleep(3)
    return False


def snapshot():
    state = prepare(read_post())
    if BACKUP.exists():
        raise PublishError("Rollback archive already exists")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema_version": 1, "post_id": POST_ID, "slug": SLUG,
        "original_raw": state["before"], "original_hash": state["hash"],
        "expected_hash": digest(state["after"]),
        "modified_gmt": state["modified"], "mode": state["mode"],
        "panel_sha256": digest(panel()), "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY", "post_id": POST_ID,
                      "write_needed": state["mode"] == "update", "remote_writes": 0}))


def apply():
    if not BACKUP.exists():
        raise PublishError("Mandatory immutable rollback artifact missing")
    manifest = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("post_id") != POST_ID
            or manifest.get("slug") != SLUG or manifest.get("remote_writes") != 0
            or manifest.get("panel_sha256") != digest(panel())):
        raise PublishError("Untrusted rollback manifest")
    state = prepare(read_post())
    if (manifest.get("original_hash") != state["hash"]
            or manifest.get("original_raw") != state["before"]
            or manifest.get("modified_gmt") != state["modified"]
            or manifest.get("expected_hash") != digest(state["after"])
            or manifest.get("mode") != state["mode"]):
        raise PublishError("Concurrent WordPress edit since snapshot")
    if state["mode"] == "already_applied":
        if not verify_public():
            raise PublishError("Already-applied panel not visible publicly")
        print(json.dumps({"state": "ALREADY_APPLIED_NO_WRITE", "post_id": POST_ID,
                          "public_site_modified": False}))
        return
    try:
        wp_request(normalized_base(), "posts/" + str(POST_ID),
                   payload={"content": state["after"]})
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        # One and only one POST; reconcile ambiguous responses via GET.
        pass
    try:
        latest = read_post()
        if (latest.get("id") != POST_ID or latest.get("slug") != SLUG
                or latest.get("status") != "publish"):
            raise PublishError("Unexpected post identity after write")
        saved = (latest.get("content") or {}).get("raw")
        saved_hash = digest(saved) if isinstance(saved, str) else None
    except (PublishError, OSError, TypeError, ValueError, KeyError):
        print(json.dumps({"state": "BLOCKED_MANUAL_REVIEW", "reason": "readback_unavailable"}))
        raise PublishError("Ambiguous POST; do not retry")
    if saved_hash != digest(state["after"]):
        raise PublishError("Post did not retain exact reviewed content; do not retry")
    if not verify_public():
        raise PublishError("WP API verified, but public panel not visible")
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID,
                      "url": URL, "posts_changed": 1, "post_attempts": 1,
                      "public_site_modified": True}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, KeyError, TypeError) as exc:
        print("XFIT_PROTEIN_EARLY_CHOICES_ERROR: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
