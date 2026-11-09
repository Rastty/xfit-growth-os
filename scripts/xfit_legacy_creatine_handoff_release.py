"""One verified legacy-post edit: a relevant creatine decision handoff.

Only WordPress article 4224 is authorized. Preserve original body exactly and
append one reviewed paragraph. Never republish a stale repository article.
A full pre-write backup artifact and live REST/public readbacks are mandatory.
No retry on ambiguous POST; running again is idempotent.
"""
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import Inspector

POST_ID = 4224
SLUG = ("nejlepsi-zpusoby-jak-kombinovat-kreatin-s-dalsimi-doplnky-"
        "stravy-a-treninkovymi-metodami-pro-uspech-v-fitness")
URL = "https://xfit.cz/" + SLUG + "/"
TARGET = "https://xfit.cz/xfit-os-kreatin-poradce/"
MARK = "xfit-legacy-creatine-choice-20261109"
VISIBLE = "Rozhodněte se, zda kreatin vůbec potřebujete"
PARAGRAPH = (
    '<p data-xfit-legacy="' + MARK + '">'
    '<strong>' + VISIBLE + '.</strong> '
    'Kombinace více doplňků není automaticky nutná. Nejdřív si ujasněte '
    'tréninkový cíl, rozpočet a zda vám stačí běžná strava a trénink. '
    'Jestliže pro vás kreatin dává smysl, můžete použít '
    '<a href="' + TARGET + '">nezávislý výběr kreatinu '
    'podle velikosti balení a ceny za 100 g prášku</a>. '
    'Ceny z produktového katalogu nejsou konečnou cenou s dopravou '
    'a neprokazují čistotu výrobku. Pokud doplněk nepotřebujete, '
    'nemusíte nic kupovat.</p>'
)
BACKUP = Path("reports/backups/xfit-legacy-creatine-4224.json")
MAX_BYTES = 400_000


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            link = dict(attrs).get("href")
            if isinstance(link, str):
                self.hrefs.add(html.unescape(link))


def hrefs(value):
    p = Anchors()
    p.feed(value)
    return p.hrefs


def remote():
    return wp_request(
        normalized_base(),
        "posts/" + str(POST_ID) +
        "?context=edit&_fields=id,slug,status,link,title,content,modified_gmt",
    )


def prepare(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish"):
        raise PublishError("Pinned article identity/status mismatch")
    u = urllib.parse.urlsplit(post.get("link") or "")
    if (u.scheme != "https" or u.hostname not in ("xfit.cz", "www.xfit.cz")
            or u.username or u.password or u.port
            or u.query or u.fragment or u.path.rstrip("/") != "/" + SLUG):
        raise PublishError("Pinned article public URL mismatch")
    title = (post.get("title") or {}).get("raw") or ""
    if "kreatin" not in html.unescape(re.sub(r"<[^>]+>", " ", title)).casefold():
        raise PublishError("Pinned article title no longer matches topic")
    raw = (post.get("content") or {}).get("raw")
    if (not isinstance(raw, str) or len(raw) < 1500
            or len(raw.encode("utf-8")) > MAX_BYTES):
        raise PublishError("Missing or oversized legacy source")
    modified = post.get("modified_gmt")
    if not isinstance(modified, str) or not modified:
        raise PublishError("Missing source version date")
    existing = hrefs(raw)
    if TARGET in existing:
        if MARK in raw and raw.count(MARK) != 1:
            raise PublishError("Repeated source marker")
        return {"state": "already_linked", "before": raw, "after": raw,
                "before_sha": sha(raw), "modified": modified}
    if MARK in raw:
        raise PublishError("Partial legacy patch; target anchor missing")
    if "</script" in PARAGRAPH.casefold() or "<iframe" in PARAGRAPH.casefold():
        raise PublishError("Unexpected active editor HTML")
    new = raw + "\n" + PARAGRAPH
    before, after = Inspector(), Inspector()
    before.feed(raw)
    after.feed(new)
    if (before.headers != after.headers or before.images != after.images
            or after.links != before.links + [(TARGET, "")]):
        raise PublishError("Unrelated links, headings or images changed")
    if (not new.startswith(raw + "\n") or new.count(MARK) != 1
            or TARGET not in hrefs(new)):
        raise PublishError("Non-reversible or incomplete proposed edit")
    return {"state": "update", "before": raw, "after": new,
            "before_sha": sha(raw), "modified": modified}


def snapshot():
    state = prepare(remote())
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    if BACKUP.exists():
        raise PublishError("Rollback file already exists")
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG,
        "mode": state["state"], "before_sha": state["before_sha"],
        "after_sha": sha(state["after"]), "modified": state["modified"],
        "original_raw": state["before"], "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "LEGACY_CREATINE_BACKUP_READY",
                      "post_id": POST_ID, "write_needed": state["state"] == "update",
                      "remote_writes": 0}))


def public_verified(*, reader=None):
    """Verify exact public permalink, unique editorial text and real href."""
    def accepted(body):
        if not isinstance(body, str):
            return False
        if TARGET not in hrefs(body):
            return False
        readable = " ".join(html.unescape(re.sub(r"<[^>]*>", " ", body)).split())
        return VISIBLE in readable and "nemusíte nic kupovat" in readable

    if reader is not None:
        return accepted(reader(URL))
    for attempt in range(3):
        req = urllib.request.Request(URL, headers={
            "User-Agent": "XFITLegacyCreatineReadback/1.0",
            "Cache-Control": "no-cache", "Pragma": "no-cache",
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                final = urllib.parse.urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https"
                        or final.hostname not in ("xfit.cz", "www.xfit.cz")
                        or final.username or final.password or final.port
                        or final.query or final.fragment
                        or final.path.rstrip("/") != "/" + SLUG):
                    raise PublishError("Public page identity changed")
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise PublishError("Public page exceeded readback bound")
                if accepted(data.decode("utf-8", errors="replace")):
                    return True
        except (OSError, ValueError):
            if attempt == 2:
                raise PublishError("Public page readback unavailable")
        if attempt < 2:
            time.sleep(3)
    return False


def apply():
    if not BACKUP.exists():
        raise PublishError("Missing pre-write artifact")
    state = prepare(remote())
    backed = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (backed.get("schema") != 1 or backed.get("post_id") != POST_ID
            or backed.get("slug") != SLUG or backed.get("remote_writes") != 0
            or backed.get("mode") != state["state"]
            or backed.get("before_sha") != state["before_sha"]
            or backed.get("original_raw") != state["before"]
            or backed.get("modified") != state["modified"]
            or backed.get("after_sha") != sha(state["after"])):
        raise PublishError("WordPress source drifted since saved backup")
    if state["state"] == "already_linked":
        if not public_verified():
            raise PublishError("Already-linked source not public")
        print(json.dumps({"state": "ALREADY_LINKED_NO_WRITE",
                          "post_id": POST_ID, "url": URL,
                          "public_site_modified": False, "post_attempts": 0}))
        return

    # Exactly one POST; a failed HTTP response may already have committed.
    response_error = False
    try:
        result = wp_request(normalized_base(), "posts/" + str(POST_ID),
                            payload={"content": state["after"]})
        if (not isinstance(result, dict) or result.get("id") != POST_ID
                or result.get("status") != "publish"):
            response_error = True
    except (PublishError, OSError, ValueError, TypeError):
        response_error = True

    try:
        post = remote()
        if (post.get("id") != POST_ID or post.get("slug") != SLUG
                or post.get("status") != "publish"):
            raise PublishError("Post identity drift after attempted write")
        current = (post.get("content") or {}).get("raw")
        current_sha = sha(current) if isinstance(current, str) else None
    except (PublishError, OSError, ValueError, TypeError, AttributeError):
        print(json.dumps({"state": "BLOCKED_MANUAL_REVIEW",
                          "post_id": POST_ID, "reason": "readback_unknown",
                          "write_response_uncertain": response_error}))
        raise PublishError("Unknown post-write state; never retry blindly")

    if current_sha != sha(state["after"]):
        print(json.dumps({"state": "UNRESOLVED_OR_DRIFTED",
                          "post_id": POST_ID,
                          "content_unchanged": current_sha == state["before_sha"],
                          "post_attempts": 1}))
        raise PublishError("Exact expected WordPress content not confirmed")
    if not public_verified():
        print(json.dumps({"state": "API_VERIFIED_PUBLIC_STALE",
                          "post_id": POST_ID, "post_attempts": 1}))
        raise PublishError("WordPress accepted but public page stale")
    print(json.dumps({"state": "PUBLIC_VERIFIED",
                      "post_id": POST_ID, "url": URL,
                      "post_attempts": 1, "posts_changed": 1,
                      "new_posts": 0, "public_site_modified": True}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, TypeError, AttributeError) as exc:
        # Never echo raw HTML, credentials, or a private WP response body.
        print("XFIT_LEGACY_CREATINE_RELEASE_ERROR: " + type(exc).__name__,
              file=sys.stderr)
        raise SystemExit(2)
