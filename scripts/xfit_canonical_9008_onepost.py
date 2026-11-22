"""Surgical correction of one verified wrong body canonical on WP #9008.

Full original WP raw/source snapshot uploaded before the ONLY possible POST;
retains every other byte of original content, metadata, links and title.
One public HTML canonical -> correct owned URL is the acceptance criterion.
No new articles, redirects, disavow, noindex or blind POST retry.
"""
import hashlib
from html.parser import HTMLParser
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import PublishError, normalized_base, wp_request

POST_ID = 9008
SLUG = "jaky-je-nejlepsi-cas-pro-uzivani-kreatinu-v-ramci-fitness-treninku"
URL = "https://xfit.cz/" + SLUG + "/"
BACKUP = Path("reports/backups/xfit-creatine-timing-canonical-9008.json")
FIELDS = "id,slug,status,link,title,content,modified_gmt,featured_media"
MAX_BYTES = 350_000
TAG_RE = re.compile(r"<link\b[^>]{0,1600}>", re.I | re.S)
APPROVED_OLD_HOSTS = {"example.com", "www.example.com"}


def digest(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.canonical = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "link":
            return
        vals = dict(attrs)
        if "canonical" in (vals.get("rel") or "").casefold().split():
            self.canonical.append(vals.get("href", ""))

    handle_startendtag = handle_starttag


def canonicals(html):
    parser = Links()
    parser.feed(html)
    return parser.canonical


def exact_site_link(url):
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.netloc in ("xfit.cz", "www.xfit.cz")
                and p.path.rstrip("/") == "/" + SLUG
                and not p.query and not p.fragment and not p.username
                and not p.password and p.port is None)
    except ValueError:
        return False


def bogus(url):
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname in APPROVED_OLD_HOSTS
                and not p.username and not p.password and p.port is None)
    except ValueError:
        return False


def remove_one_bogus_canonical(raw):
    """Exact one token removed; any ambiguity means absolutely no WP writes."""
    if not isinstance(raw, str) or not 1000 <= len(raw.encode("utf-8")) <= MAX_BYTES:
        raise PublishError("Missing or oversized exact legacy article content")
    matches = []
    for m in TAG_RE.finditer(raw):
        links = canonicals(m.group(0))
        if len(links) > 1:
            raise PublishError("Ambiguous canonical tag")
        if links:
            matches.append((m.start(), m.end(), links[0]))
    if len(matches) != 1 or canonicals(raw) != [matches[0][2]]:
        raise PublishError("Expected exactly one raw article-body canonical")
    start, end, target = matches[0]
    if not bogus(target):
        raise PublishError("Body canonical did not target verified wrong example.com host")
    after = raw[:start] + raw[end:]
    if (after == raw or canonicals(after) or
            after.count("<link") > raw.count("<link")):
        raise PublishError("Unexpected canonical cleanup mutation")
    return after


def pinned(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish" or post.get("link") != URL
            or not exact_site_link(post.get("link"))):
        raise PublishError("Pinned creatine timing article identity changed")
    raw = (post.get("content") or {}).get("raw")
    title = (post.get("title") or {}).get("raw")
    modified = post.get("modified_gmt")
    media = post.get("featured_media")
    if (not isinstance(raw, str) or not 1000 <= len(raw.encode("utf-8")) <= MAX_BYTES
            or not isinstance(title, str)
            or "kreatin" not in title.casefold()
            or not isinstance(modified, str)
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", modified)
            or type(media) is not int):
        raise PublishError("Missing authenticated original source and metadata")
    return raw, title, modified, media


def remote():
    return wp_request(normalized_base(),
                      f"posts/{POST_ID}?context=edit&_fields={FIELDS}")


def public_page():
    req = Request(URL, headers={
        "User-Agent": "XFITCanonical9008Review/1.0",
        "Cache-Control": "no-cache", "Pragma": "no-cache",
    }, method="GET")
    with urlopen(req, timeout=25) as response:
        if response.status != 200 or not exact_site_link(response.geturl()):
            raise PublishError("Unexpected public page identity or redirect")
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise PublishError("Oversized public canonical page")
    return body.decode("utf-8", errors="replace")


def public_state(page):
    values = canonicals(page)
    good = [u for u in values if exact_site_link(u)]
    wrong = [u for u in values if bogus(u)]
    return {
        "canonical_total": len(values),
        "site_count": len(good),
        "bogus_count": len(wrong),
    }


def approved_before(page):
    state = public_state(page)
    return (state["canonical_total"] == 2
            and state["site_count"] == 1 and state["bogus_count"] == 1)


def approved_after(page):
    state = public_state(page)
    return state == {"canonical_total": 1, "site_count": 1, "bogus_count": 0}


def snapshot():
    post = remote()
    before, title, modified, media = pinned(post)
    after = remove_one_bogus_canonical(before)
    # Two independent public states: old public URL must show the *same*
    # category of confirmed defect, not merely an outdated audit from Nov 20.
    old_public = public_page()
    if not approved_before(old_public):
        raise PublishError("Public canonical source no longer matches reviewed defect")
    if BACKUP.exists():
        raise PublishError("Immutable rollback snapshot already exists")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG, "url": URL,
        "original_raw": before, "original_title": title,
        "original_sha256": digest(before),
        "modified_gmt": modified, "featured_media": media,
        "revised_sha256": digest(after),
        "reviewed_public_canonicals": public_state(old_public),
        "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "CANONICAL_9008_BACKUP_READY", "post_id": POST_ID,
        "raw_bad_canonicals": 1, "public_bad_canonicals": 1,
        "remote_writes": 0,
    }))


def deploy():
    if not BACKUP.is_file():
        raise PublishError("Original full WP rollback not uploaded")
    record = json.loads(BACKUP.read_text(encoding="utf-8"))
    current = remote()
    before, title, modified, media = pinned(current)
    after = remove_one_bogus_canonical(before)
    if (not isinstance(record, dict) or record.get("schema") != 1
            or record.get("post_id") != POST_ID or record.get("slug") != SLUG
            or record.get("url") != URL or record.get("remote_writes") != 0
            or record.get("original_raw") != before
            or record.get("original_title") != title
            or record.get("original_sha256") != digest(before)
            or record.get("modified_gmt") != modified
            or record.get("featured_media") != media
            or record.get("revised_sha256") != digest(after)
            or record.get("reviewed_public_canonicals") != {
                "canonical_total": 2, "site_count": 1, "bogus_count": 1
            }):
        raise PublishError("Concurrent WordPress editor changed source after backup")
    # No change if public page no longer proves old wrong canonical;
    # prevent a stale snapshot from making an unnecessary WP edit.
    if not approved_before(public_page()):
        raise PublishError("Live prewrite public canonical changed; no WP POST")
    uncertain = False
    try:
        response = wp_request(normalized_base(),
                              "posts/" + str(POST_ID),
                              payload={"content": after})
        if (not isinstance(response, dict) or response.get("id") != POST_ID
                or response.get("status") != "publish"):
            uncertain = True
    except (PublishError, OSError, ValueError, TypeError):
        uncertain = True
    # A timed-out POST might have committed: no automatic retry.
    try:
        readback = remote()
        actual, actual_title, _, actual_media = pinned(readback)
    except (PublishError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"state":"UNKNOWN_NO_RETRY",
                          "post_id":POST_ID,"post_attempts":1}))
        raise PublishError("Cannot authenticate postwrite canonical revision") from exc
    if (actual != after or actual_title != title or actual_media != media
            or canonicals(actual)):
        print(json.dumps({"state":"AUTH_READBACK_MISMATCH_NO_RETRY",
                          "post_id":POST_ID,"post_attempts":1}))
        raise PublishError("Postwrite article not confirmed, never retry")
    # Public cache may be stale: re-read only, no second write.
    for attempt in range(3):
        try:
            if approved_after(public_page()):
                print(json.dumps({
                    "state":"PUBLIC_CANONICAL_VERIFIED", "post_id":POST_ID,
                    "url":URL,"post_attempts":1,"posts_changed":1,
                    "old_body_canonicals_removed":1,
                    "remaining_public_canonicals":1,
                    "new_posts":0,"redirects":0,"deletes":0,
                    "write_response_uncertain":uncertain,
                    "public_site_modified":True,
                }))
                return
        except (OSError, ValueError, PublishError):
            pass
        if attempt < 2:
            time.sleep(3)
    raise PublishError("Public canonical still stale/ambiguous; no WP retry")


if __name__ == "__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","deploy"):
            raise PublishError("Usage: snapshot|deploy")
        (snapshot if sys.argv[1]=="snapshot" else deploy)()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_CANONICAL_9008_ERROR: " + type(exc).__name__,
              file=sys.stderr)
        raise SystemExit(2)
