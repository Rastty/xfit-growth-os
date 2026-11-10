#!/usr/bin/env python3
"""One-post, source-bound insertion of the food-first choice in the protein decision table.

No WordPress plugin, no new article, no bulk update. A reviewed revision can
replace one exact table-row prefix on WP post 25451 while retaining every other live
editorial enhancement, link, markup and title. A rollback archive is mandatory
before the one possible REST POST; never repeat a possibly committed POST.
"""
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.wp_publish import MARKER, PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import Inspector, check_document

POST_ID = 25451
SLUG = "xfit-os-protein-guide"
REVISION = Path("content/revisions/editor-protein-table-opt-out.json")
BACKUP = Path("reports/backups/xfit-protein-table-optout-25451.json")
PUBLIC_URL = "https://xfit.cz/" + SLUG + "/"
MAX_BODY_BYTES = 450000


def digest(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def revision():
    data = json.loads(REVISION.read_text(encoding="utf-8"))
    if (not isinstance(data, dict)
            or data.get("status") != "editorial_proposal_not_deployed"
            or data.get("operation") != "replace_exact_once"
            or data.get("wp_post_id") != POST_ID
            or data.get("slug") != SLUG
            or data.get("source_file") != "content/ready/xfit-os-protein-guide.json"):
        raise PublishError("Unapproved or unexpected editorial revision")
    old, new = data.get("original"), data.get("replacement")
    if (not isinstance(old, str) or not isinstance(new, str)
            or old != "<tr><td>Univerzální protein za rozumnou cenu</td>"
            or not new.startswith("<tr><td>Bílkoviny už pokryjete běžným jídlem</td>")
            or not new.endswith(old)
            or new.count("<tr>") != 2 or new.count("</tr>") != 1
            or new.count("<td>") != 4 or new.count("</td>") != 4
            or len(new) > 600 or "<script" in new.casefold()
            or "<a " in new.casefold() or "<img" in new.casefold()):
        raise PublishError("Unexpected or unsafe no-supplement table revision")
    srcfile = Path(data["source_file"])
    source_bytes = srcfile.read_bytes()
    source = json.loads(source_bytes)
    if (digest(source_bytes.decode("utf-8")) != data.get("source_file_sha256")
            or source.get("slug") != SLUG or source.get("wp_post_id") != POST_ID
            or digest(source["content"]) != data.get("source_content_sha256")
            or source["content"].count(old) != 1):
        raise PublishError("Reviewed source snapshot does not match commit")
    preview = dict(source)
    preview["content"] = source["content"].replace(old, new, 1)
    check_document(preview)
    return data


def post():
    return wp_request(normalized_base(), "posts/" + str(POST_ID) +
                      "?context=edit&_fields=id,slug,status,content,link,modified_gmt")


def inspect(p, rev):
    if (not isinstance(p, dict) or type(p.get("id")) is not int
            or p["id"] != POST_ID or p.get("slug") != SLUG
            or p.get("status") != "publish"):
        raise PublishError("Target WordPress article changed identity or status")
    url = urllib.parse.urlsplit(p.get("link") or "")
    if (url.scheme != "https" or url.hostname not in ("xfit.cz", "www.xfit.cz")
            or url.username or url.password or url.port or url.query
            or url.fragment or url.path.rstrip("/") != "/" + SLUG):
        raise PublishError("Unexpected canonical WordPress permalink")
    raw = (p.get("content") or {}).get("raw")
    if (not isinstance(raw, str) or len(raw) < 500
            or len(raw.encode("utf-8")) > MAX_BODY_BYTES or MARKER not in raw):
        raise PublishError("Not an owned, safe WordPress source body")
    old, new = rev["original"], rev["replacement"]
    if raw.count(old) == 0 and raw.count(new) == 1:
        return {"status": "already_applied", "before": raw, "after": raw,
                "hash": digest(raw), "modified": p.get("modified_gmt")}
    if raw.count(old) != 1 or raw.count(new) != 0:
        raise PublishError("Original passage absent/duplicated or conflicting revision")
    changed = raw.replace(old, new, 1)
    if changed.replace(new, old, 1) != raw:
        raise PublishError("Reversibility validation failed")
    a, b = Inspector(), Inspector()
    a.feed(raw)
    b.feed(changed)
    if a.headers != b.headers or a.links != b.links or a.images != b.images:
        raise PublishError("Unapproved heading, link or image change")
    # A public post may contain previously approved appended AI sections.
    # Validate the ENTIRE updated page, not a stale ready-file replacement.
    check_document({"content": changed})
    return {"status": "ready", "before": raw, "after": changed,
            "hash": digest(raw), "modified": p.get("modified_gmt")}


def snapshot():
    rev = revision()
    state = inspect(post(), rev)
    if BACKUP.exists():
        raise PublishError("Existing rollback snapshot cannot be overwritten")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema_version": 1, "post_id": POST_ID, "slug": SLUG,
        "original_raw": state["before"], "original_hash": state["hash"],
        "expected_hash": digest(state["after"]),
        "modified_gmt": state["modified"], "state": state["status"],
        "revision_sha256": digest(REVISION.read_text(encoding="utf-8")),
        "remote_writes": 0,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"state": "PROTEIN_TABLE_OPTOUT_BACKUP_READY", "post_id": POST_ID,
                      "write_needed": state["status"] == "ready",
                      "remote_writes": 0}))


def public_verified(url=PUBLIC_URL, *, reader=None):
    """Require real public body to expose the proposed section, not only API."""
    def matches(body):
        # Match the new row as it appears to readers, not only the REST post.
        visible = " ".join(html.unescape(
            re.sub(r"<[^>]+>", " ", body)).split()).casefold()
        return (visible.count("bílkoviny už pokryjete běžným jídlem") == 1
                and "žádný proteinový doplněk" in visible
                and "než přejdete ke srovnání cen" in visible
                and "univerzální protein za rozumnou cenu" in visible
                and "kolik bílkovin vlastně potřebujete" in visible)
    if reader is not None:
        return matches(reader(url))
    for attempt in range(3):
        req = urllib.request.Request(url, headers={
            "User-Agent": "XFITProteinTableOptout/1.0",
            "Cache-Control": "no-cache", "Pragma": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                real = urllib.parse.urlsplit(resp.geturl())
                if (resp.status != 200 or real.scheme != "https"
                        or real.hostname not in ("xfit.cz", "www.xfit.cz")
                        or real.path.rstrip("/") != "/" + SLUG
                        or real.query or real.fragment):
                    raise PublishError("Public page returned a foreign location")
                body = resp.read(2_500_001)
                if len(body) > 2_500_000:
                    raise PublishError("Public page too large to verify")
                if matches(body.decode("utf-8", errors="replace")):
                    return True
        except (OSError, UnicodeError) as exc:
            if attempt == 2:
                raise PublishError("Public page readback unavailable") from exc
        if attempt < 2:
            time.sleep(3)
    return False


def apply():
    if not BACKUP.exists():
        raise PublishError("Missing mandatory rollback artifact source")
    rev = revision()
    manifest = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1
            or manifest.get("post_id") != POST_ID
            or manifest.get("slug") != SLUG
            or manifest.get("remote_writes") != 0
            or manifest.get("revision_sha256") != digest(
                REVISION.read_text(encoding="utf-8"))):
        raise PublishError("Untrusted rollback manifest")

    current = inspect(post(), rev)
    if (current["hash"] != manifest.get("original_hash")
            or current["before"] != manifest.get("original_raw")
            or current["modified"] != manifest.get("modified_gmt")
            or digest(current["after"]) != manifest.get("expected_hash")
            or current["status"] != manifest.get("state")):
        raise PublishError("Concurrent WordPress edit since backup; no write")

    if current["status"] == "already_applied":
        if not public_verified():
            raise PublishError("Previously applied revision not visible publicly")
        print(json.dumps({"state": "ALREADY_APPLIED_NO_WRITE",
                          "post_id": POST_ID, "public_site_modified": False,
                          "url": PUBLIC_URL, "post_attempts": 0}))
        return

    # Only ONE authenticated WP POST. A thrown HTTP error or timeout may be a
    # completed remote write: reconcile with a separate authenticated GET.
    write_failed = False
    try:
        saved = wp_request(normalized_base(), "posts/" + str(POST_ID),
                           payload={"content": current["after"]})
        if saved.get("id") != POST_ID or saved.get("status") != "publish":
            write_failed = True
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        write_failed = True

    try:
        latest = post()
        if (latest.get("id") != POST_ID or latest.get("slug") != SLUG
                or latest.get("status") != "publish"):
            raise PublishError("Unexpected identity on WordPress readback")
        saved_raw = (latest.get("content") or {}).get("raw")
        saved_hash = digest(saved_raw) if isinstance(saved_raw, str) else None
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"state": "BLOCKED_MANUAL_REVIEW",
                          "post_id": POST_ID, "reason": "api_readback_unavailable"}))
        raise PublishError("Ambiguous REST write; never retry POST")
    if saved_hash == current["hash"]:
        print(json.dumps({"state": "UNRESOLVED_UNCHANGED",
                          "post_id": POST_ID, "post_attempts": 1,
                          "public_site_modified": False}))
        raise PublishError("WordPress unchanged after one attempted update")
    if saved_hash != digest(current["after"]):
        print(json.dumps({"state": "BLOCKED_MANUAL_REVIEW",
                          "post_id": POST_ID, "reason": "content_drift"}))
        raise PublishError("Unexpected concurrent change or WordPress transformation")

    if not public_verified():
        print(json.dumps({"state": "API_VERIFIED_PUBLIC_STALE",
                          "post_id": POST_ID, "public_site_modified": True}))
        raise PublishError("New text saved, but not yet visible publicly")
    print(json.dumps({
        "state": "PUBLIC_VERIFIED", "post_id": POST_ID, "slug": SLUG,
        "url": PUBLIC_URL, "posts_changed": 1, "post_attempts": 1,
        "public_site_modified": True, "new_table_rows_inserted": 1,
        "new_posts": 0, "deletes": 0, "redirects": 0,
    }))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, TypeError, ValueError, KeyError) as exc:
        # Logs must contain no raw WordPress HTML, bearer credentials or
        # affiliate URLs. The detailed facts remain in the rollback artifact.
        print("XFIT_PROTEIN_TABLE_OPTOUT_ERROR: " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(2)
