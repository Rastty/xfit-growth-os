"""Onepost sitewide home-index promotion of EXISTING reader-first XFIT guide.

WordPress sticky flag is a core API feature and does not need theme/menu access.
Fail closed unless the homepage clearly contains this guide as a regular card,
the exact guide is published and non-sticky, and there are no other sticky
posts. Backup the complete source before one possible sticky-only POST.
No new content, no new redirects, no changes to product offers.
"""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import PublishError, normalized_base, wp_request, normalize_visible

POST_ID = 25458
SLUG = "xfit-os-doplnky-pro-zacatecniky"
URL = "https://xfit.cz/" + SLUG + "/"
TITLE = "Doplňky stravy pro začátečníky: co má smysl, co nekupovat a jak se rozhodnout"
BACKUP = Path("reports/backups/xfit-home-guide-sticky-20261121.json")
MAX_PUBLIC = 2_000_000


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_get():
    return wp_request(
        normalized_base(),
        "posts/" + str(POST_ID) +
        "?context=edit&_fields=id,slug,status,sticky,link,title,content,excerpt,modified_gmt",
    )


def sticky_list():
    return wp_request(
        normalized_base(),
        "posts?sticky=true&context=edit&per_page=50&_fields=id,slug,sticky",
    )


def selected(post):
    if not isinstance(post, dict):
        raise PublishError("Missing pinned published guide")
    title = (post.get("title") or {}).get("raw")
    raw = (post.get("content") or {}).get("raw")
    excerpt = (post.get("excerpt") or {}).get("raw")
    if (type(post.get("id")) is not int or post["id"] != POST_ID or
            post.get("slug") != SLUG or post.get("status") != "publish" or
            post.get("link") != URL or type(post.get("sticky")) is not bool or
            not isinstance(title, str) or
            normalize_visible(title) != normalize_visible(TITLE) or
            not isinstance(raw, str) or len(raw) < 1400 or len(raw) > 130000 or
            not isinstance(excerpt, str) or
            not isinstance(post.get("modified_gmt"), str) or
            not post["modified_gmt"] or
            "nekup" not in normalize_visible(raw) or
            "xfit-os-kreatin-nebo-protein" not in raw):
        raise PublishError("Current guide source is not reviewed published decision guide")
    return post


def sticky_ids(rows):
    if not isinstance(rows, list) or len(rows) >= 50:
        raise PublishError("Incomplete sticky post inventory")
    values = []
    for post in rows:
        if (not isinstance(post, dict) or type(post.get("id")) is not int or
                post["id"] <= 0 or post.get("sticky") is not True):
            raise PublishError("Ambiguous sticky post inventory")
        values.append(post["id"])
    if len(values) != len(set(values)):
        raise PublishError("Duplicate sticky post identities")
    return sorted(values)


class HeadlineCards(HTMLParser):
    """Only genuine anchors inside H2/H3. Ignore nav, sidebar lists and script."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading = 0
        self.skip = 0
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template", "noscript"):
            self.skip += 1
        if tag in ("h2", "h3") and not self.skip:
            self.heading += 1
        if tag == "a" and self.heading and not self.skip:
            href = dict(attrs).get("href")
            if isinstance(href, str):
                try:
                    p = urlsplit(href)
                except ValueError:
                    return
                if (p.scheme == "https" and p.hostname in ("xfit.cz", "www.xfit.cz")
                        and not p.username and not p.password and not p.port and
                        not p.query and not p.fragment and
                        p.path.startswith("/") and p.path.endswith("/")):
                    self.hrefs.append(p.path)

    def handle_endtag(self, tag):
        if tag in ("h2", "h3") and self.heading:
            self.heading -= 1
        if tag in ("script", "style", "template", "noscript") and self.skip:
            self.skip -= 1


def homepage_get():
    req = Request("https://xfit.cz/", headers={
        "User-Agent": "XFITFirstPartyGuideSticky/1.0",
        "Cache-Control": "no-cache", "Pragma": "no-cache",
    }, method="GET")
    with urlopen(req, timeout=25) as result:
        p = urlsplit(result.geturl())
        if (result.status != 200 or p.scheme != "https"
                or p.hostname not in ("xfit.cz", "www.xfit.cz")
                or p.path != "/" or p.query or p.fragment
                or p.username or p.password or p.port):
            raise PublishError("Homepage redirected or unavailable")
        html = result.read(MAX_PUBLIC + 1)
        if len(html) > MAX_PUBLIC:
            raise PublishError("Homepage too large for safe heading probe")
        return html.decode("utf-8", errors="replace")


def card_rank(html):
    if not isinstance(html, str) or len(html) < 250:
        raise PublishError("No usable public homepage")
    cards = HeadlineCards()
    cards.feed(html)
    unique = list(dict.fromkeys(cards.hrefs))
    if len(unique) < 8 or len(unique) > 200:
        raise PublishError("Homepage card-list shape unknown")
    path = "/" + SLUG + "/"
    return unique.index(path) + 1 if path in unique else None



def diagnose_readonly():
    """Classify public/home + WP sticky prewrite blocker without raw content."""
    report = {"state": "GET_ONLY_HOME_STICKY_DIAGNOSIS",
              "wordpress_writes": 0, "post_attempts": 0}
    try:
        p = source_get()
        title = (p.get("title") or {}).get("raw") if isinstance(p, dict) else None
        content = (p.get("content") or {}).get("raw") if isinstance(p, dict) else None
        report["source"] = {
            "post_id_matches": isinstance(p, dict) and p.get("id") == POST_ID,
            "slug_matches": isinstance(p, dict) and p.get("slug") == SLUG,
            "canonical_matches": isinstance(p, dict) and p.get("link") == URL,
            "published": isinstance(p, dict) and p.get("status") == "publish",
            "sticky_is_true": isinstance(p, dict) and p.get("sticky") is True,
            "sticky_is_false": isinstance(p, dict) and p.get("sticky") is False,
            "title_matches": isinstance(title, str) and
                            normalize_visible(title) == normalize_visible(TITLE),
            "raw_chars": len(content) if isinstance(content, str) else None,
            "raw_has_no_buy": isinstance(content, str) and
                              "nekup" in normalize_visible(content),
            "raw_has_decision_link": isinstance(content, str) and
                                     "xfit-os-kreatin-nebo-protein" in content,
            "excerpt_text": isinstance(p, dict) and isinstance(
                (p.get("excerpt") or {}).get("raw"), str),
            "modified_present": isinstance(p, dict) and
                                bool(p.get("modified_gmt")),
        }
    except (PublishError, OSError, ValueError, TypeError):
        report["source"] = {"state": "WP_SOURCE_GET_UNAVAILABLE"}
    try:
        ids = sticky_ids(sticky_list())
        report["sticky_inventory"] = {
            "count": len(ids),
            "only_guide_or_empty": ids in ([], [POST_ID]),
            "guide_is_sticky": POST_ID in ids,
        }
    except (PublishError, OSError, ValueError, TypeError):
        report["sticky_inventory"] = {"state": "WP_STICKY_QUERY_UNAVAILABLE"}
    try:
        html = homepage_get()
        cards = HeadlineCards()
        cards.feed(html)
        urls = list(dict.fromkeys(cards.hrefs))
        report["homepage"] = {
            "recognized_unique_h2_h3_links": len(urls),
            "guide_visible_among_cards": ("/" + SLUG + "/") in urls,
            "guide_rank": urls.index("/" + SLUG + "/") + 1
                          if "/" + SLUG + "/" in urls else None,
            "public_card_parser_ok": 8 <= len(urls) <= 200,
        }
    except (PublishError, OSError, ValueError, TypeError):
        report["homepage"] = {"state": "PUBLIC_HOME_GET_UNAVAILABLE"}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report

def snapshot():
    original = selected(source_get())
    sticky = sticky_ids(sticky_list())
    if sticky not in ([], [POST_ID]):
        raise PublishError("Other sticky posts exist; no homepage reordering")
    homepage_rank = card_rank(homepage_get())
    if homepage_rank is None:
        raise PublishError("Guide is not a visible homepage content card")
    if BACKUP.exists():
        raise PublishError("Cannot overwrite first rollback")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1,
        "post_id": POST_ID,
        "before": original,
        "body_sha256": sha(original["content"]["raw"]),
        "mode": "already_sticky" if original["sticky"] else "enable_sticky",
        "previous_sticky_ids": sticky,
        "before_home_card_rank": homepage_rank,
        "wordpress_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "STICKY_BACKUP_READY_NO_POST",
        "post_id": POST_ID, "homepage_card_rank_before": homepage_rank,
        "mode": "already_sticky" if original["sticky"] else "enable_sticky",
        "wordpress_writes": 0,
    }))


def apply():
    if not BACKUP.is_file():
        raise PublishError("Missing mandatory full-source rollback")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    before = saved.get("before")
    if (saved.get("schema") != 1 or saved.get("post_id") != POST_ID or
            saved.get("wordpress_writes") != 0 or
            saved.get("mode") not in ("already_sticky", "enable_sticky") or
            not isinstance(before, dict) or
            not isinstance(saved.get("before_home_card_rank"), int) or
            not isinstance((before.get("content") or {}).get("raw"), str) or
            saved.get("body_sha256") != sha(before["content"]["raw"])):
        raise PublishError("Rollback or public baseline incomplete")
    now = selected(source_get())
    if now != before or sticky_ids(sticky_list()) != saved["previous_sticky_ids"]:
        raise PublishError("Guide or other sticky state drifted after snapshot")
    if card_rank(homepage_get()) != saved["before_home_card_rank"]:
        raise PublishError("Homepage card order changed after snapshot")
    if saved["mode"] == "already_sticky":
        print(json.dumps({"state": "ALREADY_STICKY_NO_WRITE",
                          "post_id": POST_ID, "wordpress_writes": 0}))
        return
    # Single POST. Even timeout can mean committed. Read only to reconcile.
    try:
        wp_request(normalized_base(), "posts/" + str(POST_ID),
                   payload={"sticky": True})
    except (OSError, ValueError, PublishError, TypeError):
        pass
    try:
        after = selected(source_get())
        ids = sticky_ids(sticky_list())
    except (PublishError, OSError, ValueError, TypeError) as exc:
        raise PublishError("Sticky POST outcome unknown; do not retry") from exc
    before_no_sticky = dict(before)
    after_no_sticky = dict(after)
    before_no_sticky.pop("sticky")
    after_no_sticky.pop("sticky")
    before_no_sticky.pop("modified_gmt")
    after_no_sticky.pop("modified_gmt")
    if (after["sticky"] is not True or before_no_sticky != after_no_sticky
            or ids != [POST_ID]):
        raise PublishError("Sticky field or original content not verified; no retry")
    # This checks the REAL user-visible homepage, not merely a WordPress flag.
    current_rank = card_rank(homepage_get())
    state = ("PUBLIC_HOME_PROMOTED" if current_rank <= 3 and
             current_rank < saved["before_home_card_rank"]
             else "WP_STICKY_SET_PUBLIC_HOME_PROMOTION_UNPROVEN")
    print(json.dumps({
        "state": state, "post_id": POST_ID,
        "before_home_card_rank": saved["before_home_card_rank"],
        "after_home_card_rank": current_rank,
        "posts_created": 0, "posts_deleted": 0, "post_content_changes": 0,
        "wordpress_sticky_post_attempts": 1,
        "url": URL,
    }))
    if state != "PUBLIC_HOME_PROMOTED":
        raise PublishError("WP sticky true; public homepage not proven promoted")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply", "diagnose"):
            raise PublishError("Usage snapshot|apply|diagnose")
        (snapshot if sys.argv[1] == "snapshot" else
         diagnose_readonly if sys.argv[1] == "diagnose" else apply)()
    except (PublishError, OSError, ValueError, TypeError, KeyError):
        print("XFIT_HOME_STICKY_ERROR: SOURCE_OR_PUBLIC_GUARD", file=sys.stderr)
        sys.exit(2)
