"""One-post replacement of an obsolete Pilates equipment placeholder.

Public Pilates #3660 says the equipment selection is forthcoming, while the
matching first-party mat guide already exists and links back. Only the exact
stale paragraph is replaced; the rest of the legacy HTML remains byte-identical.
Mandatory full prewrite backup, source lease and at most one WordPress POST.
"""
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_pilates_gsc_title_release import (
    POST_ID, SLUG, URL, NEW_TITLE,
)

TARGET = "https://xfit.cz/xfit-os-vyber-podlozky-na-cviceni/"
TARGET_TITLE = "Jak vybrat podložku na domácí cvičení podle pohybu a prostoru"
OLD = (
    "Výběr vybavení připravujeme: na Xfit.cz chceme umožnit porovnání "
    "podložek a dalších pomůcek podle rozpočtu, použití a ověřených "
    "parametrů. Než dostaneme aktuální produktové feedy, nebudeme "
    "zobrazovat vymyšlené ceny ani pořadí obchodů."
)
MARKER = "xfit-pilates-mat-bridge-20261121"
NEW = (
    '<strong data-xfit-handoff="' + MARKER + '">Cvičíte pilates doma a řešíte podložku?</strong> '
    'Nejdřív se zeptejte, zda vám ji poskytne studio nebo zda vyhovuje '
    'ta, kterou už máte. Pokud si vybíráte vlastní, přečtěte si '
    '<a href="' + TARGET + '">praktického průvodce výběrem podložky '
    'pro domácí cvičení</a>: podle pohybu, místa, povrchu a skladování. '
    'Jde o postup výběru, nikoli srovnávač aktuálních cen či zásob. '
    'Novou podložku nemusíte kupovat.'
)
PARAGRAPHS = re.compile(
    r"(?P<open><p\b[^>]*>)(?P<body>.*?)(?P<close></p\s*>)",
    re.IGNORECASE | re.DOTALL,
)
BACKUP = Path("reports/backups/xfit-pilates-mat-3660.json")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def visible(value):
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", value)).split())


class PublicProof(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.h1 = []
        self._h1 = 0
        self._h1_buffer = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))
        if tag == "h1":
            self._h1 += 1
            self._h1_buffer = []

    def handle_endtag(self, tag):
        if tag == "h1" and self._h1:
            self._h1 -= 1
            self.h1.append(" ".join("".join(self._h1_buffer).split()))

    def handle_data(self, value):
        if self._h1:
            self._h1_buffer.append(value)
        self.text.append(value)


def links(value):
    read = PublicProof()
    read.feed(value)
    return read.links


def change_one_paragraph(raw):
    if not isinstance(raw, str) or not 2000 <= len(raw) <= 200000:
        raise PublishError("Unexpected Pilates source length")
    if MARKER in raw:
        if raw.count(MARKER) != 1 or TARGET not in links(raw) or OLD in visible(raw):
            raise PublishError("Partially applied Pilates handoff")
        return raw, "already_applied"
    if TARGET in links(raw):
        raise PublishError("Mat target already linked; review context, no duplicate")
    selected = [match for match in PARAGRAPHS.finditer(raw)
                if "Výběr vybavení připravujeme" in visible(match.group("body"))]
    if len(selected) != 1:
        raise PublishError("Obsolete equipment paragraph absent or duplicated")
    match = selected[0]
    # Reject unexpected embedded links, inline tags or shifted editorial claims.
    old_body = match.group("body")
    if ("<" in old_body or visible(old_body) != OLD or OLD not in visible(raw)):
        raise PublishError("Legacy paragraph differs from reviewed exact public text")
    after = (raw[:match.start("body")] + NEW +
             raw[match.end("body"):])
    if (after.count(TARGET) != 1 or after.count("Výběr vybavení připravujeme")
            or after[:match.start("body")] != raw[:match.start("body")]
            or after[match.start("body") + len(NEW):] != raw[match.end("body"):]):
        raise PublishError("Unexpected Pilates paragraph transformation")
    return after, "update"


def post_get():
    return wp_request(
        normalized_base(),
        "posts/" + str(POST_ID) +
        "?context=edit&_fields=id,slug,status,title,content,excerpt,link,modified_gmt"
    )


def identity(post):
    if (not isinstance(post, dict) or type(post.get("id")) is not int
            or post["id"] != POST_ID or post.get("slug") != SLUG
            or post.get("status") != "publish" or post.get("link") != URL):
        raise PublishError("Unexpected Pilates WP post identity")
    title = (post.get("title") or {}).get("raw")
    excerpt = (post.get("excerpt") or {}).get("raw")
    raw = (post.get("content") or {}).get("raw")
    modified = post.get("modified_gmt")
    if (title != NEW_TITLE or not isinstance(excerpt, str)
            or not isinstance(raw, str) or not isinstance(modified, str)
            or not modified):
        raise PublishError("Missing exact published title / edit-context fields")
    return raw, title, excerpt, modified


def checked_public(url, *, require_article=False, reader=None):
    allowed = TARGET if require_article else URL
    requested = urllib.parse.urlsplit(allowed)
    if reader is None:
        req = urllib.request.Request(allowed, headers={
            "User-Agent": "XfitPilatesMatInlink/1.0",
            "Accept": "text/html", "Cache-Control": "no-cache",
        }, method="GET")
        with urllib.request.urlopen(req, timeout=25) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if (response.status != 200 or final.scheme != "https"
                    or final.hostname not in ("xfit.cz", "www.xfit.cz")
                    or final.port or final.query or final.fragment
                    or final.path.rstrip("/") != requested.path.rstrip("/")):
                raise PublishError("Public URL identity or redirect mismatch")
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise PublishError("Public article too large")
            source = raw.decode("utf-8", errors="replace")
    else:
        source = reader(allowed)
    parsed = PublicProof()
    parsed.feed(source)
    if require_article:
        return parsed.h1 == [TARGET_TITLE]
    all_text = " ".join(" ".join(parsed.text).split())
    return (parsed.h1 == [NEW_TITLE] and TARGET in parsed.links
            and "Cvičíte pilates doma a řešíte podložku?" in all_text
            and "Výběr vybavení připravujeme" not in all_text)


def source_diagnosis():
    """Non-content diagnostics for the mismatched legacy source; zero writes."""
    raw, _title, _excerpt, _modified = identity(post_get())
    selected = [match for match in PARAGRAPHS.finditer(raw)
                if "Výběr vybavení připravujeme" in visible(match.group("body"))]
    metrics = {
        "state": "GET_ONLY_SOURCE_STRUCTURE",
        "post_id": POST_ID,
        "post_attempts": 0,
        "matching_paragraphs": len(selected),
        "exact_legacy_phrase_in_full_raw": OLD in visible(raw),
        "target_link_already_in_raw": TARGET in links(raw),
    }
    if len(selected) == 1:
        fragment = selected[0].group("body")
        actual = visible(fragment)
        first = next((i for i in range(min(len(actual), len(OLD)))
                      if actual[i] != OLD[i]), min(len(actual), len(OLD)))
        metrics.update({
            "body_exact_matches": actual == OLD,
            "has_inline_markup": "<" in fragment,
            "tag_names": sorted(set(re.findall(r"</?([a-zA-Z][a-zA-Z0-9-]*)\\b",
                                                  fragment)))[:12],
            "actual_visible_length": len(actual),
            "reviewed_visible_length": len(OLD),
            "first_difference_index": first if actual != OLD else None,
            "actual_diff_codepoint": ord(actual[first]) if first < len(actual) and actual != OLD else None,
            "reviewed_diff_codepoint": ord(OLD[first]) if first < len(OLD) and actual != OLD else None,
            "body_source_sha256": digest(fragment),
            "html_comment_count": len(re.findall(r"<!--.*?-->", fragment, re.DOTALL)),
            "markup_token_count": len(re.findall(r"<[^>]*>", fragment)),
            "markup_token_kinds": sorted(set(
                (("comment" if token.startswith("<!--")
                  else "closing-tag" if token.startswith("</")
                  else "tag" if token.startswith("<")
                  else "other"))
                for token in re.findall(r"<[^>]*>", fragment)
            )),
        })
    print(json.dumps(metrics, ensure_ascii=False))


def snapshot():
    post = post_get()
    raw, title, excerpt, modified = identity(post)
    after, mode = change_one_paragraph(raw)
    if mode == "update" and not checked_public(TARGET, require_article=True):
        raise PublishError("Matching mat guide is not independently public")
    if BACKUP.exists():
        raise PublishError("Existing backup cannot be overwritten")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema": 1, "post_id": POST_ID, "slug": SLUG, "url": URL,
        "original_raw": raw, "original_sha256": digest(raw),
        "replacement_sha256": digest(after), "title": title,
        "excerpt": excerpt, "modified_gmt": modified,
        "mode": mode, "remote_writes": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"state": "BACKUP_READY_NO_WRITE", "post_id": POST_ID,
                      "mode": mode, "remote_writes": 0}))


def apply():
    if not BACKUP.is_file():
        raise PublishError("Missing mandatory full-content backup")
    saved = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (saved.get("schema") != 1 or saved.get("post_id") != POST_ID
            or saved.get("slug") != SLUG or saved.get("url") != URL
            or saved.get("remote_writes") != 0
            or not isinstance(saved.get("original_raw"), str)
            or digest(saved["original_raw"]) != saved.get("original_sha256")):
        raise PublishError("Invalid source-bound backup")
    after, mode = change_one_paragraph(saved["original_raw"])
    if mode != saved.get("mode") or digest(after) != saved.get("replacement_sha256"):
        raise PublishError("Unreviewed replacement or backup drift")
    raw, title, excerpt, modified = identity(post_get())
    if (digest(raw) != saved["original_sha256"]
            or title != saved["title"] or excerpt != saved["excerpt"]
            or modified != saved["modified_gmt"]):
        raise PublishError("Live source drift since snapshot: no write")
    if mode == "already_applied":
        if not checked_public(URL):
            raise PublishError("Handoff exists in WP, public proof missing")
        print(json.dumps({"state": "ALREADY_APPLIED_NO_WRITE", "post_id": POST_ID,
                          "posts_changed": 0}))
        return
    # One POST maximum; an HTTP failure may have committed. Never retry.
    try:
        wp_request(normalized_base(), "posts/" + str(POST_ID),
                   payload={"content": after})
    except (PublishError, OSError, ValueError, TypeError):
        pass
    try:
        final, final_title, final_excerpt, _ = identity(post_get())
    except (PublishError, OSError, ValueError, TypeError) as exc:
        raise PublishError("POST outcome unknown, authenticated readback unavailable; no retry") from exc
    if final_title != title or final_excerpt != excerpt:
        raise PublishError("Post title/excerpt changed unexpectedly; no retry")
    if digest(final) != digest(after):
        raise PublishError("POST not confirmed or independent live edit; no retry")
    if not checked_public(URL):
        raise PublishError("WP post updated but public mat link unverified; no retry")
    print(json.dumps({"state": "PUBLIC_VERIFIED", "post_id": POST_ID,
                      "posts_changed": 1, "post_attempts": 1,
                      "url": URL, "new_posts": 0, "redirects": 0}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply", "diagnose"):
            raise PublishError("Usage: snapshot|apply|diagnose")
        (snapshot if sys.argv[1] == "snapshot" else
         source_diagnosis if sys.argv[1] == "diagnose" else apply)()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print("XFIT_PILATES_MAT_ERROR: " + str(exc), file=sys.stderr)
        sys.exit(2)
