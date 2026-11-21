#!/usr/bin/env python3
"""Replace the redundant opening navigation in the EXISTING XFIT beginner hub.

One precisely guarded WordPress article (#25458), not a new page or plugin.
The existing longform educational guide stays intact; one opening two-paragraph
navigation is replaced with a single transparent three-way decision surface.

A required complete rollback artifact is uploaded BEFORE the one possible POST.
WP source is leased both against the previously approved Git ready file and
against the exact just-backed-up edit-context source. No POST retries.
"""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import (
    MARKER, PublishError, validate_document, assert_prewrite_source,
    normalized_base, wp_request, normalize_visible, article_visible,
    editorial_links, verify_public,
)
from scripts.xfit_home_sticky_guide_onepost import (
    homepage_get, card_rank,
)
from scripts.xfit_supplements_category_hub_onepost import (
    category_public_get, archive_rank,
)

POST_ID = 25458
SLUG = "xfit-os-doplnky-pro-zacatecniky"
URL = "https://xfit.cz/" + SLUG + "/"
CATEGORY_ID = 44
GUIDE = Path("content/ready/xfit-os-doplnky-pro-zacatecniky.json")
BACKUP = Path("reports/backups/xfit-beginner-hub-choice-strip-20261121.json")
OLD_START = "<p><strong>Rychlá navigace:</strong>"
END_NEXT_SECTION = '<h2 id="zacatecnik-rozhodnuti">'
REVISION_MARKER = 'id="xfit-rychla-volba-20261121"'
MERCHANTS = ("namaximum.cz", "www.namaximum.cz")
CHOICES = (
    "#zacatecnik-rozhodnuti",
    "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
    "https://xfit.cz/xfit-os-kreatin-poradce/",
    "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
)
NEW_NAV = """<section id="xfit-rychla-volba-20261121" aria-label="První krok: doplňky stravy pro začátečníky" style="border:1px solid #dbe5e2;border-radius:12px;padding:18px;margin:20px 0;background:#f6faf8">
<h2 style="margin:0 0 8px">Co potřebujete právě teď?</h2>
<p style="margin:0 0 14px">Vyberte si jednu cestu. Pokud doplňky zatím nepotřebujete, nemusíte nic kupovat.</p>
<p style="margin:0 0 8px"><a href="#zacatecnik-rozhodnuti" style="display:block;padding:12px 14px;border-radius:8px;background:#fff;border:1px solid #cdded7"><strong>Začínám cvičit – bez nákupu</strong><span style="display:block">Nejdřív návyky, jídlo a trénink</span></a></p>
<p style="margin:0 0 8px"><a href="https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/" style="display:block;padding:12px 14px;border-radius:8px;background:#fff;border:1px solid #cdded7"><strong>Hledám protein</strong><span style="display:block">Porovnat balení, cenu a alergeny</span></a></p>
<p style="margin:0 0 8px"><a href="https://xfit.cz/xfit-os-kreatin-poradce/" style="display:block;padding:12px 14px;border-radius:8px;background:#fff;border:1px solid #cdded7"><strong>Hledám kreatin</strong><span style="display:block">Porovnat monohydrát a cenu za 100 g</span></a></p>
<p style="margin:12px 0 0"><strong>Ještě nevím, co má smysl?</strong> <a href="https://xfit.cz/xfit-os-kreatin-nebo-protein/">Pomůže průvodce kreatin versus protein, včetně možnosti nekupovat nic.</a></p>
</section>
"""


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ready():
    data = json.loads(GUIDE.read_text(encoding="utf-8"))
    doc = validate_document(data)
    if doc["slug"] != SLUG or not isinstance(doc["title"], str):
        raise PublishError("Unreviewed existing guide source")
    if doc["content"].count(OLD_START) != 1 or doc["content"].count(END_NEXT_SECTION) != 1:
        raise PublishError("Previous Git source nav pattern not unique")
    return doc


def source_get():
    return wp_request(
        normalized_base(),
        "posts/" + str(POST_ID) +
        "?context=edit&_fields=id,slug,status,sticky,link,title,content,excerpt,categories,modified_gmt",
    )


def identity(post):
    if not isinstance(post, dict):
        raise PublishError("Expected exactly one published existing guide")
    title = (post.get("title") or {}).get("raw")
    raw = (post.get("content") or {}).get("raw")
    excerpt = (post.get("excerpt") or {}).get("raw")
    categories = post.get("categories")
    if (type(post.get("id")) is not int or post["id"] != POST_ID
            or post.get("slug") != SLUG or post.get("link") != URL
            or post.get("status") != "publish"
            or post.get("sticky") is not True
            or not isinstance(title, str)
            or not isinstance(raw, str) or not 4000 <= len(raw) <= 30000
            or not isinstance(excerpt, str)
            or not isinstance(categories, list) or
            CATEGORY_ID not in categories or
            len(categories) != len(set(categories)) or len(categories) > 20
            or any(type(v) is not int or v <= 0 for v in categories)
            or not isinstance(post.get("modified_gmt"), str)
            or not post["modified_gmt"]):
        raise PublishError("Pinned guide/category/sticky/identity drift")
    return post


def revised_from_original(post, old_doc):
    post = identity(post)
    assert_prewrite_source(post, old_doc)
    raw = post["content"]["raw"]
    if REVISION_MARKER in raw or raw.count(OLD_START) != 1 or raw.count(END_NEXT_SECTION) != 1:
        raise PublishError("Navigation already revised or changed by another editor")
    a = raw.index(OLD_START)
    b = raw.index(END_NEXT_SECTION)
    if not 200 < a < b < 6500:
        raise PublishError("Original navigation not in expected early content")
    original_block = raw[a:b]
    expected = old_doc["content"]
    x = expected.index(OLD_START)
    y = expected.index(END_NEXT_SECTION)
    if (article_visible(original_block)[0] != article_visible(expected[x:y])[0]
            or editorial_links(original_block) != editorial_links(expected[x:y])):
        raise PublishError("Opening nav or outbound routes changed")
    # Never turn a first-party educational page into a direct merchant
    # affiliate landing; these are only previously published XFIT guides.
    assert all("namaximum" not in link for link in CHOICES)
    updated = raw[:a] + NEW_NAV + raw[b:]
    if (updated.count(REVISION_MARKER) != 1
            or len(updated) > 35000
            or old_doc["slug"] != post["slug"]
            or editorial_links(updated).count(CHOICES[1]) < 2
            or editorial_links(updated).count(CHOICES[2]) < 2
            or any("namaximum.cz" in link for link in editorial_links(updated))):
        raise PublishError("Unexpected editorial decision link mutation")
    # The remainder of the original article must remain byte-for-byte.
    if not updated.endswith(raw[b:]) or not updated.startswith(raw[:a]):
        raise PublishError("Nonlocal article edit refused")
    return updated


def preserve_unchanged(before, after):
    a, b = dict(before), dict(after)
    for key in ("content", "modified_gmt"):
        a.pop(key, None)
        b.pop(key, None)
    return a == b


class PublicChoiceLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_section = False
        self.depth = 0
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "section":
            if self.in_section:
                self.depth += 1
            elif a.get("id") == "xfit-rychla-volba-20261121":
                self.in_section = True
                self.depth = 1
        if tag == "a" and self.in_section:
            self.hrefs.append(a.get("href"))

    def handle_endtag(self, tag):
        if tag == "section" and self.in_section:
            self.depth -= 1
            if not self.depth:
                self.in_section = False


def public_links():
    req = Request(URL, method="GET", headers={
        "User-Agent": "XFITChoiceStripVerify/1.0",
        "Cache-Control": "no-cache", "Pragma": "no-cache",
    })
    with urlopen(req, timeout=25) as res:
        parsed = urlsplit(res.geturl())
        if (res.status != 200 or parsed.scheme != "https"
                or parsed.hostname not in ("xfit.cz", "www.xfit.cz")
                or parsed.username or parsed.password or parsed.port
                or parsed.path != "/" + SLUG + "/"
                or parsed.query or parsed.fragment):
            raise PublishError("Unexpected public guide identity")
        raw = res.read(2_000_001)
        if len(raw) > 2_000_000:
            raise PublishError("Public guide too large")
        parser = PublicChoiceLinks()
        parser.feed(raw.decode("utf-8", errors="replace"))
        return parser.hrefs


def snapshot():
    old = ready()
    current = identity(source_get())
    revised = revised_from_original(current, old)
    home = card_rank(homepage_get())
    archive = archive_rank(category_public_get())
    if home != 1 or archive != 1:
        raise PublishError("Existing homepage/category first-card growth lost")
    if BACKUP.exists():
        raise PublishError("Never overwrite first original article backup")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "before": current, "post_id": POST_ID,
        "raw_sha256": sha(current["content"]["raw"]),
        "updated_sha256": sha(revised),
        "previous_home_rank": home, "previous_category_rank": archive,
        "wordpress_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "state": "FULL_SOURCE_BACKUP_READY_NO_WRITE",
        "post_id": POST_ID, "previous_home_rank": home,
        "previous_category_rank": archive, "wordpress_writes": 0,
    }), flush=True)


def apply():
    old = ready()
    if not BACKUP.is_file():
        raise PublishError("Missing original edit-context rollback")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    before = saved.get("before")
    if (saved.get("schema") != 1 or saved.get("post_id") != POST_ID
            or saved.get("wordpress_writes") != 0
            or not isinstance(before, dict)
            or not isinstance((before.get("content") or {}).get("raw"), str)
            or saved.get("raw_sha256") != sha(before["content"]["raw"])):
        raise PublishError("Untrusted rollback identity")
    approved = revised_from_original(before, old)
    if saved.get("updated_sha256") != sha(approved):
        raise PublishError("Approved update changed after backup")
    current = source_get()
    if current != before:
        raise PublishError("Concurrent content or category change before POST")
    if (card_rank(homepage_get()) != saved["previous_home_rank"] or
            archive_rank(category_public_get()) != saved["previous_category_rank"]):
        raise PublishError("Public discovery path changed before POST")
    print(json.dumps({"state": "ONE_EDIT_POST_ATTEMPT_START", "post_id": POST_ID}), flush=True)
    try:
        wp_request(normalized_base(), "posts/" + str(POST_ID),
                   payload={"content": approved})
    except (PublishError, OSError, ValueError, TypeError):
        pass  # Unknown POST outcome: never retry.
    try:
        after = identity(source_get())
    except (PublishError, OSError, ValueError, TypeError) as exc:
        raise PublishError("POST uncertain and cannot re-read; no retry") from exc
    if (not preserve_unchanged(before, after)
            or article_visible(after["content"]["raw"])[0] != article_visible(approved)[0]
            or editorial_links(after["content"]["raw"]) != editorial_links(approved)):
        raise PublishError("WordPress content or metadata not proven exact; no retry")
    print(json.dumps({"state": "WP_REVISED_SOURCE_VERIFIED", "post_id": POST_ID}), flush=True)
    verify_public(URL, old["title"], approved)
    rendered = public_links()
    if rendered != list(CHOICES):
        raise PublishError("Public three-way first-party navigation not verified")
    home = card_rank(homepage_get())
    category = archive_rank(category_public_get())
    if home != 1 or category != 1:
        raise PublishError("Homepage or category first-card discovery lost")
    print(json.dumps({
        "state": "PUBLIC_THREE_WAY_DECISION_VERIFIED",
        "post_id": POST_ID, "new_pages": 0, "redirects": 0,
        "post_attempts": 1, "guide_home_rank": home,
        "guide_category_rank": category,
        "public_first_party_choices": len(CHOICES),
        "original_categories_sticky_title_excerpt_preserved": True,
        "url": URL,
    }), flush=True)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply"):
            raise PublishError("Usage snapshot|apply")
        (snapshot if sys.argv[1] == "snapshot" else apply)()
    except (PublishError, OSError, ValueError, TypeError, KeyError):
        print("XFIT_BEGINNER_DECISION_ERROR: PREWRITE_OR_POSTREAD_GUARD", file=sys.stderr)
        sys.exit(2)
