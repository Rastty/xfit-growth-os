"""Fail-closed one-time WordPress primary-menu link to existing reader-first guide.

Never modify theme files, reorder existing items, or create a new article.
Requires one exact public primary/header menu with four existing navigation
titles already observed on xfit.cz. Backup menu state before one possible POST.
"""
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

from scripts.wp_publish import PublishError, normalized_base, wp_request

DEST = "https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/"
TITLE = "Vybrat doplněk"
KNOWN_HEADER = {"Výživa", "Kulturistika & fitness", "Sporty", "Anatomie"}
BACKUP = Path("reports/backups/xfit-main-nav-decision-20261121.json")
SITE = "https://xfit.cz/"
MAX_MENU_ITEMS = 99


def normalized_title(value):
    if isinstance(value, dict):
        value = value.get("raw") or value.get("rendered")
    return " ".join(unescape(value or "").split())


def menu_projection(items):
    if not isinstance(items, list) or len(items) > MAX_MENU_ITEMS:
        raise PublishError("Menu item inventory missing or paginated")
    rows = []
    for item in items:
        if not isinstance(item, dict) or type(item.get("id")) is not int:
            raise PublishError("Malformed menu item")
        rows.append({
            "id": item["id"],
            "title": normalized_title(item.get("title")),
            "url": item.get("url") or "",
            "menus": item.get("menus"),
            "parent": item.get("parent", 0),
            "menu_order": item.get("menu_order"),
            "status": item.get("status"),
        })
    return sorted(rows, key=lambda row: row["id"])


def fetch_menu_items(menu_id):
    return wp_request(
        normalized_base(),
        "menu-items?" + urllib.parse.urlencode({
            "context": "edit", "menus": menu_id, "per_page": 100,
            "_fields": "id,menus,parent,menu_order,title,url,status",
        }),
    )


def choose_header_menu(*, fetch=wp_request):
    menus = fetch(
        normalized_base(),
        "menus?context=edit&per_page=100&_fields=id,slug,name,locations",
    )
    if not isinstance(menus, list) or not menus or len(menus) >= 100:
        raise PublishError("No complete WordPress menu inventory")
    candidates = []
    for menu in menus:
        if type(menu.get("id")) is not int:
            continue
        locs = menu.get("locations")
        if not isinstance(locs, list) or not any(
            isinstance(loc, str) and
            any(key in loc.casefold() for key in ("header", "primary", "main"))
            for loc in locs
        ):
            continue
        items = menu_projection(fetch_menu_items(menu["id"]))
        headings = {row["title"] for row in items if row["parent"] == 0}
        if KNOWN_HEADER.issubset(headings):
            candidates.append((menu["id"], items))
    if len(candidates) != 1:
        raise PublishError("Primary public menu cannot be identified uniquely")
    ident, items = candidates[0]
    if any(row["url"].rstrip("/") == DEST.rstrip("/") and
           row["title"] != TITLE for row in items):
        raise PublishError("Target already linked under a different label")
    return ident, items


def assert_public_guide():
    # Direct same-origin WordPress REST post GET; no new page is created.
    posts = wp_request(
        normalized_base(),
        "posts?" + urllib.parse.urlencode({
            "slug": "xfit-os-doplnky-pro-zacatecniky",
            "status": "publish", "context": "edit", "per_page": 2,
            "_fields": "id,slug,link,status",
        }),
    )
    if (not isinstance(posts, list) or len(posts) != 1 or
            posts[0].get("status") != "publish" or posts[0].get("link") != DEST):
        raise PublishError("Destination guide is not uniquely published")


class HeaderLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.targets = []
        self._href = None
        self._buffer = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        signature = " ".join((d.get("id") or "", d.get("class") or "")).casefold()
        self.stack.append((tag, signature))
        context = any(t in ("nav", "header") or
                      "header-menu" in a or "td-header" in a or
                      "menu-header" in a for t, a in self.stack)
        if tag == "a" and context:
            self._href = d.get("href")
            self._buffer = []

    def handle_data(self, data):
        if self._href is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.targets.append((self._href, " ".join("".join(self._buffer).split())))
            self._href = None
        if self.stack:
            for n in range(len(self.stack)-1, -1, -1):
                if self.stack[n][0] == tag:
                    self.stack = self.stack[:n]
                    break


def public_header_verified(*, reader=None):
    if reader is None:
        request = urllib.request.Request(SITE, headers={
            "User-Agent": "XFITHeaderMenuGETOnly/1.0",
            "Cache-Control": "no-cache", "Pragma": "no-cache",
        }, method="GET")
        with urllib.request.urlopen(request, timeout=25) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if (response.status != 200 or final.scheme != "https" or
                    final.hostname not in ("xfit.cz", "www.xfit.cz") or
                    final.path not in ("", "/") or final.query or final.fragment or
                    final.username or final.password or final.port):
                raise PublishError("Homepage public URL verification failed")
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise PublishError("Homepage HTML oversized")
            html = raw.decode("utf-8", errors="replace")
    else:
        html = reader(SITE)
    p = HeaderLinks()
    p.feed(html)
    return (DEST, TITLE) in p.targets


def snapshot():
    assert_public_guide()
    menu_id, items = choose_header_menu()
    if BACKUP.exists():
        raise PublishError("Already saved one-time backup; no overwrite")
    preexisting = [item for item in items if item["url"].rstrip("/") == DEST.rstrip("/")]
    if preexisting and preexisting[0]["title"] != TITLE:
        raise PublishError("Unexpected preexisting destination label")
    mode = "already_linked" if len(preexisting) == 1 else "create"
    if len(preexisting) > 1:
        raise PublishError("Repeated link in original menu")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "menu_id": menu_id, "items": items,
        "mode": mode, "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY_NO_POST", "menu_id": menu_id,
                      "original_item_count": len(items), "mode": mode,
                      "wordpress_writes": 0}))


def apply():
    if not BACKUP.is_file():
        raise PublishError("Missing full menu rollback")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (saved.get("schema") != 1 or saved.get("remote_writes") != 0 or
            saved.get("mode") not in ("create", "already_linked") or
            type(saved.get("menu_id")) is not int or
            not isinstance(saved.get("items"), list)):
        raise PublishError("Invalid menu prewrite manifest")
    menu_id, before = choose_header_menu()
    if menu_id != saved["menu_id"] or before != saved["items"]:
        raise PublishError("Concurrent menu editor drift; no POST")
    if saved["mode"] == "already_linked":
        if not public_header_verified():
            raise PublishError("Link exists in WP menu but is not confirmed in header")
        print(json.dumps({"state": "ALREADY_VISIBLE_NO_WRITE",
                          "menu_id": menu_id, "wordpress_writes": 0}))
        return
    order = max([int(row["menu_order"] or 0) for row in before] + [0]) + 1
    try:
        wp_request(normalized_base(), "menu-items", payload={
            "title": TITLE, "url": DEST, "type": "custom",
            "menus": menu_id, "status": "publish", "parent": 0,
            "menu_order": order,
        })
    except (PublishError, OSError, TypeError, ValueError):
        pass  # Possible committed POST; do NOT try again.
    try:
        after = menu_projection(fetch_menu_items(menu_id))
    except (PublishError, OSError, TypeError, ValueError) as exc:
        raise PublishError("Post-write menu state unknown; no retry") from exc
    originals = [x for x in after if x["id"] in {j["id"] for j in before}]
    new = [x for x in after if x["id"] not in {j["id"] for j in before}]
    if (originals != before or len(new) != 1 or new[0]["title"] != TITLE or
            new[0]["url"] != DEST or new[0]["menus"] != menu_id or
            new[0]["parent"] != 0 or new[0]["status"] != "publish"):
        raise PublishError("Menu POST outcome or existing items changed; no retry")
    if not public_header_verified():
        raise PublishError("WordPress menu changed, public header not yet verified; no retry")
    print(json.dumps({"state": "PUBLIC_HEADER_VERIFIED", "menu_id": menu_id,
                      "menu_item_id": new[0]["id"], "wordpress_writes": 1,
                      "new_posts": 0, "existing_menu_items_changed": 0,
                      "url": DEST}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, TypeError, ValueError, KeyError) as exc:
        print("XFIT_PRIMARY_MENU_ERROR: " + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
