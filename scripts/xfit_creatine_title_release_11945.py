"""One title-only correction on the already verified WP creatine post 11945.

Never retry an uncertain POST. Keep content, excerpt, status, slug and canonical
URL immutable and verify the actual public H1 after authenticated readback.
"""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

from scripts.wp_publish import PublishError, normalized_base, wp_request


POST_ID = 11945
SLUG = "jak-kreatin-muze-pomoci-ziskat-svalovy-objem-v-fitness"
URL = "https://xfit.cz/" + SLUG + "/"
OLD_TITLE = "Jak kreatin může pomoci získat svalový objem v fitness"
NEW_TITLE = "Jak kreatin může pomoci získat svalový objem: co říkají studie"
BACKUP = Path("reports/backups/xfit-creatine-title-11945.json")


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_post():
    return wp_request(normalized_base(), "posts/11945?context=edit&_fields="
                      "id,slug,status,title,content,excerpt,link")


def classify(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish" or post.get("link") != URL):
        raise PublishError("Unexpected WordPress post or canonical identity")
    title = (post.get("title") or {}).get("raw")
    body = (post.get("content") or {}).get("raw")
    excerpt = (post.get("excerpt") or {}).get("raw")
    if (title not in (OLD_TITLE, NEW_TITLE) or not isinstance(body, str)
            or not 4500 < len(body.encode("utf-8")) < 500000
            or not isinstance(excerpt, str)
            or "Může kreatin pomoci nabrat svaly?" not in body
            or "Zdroje, omezení a redakční metodika" not in body
            or "ods.od.nih.gov" not in body
            or "<!doctype" in body.casefold() or "<html" in body.casefold()
            or "5nm2022" in body.casefold()):
        raise PublishError("Source article or exact title transition changed")
    return {"post_id": POST_ID, "slug": SLUG, "url": URL,
            "title": title, "content_sha256": sha(body),
            "excerpt_sha256": sha(excerpt), "needs_write": title == OLD_TITLE}


class H1Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.current = []
        self.headings = []

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self.depth += 1
            if self.depth == 1:
                self.current = []

    def handle_data(self, data):
        if self.depth:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "h1" and self.depth:
            self.depth -= 1
            if not self.depth:
                self.headings.append(" ".join("".join(self.current).split()))


def public_title_verified(*, reader=None):
    if reader is not None:
        page = reader(URL)
        if not isinstance(page, str):
            return False
        parser = H1Parser()
        parser.feed(page)
        return parser.headings == [NEW_TITLE]
    request = urllib.request.Request(URL, headers={
        "User-Agent": "Xfit11945TitleVerification/1.0",
        "Cache-Control": "no-cache", "Pragma": "no-cache"})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                final = urllib.parse.urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https"
                        or final.hostname not in ("xfit.cz", "www.xfit.cz")
                        or final.path != "/" + SLUG + "/"
                        or final.query or final.fragment or final.username
                        or final.password or final.port):
                    raise PublishError("Unexpected public article URL or HTTP response")
                content = response.read(2_000_001)
                if len(content) > 2_000_000:
                    raise PublishError("Unexpected public page size")
                parser = H1Parser()
                parser.feed(content.decode("utf-8", errors="replace"))
                if parser.headings == [NEW_TITLE]:
                    return True
        except (OSError, ValueError) as error:
            if attempt == 7:
                raise PublishError("Public article unavailable") from error
        if attempt < 7:
            time.sleep(4)
    return False


def snapshot():
    before = classify(get_post())
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite immutable title rollback")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "purpose": "exact_creatine_11945_title_only",
        "original": before, "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "TITLE_BACKUP_READY", "post_id": POST_ID,
                      "needs_write": before["needs_write"], "remote_writes": 0}))


def apply():
    if not BACKUP.exists():
        raise PublishError("Mandatory title rollback missing")
    manifest = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("schema") != 1
            or manifest.get("purpose") != "exact_creatine_11945_title_only"
            or manifest.get("remote_writes") != 0):
        raise PublishError("Invalid immutable rollback contract")
    before = manifest.get("original")
    current = classify(get_post())
    if current != before:
        raise PublishError("Concurrent WordPress edit since title backup")
    if not current["needs_write"]:
        if not public_title_verified():
            raise PublishError("Already updated title not publicly verified")
        print(json.dumps({"state": "ALREADY_APPLIED_NO_WRITE", "post_id": POST_ID,
                          "remote_writes": 0, "url": URL}))
        return
    try:
        response = wp_request(normalized_base(), "posts/11945",
                              payload={"title": NEW_TITLE})
        if (not isinstance(response, dict) or response.get("id") != POST_ID
                or response.get("status") != "publish"):
            raise PublishError("Uncertain WordPress POST result")
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        pass  # One POST maximum: a timeout may already have committed it.
    try:
        after = classify(get_post())
    except (PublishError, OSError, ValueError, KeyError, TypeError) as error:
        raise PublishError("Uncertain title state; never blind retry") from error
    if (after["content_sha256"] != before["content_sha256"]
            or after["excerpt_sha256"] != before["excerpt_sha256"]
            or after["title"] != NEW_TITLE):
        raise PublishError("Title-only post not confirmed; never blind retry")
    if not public_title_verified():
        print(json.dumps({"state": "WP_UPDATED_PUBLIC_PENDING", "post_id": POST_ID,
                          "post_attempts": 1}))
        raise PublishError("Public H1 still stale; verify read-only later")
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID,
                      "title_changed": True, "post_attempts": 1,
                      "body_and_excerpt_preserved": True, "new_posts": 0,
                      "redirects": 0, "deletes": 0, "plugins": 0, "url": URL}))


def verify_only():
    current = classify(get_post())
    if current["title"] != NEW_TITLE or not public_title_verified():
        raise PublishError("Title not publicly verified")
    print(json.dumps({"state": "ALREADY_LIVE_VERIFIED", "post_id": POST_ID,
                      "remote_writes": 0, "url": URL}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply", "verify"):
            raise PublishError("Usage: snapshot|apply|verify")
        {"snapshot": snapshot, "apply": apply, "verify": verify_only}[sys.argv[1]]()
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        print("XFIT_11945_TITLE_ERROR: release stopped", file=sys.stderr)
        sys.exit(2)
