"""One exact Xfit WP 3660 title update justified by observed GSC query intent.

Only title changes. Every existing HTML byte, excerpt, slug, canonical URL,
affiliate link and WordPress status must remain unchanged. Mandatory rollback
manifest and one POST at most. Never blind-retry a timed-out write.
"""
import hashlib
from html.parser import HTMLParser
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.wp_publish import PublishError, normalized_base, wp_request

POST_ID = 3660
SLUG = "jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates"
URL = "https://xfit.cz/" + SLUG + "/"
OLD_TITLE = "Jaký je rozdíl mezi klasickým pilates a power pilates"
NEW_TITLE = "Co je power pilates? Rozdíl oproti klasickému pilates"
BACKUP = Path("reports/backups/xfit-pilates-gsc-title-3660.json")


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_post():
    return wp_request(normalized_base(), "posts/" + str(POST_ID) +
                      "?context=edit&_fields=id,slug,status,title,content,excerpt,link")


def classify(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("status") != "publish"
            or post.get("slug") != SLUG or post.get("link") != URL):
        raise PublishError("Unexpected owned WordPress identity/status/canonical URL")
    title = (post.get("title") or {}).get("raw")
    if not isinstance(title, str) or title not in (OLD_TITLE, NEW_TITLE):
        raise PublishError("Live title differs from exact GSC-approved transition")
    content = (post.get("content") or {}).get("raw")
    excerpt = (post.get("excerpt") or {}).get("raw")
    if (not isinstance(content, str) or len(content) < 3000
            or len(content.encode("utf-8")) > 200000
            or not isinstance(excerpt, str)
            or "Rozdíl mezi klasickým pilates a power pilates" not in content):
        raise PublishError("Source text unexpectedly missing or changed")
    return {
        "post_id": POST_ID, "slug": SLUG, "url": URL,
        "old_title": title, "desired_title": NEW_TITLE,
        "content_sha256": sha(content), "excerpt_sha256": sha(excerpt),
        "write_needed": title == OLD_TITLE,
    }


class H1Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.headings = []
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self.depth += 1
            if self.depth == 1:
                self.buffer = []

    def handle_data(self, data):
        if self.depth:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "h1" and self.depth:
            self.depth -= 1
            if not self.depth:
                self.headings.append(" ".join("".join(self.buffer).split()))


def public_title_verified(*, reader=None):
    if reader is not None:
        body = reader(URL)
        if not isinstance(body, str):
            return False
        parser = H1Reader()
        parser.feed(body)
        return parser.headings == [NEW_TITLE]
    req = urllib.request.Request(URL, headers={
        "User-Agent": "XfitGSCOneTitleVerification/1.0",
        "Cache-Control": "no-cache", "Pragma": "no-cache",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                final = urllib.parse.urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https"
                        or final.hostname not in ("xfit.cz", "www.xfit.cz")
                        or final.username or final.password or final.port
                        or final.query or final.fragment
                        or final.path != "/" + SLUG + "/"):
                    raise PublishError("Public article path or redirect changed")
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise PublishError("Public response too large")
                parser = H1Reader()
                parser.feed(data.decode("utf-8", errors="replace"))
                if parser.headings == [NEW_TITLE]:
                    return True
        except (OSError, ValueError) as error:
            if attempt == 2:
                raise PublishError("Public page readback unavailable") from error
        if attempt < 2:
            time.sleep(4)
    return False


def snapshot():
    before = classify(get_post())
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite one-time rollback manifest")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "purpose": "gsc_exact_query_one_existing_title",
        "source_run": 42470121265,
        "original": before, "remote_writes": 0,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"state": "TITLE_BACKUP_READY", "post_id": POST_ID,
                      "write_needed": before["write_needed"],
                      "remote_writes": 0}))


def apply():
    if not BACKUP.exists():
        raise PublishError("Mandatory prewrite rollback manifest missing")
    manifest = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("schema") != 1
            or manifest.get("purpose") != "gsc_exact_query_one_existing_title"
            or manifest.get("source_run") != 42470121265
            or manifest.get("remote_writes") != 0):
        raise PublishError("Unexpected rollback contract")
    previous = manifest.get("original")
    current = classify(get_post())
    if current != previous:
        raise PublishError("Source, title, URL or excerpt changed since snapshot")
    if not current["write_needed"]:
        if not public_title_verified():
            raise PublishError("WordPress title already changed but public H1 not verified")
        print(json.dumps({"state": "ALREADY_APPLIED_NO_WRITE", "post_id": POST_ID,
                          "public_site_modified": False, "post_attempts": 0, "url": URL}))
        return

    # One and only one title-only REST request; a timeout might have committed.
    try:
        response = wp_request(normalized_base(), "posts/" + str(POST_ID),
                              payload={"title": NEW_TITLE})
        if (not isinstance(response, dict) or response.get("id") != POST_ID
                or response.get("status") != "publish"):
            raise PublishError("WordPress POST response identity uncertain")
    except (PublishError, OSError, ValueError, TypeError, KeyError):
        pass  # Always reconcile with a new authenticated GET; never repeat POST.

    try:
        final = classify(get_post())
    except (PublishError, OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"state": "BLOCKED_UNCERTAIN_READBACK", "post_id": POST_ID}))
        raise PublishError("Cannot reconcile attempted title POST") from error
    if (final["content_sha256"] != previous["content_sha256"]
            or final["excerpt_sha256"] != previous["excerpt_sha256"]):
        raise PublishError("Article body or excerpt changed unexpectedly")
    if final["old_title"] == OLD_TITLE:
        print(json.dumps({"state": "UNRESOLVED_UNCHANGED", "post_id": POST_ID,
                          "post_attempts": 1, "public_site_modified": False}))
        raise PublishError("Title update not committed; no blind retry")
    if final["old_title"] != NEW_TITLE:
        raise PublishError("Unexpected title after POST")

    if not public_title_verified():
        print(json.dumps({"state": "WP_UPDATED_PUBLIC_STALE", "post_id": POST_ID,
                          "post_attempts": 1, "public_site_modified": True}))
        raise PublishError("Public H1 not yet verified")
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID,
                      "posts_changed": 1, "post_attempts": 1, "title_changed": True,
                      "existing_html_preserved": True, "public_site_modified": True,
                      "new_posts": 0, "deletes": 0, "redirects": 0, "url": URL}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, KeyError, TypeError) as exc:
        # No input HTML, WordPress password or OAuth data in failure logs.
        print("XFIT_PILATES_TITLE_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
