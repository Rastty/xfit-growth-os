"""Three exact WordPress media alt-text corrections, with public proof.

Each attachment is reused by specified legacy articles. No content, post
status, URL, product or affiliate link is changed. No plugins are required.
"""

from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

from scripts.wp_publish import PublishError, normalized_base, wp_request


IMAGES = (
    {
        "id": 2003,
        "slug": "michael-demoya-i2gs_mtw9hm-unsplash",
        "url": "https://xfit.cz/wp-content/uploads/2023/04/michael-demoya-i2GS_MtW9hM-unsplash.jpg",
        "alt": "Muž provádí bench press s velkou činkou, žena mu pomáhá s jištěním.",
        "posts": (
            (6440, "kreatin-a-jeho-vliv-na-ledviny-a-jatra"),
            (11945, "jak-kreatin-muze-pomoci-ziskat-svalovy-objem-v-fitness"),
        ),
    },
    {
        "id": 1767,
        "slug": "bruce-mars-gjtdg6wfmlq-unsplash",
        "url": "https://xfit.cz/wp-content/uploads/2023/04/bruce-mars-gJtDg6WfMlQ-unsplash.jpg",
        "alt": "Tři ženy cvičí na podložkách a v kleku zvedají jednu nohu.",
        "posts": ((7628, "pilates-vs-kardio-co-je-lepsi-pro-hubnuti"),),
    },
    {
        "id": 1786,
        "slug": "anastase-maragos-hyve5sikmus-unsplash",
        "url": "https://xfit.cz/wp-content/uploads/2023/04/anastase-maragos-HyvE5SiKMUs-unsplash.jpg",
        "alt": "Muž ve sportovním oblečení sedí na lavičce v posilovně a drží zelenou láhev.",
        "posts": (
            (13717, "kolik-bilkovin-potrebujete-pro-budovani-svalu-pruvodce-spravnym-stravovanim"),
            (13734, "jaky-je-vyznam-proteinu-pri-nabirani-svalove-hmoty"),
        ),
    },
)
BACKUP = Path("reports/backups/xfit-three-featured-image-alts.json")


def media_state(spec):
    media_id = spec["id"]
    data = wp_request(normalized_base(), f"media/{media_id}?context=edit&_fields=id,slug,status,alt_text,source_url")
    if (not isinstance(data, dict) or type(data.get("id")) is not int
            or data["id"] != media_id or data.get("source_url") != spec["url"]
            or data.get("alt_text") not in ("", spec["alt"])):
        raise PublishError(f"Media {media_id} is unexpected or already edited by another owner")
    # The WP filename slug may differ between versions of the REST API; the
    # exact attachment ID plus image source URL are the immutable identity.
    if not isinstance(data.get("slug"), str) or not data["slug"]:
        raise PublishError("Missing media slug")
    return {key: data[key] for key in ("id", "slug", "status", "alt_text", "source_url")}


def post_states(spec):
    snapshots = []
    for post_id, slug in spec["posts"]:
        data = wp_request(normalized_base(), f"posts/{post_id}?context=edit&_fields=id,slug,status,featured_media,link")
        url = f"https://xfit.cz/{slug}/"
        if (not isinstance(data, dict) or type(data.get("id")) is not int
                or data["id"] != post_id or data.get("slug") != slug
                or data.get("status") != "publish"
                or data.get("featured_media") != spec["id"]
                or data.get("link") != url):
            raise PublishError(f"Unexpected featured image or article identity for {post_id}")
        snapshots.append({"id": post_id, "slug": slug, "url": url, "featured_media": spec["id"]})
    return snapshots


class FeaturedImageParser(HTMLParser):
    def __init__(self, image_url):
        super().__init__(convert_charrefs=True)
        self.image_url = image_url
        self.alts = []

    def handle_starttag(self, tag, attributes):
        if tag != "img":
            return
        attrs = dict(attributes)
        classes = (attrs.get("class") or "").split()
        if "entry-thumb" in classes and attrs.get("src") == self.image_url:
            self.alts.append(attrs.get("alt"))


def public_alt_verified(spec, post, *, reader=None, attempts=5):
    url = post["url"]
    for attempt in range(attempts):
        try:
            if reader is not None:
                html = reader(url)
            else:
                request = urllib.request.Request(url, headers={
                    "User-Agent": "XfitFeaturedAltCheck/1.0",
                    "Cache-Control": "no-cache", "Pragma": "no-cache"})
                with urllib.request.urlopen(request, timeout=25) as response:
                    final = urllib.parse.urlsplit(response.geturl())
                    if (response.status != 200 or final.scheme != "https"
                            or final.hostname not in ("xfit.cz", "www.xfit.cz")
                            or final.path != "/" + post["slug"] + "/"
                            or final.query or final.fragment or final.username
                            or final.password or final.port):
                        raise PublishError("Unexpected public canonical URL")
                    body = response.read(2_000_001)
                    if len(body) > 2_000_000:
                        raise PublishError("Public page HTML too large")
                    html = body.decode("utf-8", errors="replace")
            if not isinstance(html, str):
                raise PublishError("Invalid public page HTML")
            parser = FeaturedImageParser(spec["url"])
            parser.feed(html)
            if parser.alts == [spec["alt"]]:
                return True
        except (OSError, ValueError) as error:
            if attempt == attempts - 1:
                raise PublishError("Public page unavailable") from error
        if reader is not None:
            break
        if attempt < attempts - 1:
            time.sleep(5)
    return False


def snapshot():
    originals = []
    for spec in IMAGES:
        originals.append({"media": media_state(spec), "posts": post_states(spec)})
    if BACKUP.exists():
        raise PublishError("Refusing to overwrite rollback manifest")
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps({"schema": 1, "purpose": "three_exact_featured_image_alt_edits",
                                  "originals": originals}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"state": "ALT_BACKUP_READY", "ids": [s["id"] for s in IMAGES],
                      "original_blank": sum(not item["media"]["alt_text"] for item in originals),
                      "remote_writes": 0}))


def manifest():
    if not BACKUP.is_file():
        raise PublishError("Mandatory rollback manifest absent")
    data = json.loads(BACKUP.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema") != 1
            or data.get("purpose") != "three_exact_featured_image_alt_edits"
            or not isinstance(data.get("originals"), list)
            or len(data["originals"]) != len(IMAGES)):
        raise PublishError("Invalid immutable rollback manifest")
    return data["originals"]


def apply():
    originals = manifest()
    # Validate *every* attachment and associated public post before the first
    # write; any foreign edit aborts the whole run.
    states = []
    for spec, original in zip(IMAGES, originals):
        current = media_state(spec)
        if (current != original.get("media") or post_states(spec) != original.get("posts")):
            raise PublishError("Concurrent change since snapshot; no writes")
        states.append(current)
    writes = 0
    for spec, current, original in zip(IMAGES, states, originals):
        if current["alt_text"] != spec["alt"]:
            writes += 1
            try:
                response = wp_request(normalized_base(), f"media/{spec['id']}", payload={"alt_text": spec["alt"]})
                if (not isinstance(response, dict) or response.get("id") != spec["id"]):
                    raise PublishError("Uncertain media POST response")
            except (PublishError, OSError, ValueError, KeyError, TypeError):
                pass  # Never retry a POST: it may already have committed.
        # Confirm exact media identity and expected alt after one attempt.
        after = media_state(spec)
        if (after["alt_text"] != spec["alt"]
                or {k: v for k, v in after.items() if k != "alt_text"}
                != {k: v for k, v in original["media"].items() if k != "alt_text"}):
            raise PublishError("Uncertain media state after POST; stop without retry")
        for post in original["posts"]:
            if not public_alt_verified(spec, post):
                raise PublishError(f"WP media updated but public featured alt not proven on post {post['id']}")
        print(json.dumps({"state": "PUBLIC_ALT_VERIFIED", "media_id": spec["id"],
                          "articles": [p["id"] for p in original["posts"]],
                          "alt": spec["alt"], "post_attempts": int(current["alt_text"] != spec["alt"])}, ensure_ascii=False))
    print(json.dumps({"state": "ALT_RELEASE_PUBLIC_VERIFIED", "media_ids": [s["id"] for s in IMAGES],
                      "posts_verified": sum(len(s["posts"]) for s in IMAGES),
                      "remote_writes": writes, "new_posts": 0, "plugins": 0}))


def verify():
    originals = manifest()
    for spec, original in zip(IMAGES, originals):
        if media_state(spec)["alt_text"] != spec["alt"] or post_states(spec) != original["posts"]:
            raise PublishError("Media or featured post identity no longer matches")
        for post in original["posts"]:
            if not public_alt_verified(spec, post):
                raise PublishError("Public alt verification failed")
    print(json.dumps({"state": "ALT_RELEASE_READ_ONLY_VERIFIED", "media_count": len(IMAGES),
                      "posts_verified": 5, "remote_writes": 0}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("snapshot", "apply", "verify"):
            raise PublishError("Usage: snapshot|apply|verify")
        {"snapshot": snapshot, "apply": apply, "verify": verify}[sys.argv[1]]()
    except (PublishError, OSError, ValueError, KeyError, TypeError):
        print("XFIT_FEATURED_ALT_RELEASE_ERROR: stopped; inspect the immutable backup", file=sys.stderr)
        sys.exit(2)
