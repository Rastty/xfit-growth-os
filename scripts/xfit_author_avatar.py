#!/usr/bin/env python3
"""Publish the owner's Xfit editorial avatar with native WordPress REST.

Only user 1 (Redakce Xfit.cz) may be updated. No other profile field or
article is changed. No automatic retry after uncertain POST.
"""
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SLUG = "xfit-redakce-avatar-96"
IMAGE = Path("assets/branding/" + SLUG + ".jpg")
IMAGE_HASH = "b44addba8e4401239c8b153f2eca91a68942b2b78d95948a18f7844c3db2acc5"
PUBLIC_POST = "https://xfit.cz/xfit-os-jak-porovnat-cenu-sportovniho-napoje/"
BASE = os.getenv("WP_BASE_URL", "https://xfit.cz").rstrip("/")
USERNAME = os.getenv("WP_USERNAME", "")
PASSWORD = os.getenv("WP_APP_PASSWORD", "")


def fail(reason):
    raise RuntimeError(reason)


def request(path, method="GET", payload=None, content_type="application/json"):
    if not USERNAME or not PASSWORD:
        fail("Missing WordPress application credentials")
    parsed = urllib.parse.urlsplit(BASE)
    if parsed.scheme != "https" or parsed.hostname not in ("xfit.cz", "www.xfit.cz") or parsed.path or parsed.port:
        fail("WordPress base URL is not the approved Xfit host")
    auth = base64.b64encode((USERNAME + ":" + PASSWORD).encode()).decode()
    headers = {
        "Authorization": "Basic " + auth,
        "Accept": "application/json",
        "User-Agent": "XfitAvatarRelease/1.0",
    }
    if payload is not None:
        headers["Content-Type"] = content_type
        if content_type == "image/jpeg":
            headers["Content-Disposition"] = 'attachment; filename="' + SLUG + '.jpg"'
        else:
            payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + "/wp-json/wp/v2/" + path, data=payload,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            if urllib.parse.urlsplit(response.geturl()).hostname not in ("xfit.cz", "www.xfit.cz"):
                fail("WordPress REST response left approved domain")
            return json.load(response)
    except urllib.error.HTTPError as exc:
        fail("WordPress REST " + method + " failed with HTTP " + str(exc.code))


def assert_public_avatar():
    for attempt in range(3):
        req = urllib.request.Request(PUBLIC_POST, headers={
            "Cache-Control":"no-cache", "User-Agent":"XfitAvatarRelease/1.0"
        })
        with urllib.request.urlopen(req, timeout=35) as response:
            if response.status != 200 or urllib.parse.urlsplit(response.geturl()).hostname not in ("xfit.cz","www.xfit.cz"):
                fail("Public article host or response changed")
            body = response.read(2000000).decode("utf-8", errors="replace")
        start = body.find('class="author-box-wrap"')
        if start >= 0 and SLUG in body[start:start+2200]:
            return True
        if attempt < 2:
            time.sleep(3)
    return False


def main():
    img = IMAGE.read_bytes()
    if hashlib.sha256(img).hexdigest() != IMAGE_HASH or not img.startswith(b"\\xff\\xd8") or not img.endswith(b"\\xff\\xd9"):
        fail("Avatar image bytes differ from reviewed source")
    current = request("users/me?context=edit&_fields=id,name")
    if current.get("id") != 1:
        fail("Publishing account is not the Redakce/admin author (ID 1)")
    user = request("users/1?context=edit&_fields=id,name,simple_local_avatar,avatar_urls")
    if user.get("id") != 1:
        fail("Redakce user not found")
    already = user.get("simple_local_avatar") or {}
    media_id = already.get("media_id") if isinstance(already, dict) and SLUG in str(already.get("full", "")) else None

    if media_id is None:
        matches = request("media?context=edit&per_page=10&slug=" + SLUG +
                          "&_fields=id,slug,author,media_type,source_url")
        if len(matches) > 1:
            fail("More than one staged Xfit avatar media entry; manual review")
        if matches:
            item = matches[0]
            if item.get("author") != 1 or item.get("media_type") != "image":
                fail("Staged avatar is not owned by Redakce/admin")
            media_id = item["id"]
        else:
            uploaded = request("media", method="POST", payload=img, content_type="image/jpeg")
            media_id = uploaded.get("id")
            if not isinstance(media_id, int) or uploaded.get("author") != 1:
                fail("Media upload did not return an attachment owned by admin")
            request("media/" + str(media_id), method="POST", payload={
                "title": "Redakce Xfit.cz - profilovy avatar",
                "alt_text": "Redakce Xfit.cz - redakcni tym",
                "description": "Oficialni fotografie tymu pro autorsky box clanku."
            })
        updated = request("users/1", method="POST",
                          payload={"simple_local_avatar": {"media_id": media_id}})
        if updated.get("id") != 1:
            fail("WordPress did not update selected author")
    read = request("users/1?context=edit&_fields=id,simple_local_avatar,avatar_urls")
    local = read.get("simple_local_avatar") or {}
    if str(local.get("media_id")) != str(media_id):
        fail("Avatar plugin did not confirm media ID")
    urls = read.get("avatar_urls") or {}
    if not any("xfit-redakce" in str(url) for url in urls.values()):
        fail("Avatar URL readback does not point to the uploaded Xfit photo")
    proof = assert_public_avatar()
    receipt = {"author_id": 1, "author": "Redakce Xfit.cz",
               "media_id": media_id, "public_article": PUBLIC_POST,
               "wp_user_avatar_verified": True, "public_box_verified": proof}
    print(json.dumps(receipt, ensure_ascii=False))
    if not proof:
        fail("WP avatar updated but public author-box HTML is stale; cache review required")


if __name__ == "__main__":
    main()
