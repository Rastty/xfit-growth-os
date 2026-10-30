#!/usr/bin/env python3
"""One-time, tightly scoped slug collision repair for the first Xfit article."""
import json
import sys
from scripts.wp_publish import MARKER, PublishError, existing_content, normalized_base, verify_public, wp_request

DRAFT_ID = 25450
PUBLIC_ID = 25451
TARGET = "xfit-os-protein-guide"
BACKUP = "xfit-os-protein-guide-initial-draft"


def read_post(base, post_id):
    return wp_request(base, "posts/" + str(post_id) + "?context=edit&_fields=id,slug,status,content,link,title")


def main():
    base = normalized_base()
    draft, live = read_post(base, DRAFT_ID), read_post(base, PUBLIC_ID)
    if draft.get("id") != DRAFT_ID or live.get("id") != PUBLIC_ID:
        raise PublishError("Unexpected article IDs")
    if MARKER not in existing_content(draft) or MARKER not in existing_content(live):
        raise PublishError("Ownership marker missing; refusing slug repair")
    if draft.get("status") != "draft" or live.get("status") != "publish":
        raise PublishError("Unexpected publication states")
    if draft.get("slug") == TARGET and live.get("slug") == TARGET + "-2":
        a = wp_request(base, "posts/" + str(DRAFT_ID), payload={"slug": BACKUP})
        if a.get("slug") != BACKUP:
            raise PublishError("Could not move draft slug")
        b = wp_request(base, "posts/" + str(PUBLIC_ID), payload={"slug": TARGET})
        if b.get("slug") != TARGET:
            raise PublishError("Could not set canonical slug")
    elif not (draft.get("slug") == BACKUP and live.get("slug") == TARGET):
        raise PublishError("Unexpected existing slugs: refusing mutation")
    check = read_post(base, PUBLIC_ID)
    if check.get("slug") != TARGET or check.get("status") != "publish":
        raise PublishError("Canonical slug verification failed")
    link = check.get("link")
    if not isinstance(link, str):
        raise PublishError("No published article permalink")
    print(json.dumps({"state": "canonical_slug_api_verified", "id": PUBLIC_ID, "url": link}, ensure_ascii=False))
    try:
        verify_public(link, "Jak vybrat protein: přehled druhů, výpočet ceny a praktické rozhodování")
    except PublishError as ex:
        print("PUBLIC_CHECK_FAILED: " + str(ex), file=sys.stderr)
        return 3
    print(json.dumps({"state": "live_verified", "id": PUBLIC_ID, "url": link}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PublishError as exc:
        print("RECONCILE_ERROR: " + str(exc), file=sys.stderr)
        sys.exit(2)
