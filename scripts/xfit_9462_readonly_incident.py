"""No-write evidence after the ambiguous single WordPress POST for #9462.

Uses authenticated ordinary and cache-busted GET, revision list and independent
public REST/page. Never submits a payload; emits only identity and fingerprints.
"""
import json
import time

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts import xfit_japanese_exercise_9462 as article

FIELDS = "id,slug,status,title,link,modified_gmt,content"


def fingerprint(post):
    if not isinstance(post, dict):
        raise PublishError("Unexpected authenticated post")
    body = (post.get("content") or {}).get("raw")
    if not isinstance(body, str):
        raise PublishError("Authenticated raw body missing")
    return {
        "id_matches": type(post.get("id")) is int and post["id"] == article.POST_ID,
        "slug_matches": post.get("slug") == article.SLUG,
        "title_matches": article.title_matches(post, authenticated=True),
        "published": post.get("status") == "publish",
        "link_matches": article.exact_article_url(post.get("link"), article.SLUG),
        "modified_gmt": post.get("modified_gmt"),
        "raw_length": len(body), "raw_sha256": article.sha(body),
        "old_reviewed_source": article.old_source(body),
        "new_marker": article.MARK in body,
        "new_revision_matches": body == article.revision(),
    }


def public_fingerprint():
    post = article.public_rest()
    page = article.public_page()
    body = (post.get("content") or {}).get("rendered")
    if not isinstance(body, str):
        raise PublishError("Public rendered body missing")
    return {
        "id_matches": post.get("id") == article.POST_ID,
        "modified_gmt": post.get("modified_gmt"),
        "rendered_sha256": article.sha(body),
        "new_marker_rest": article.MARK in body,
        "new_marker_page": article.MARK in page,
        "old_reviewed_rest": article.old_source(body),
        "wrong_body_canonical_present": article.BAD_LINK in page,
        "public_canonical_count": page.count('rel="canonical"'),
    }


def run():
    base = normalized_base()
    route = "posts/9462?context=edit&_fields=" + FIELDS
    ordinary = fingerprint(wp_request(base, route))
    cache_busted = fingerprint(wp_request(base, route + "&xfit_probe=" + str(time.time_ns())))
    revisions = []
    revisions_error = None
    try:
        result = wp_request(base, "posts/9462/revisions?per_page=3&_fields=id,modified,content")
        if not isinstance(result, list):
            raise PublishError("Unexpected revisions shape")
        for item in result:
            raw = (item.get("content") or {}).get("raw")
            revisions.append({"modified": item.get("modified"),
                              "raw_sha256": article.sha(raw) if isinstance(raw, str) else None,
                              "new_marker": article.MARK in raw if isinstance(raw, str) else None})
    except (PublishError, OSError, TypeError, ValueError) as error:
        revisions_error = type(error).__name__
    result = {
        "state": "READ_ONLY_9462_POST_INCIDENT", "post_id": article.POST_ID,
        "ordinary": ordinary, "cache_busted": cache_busted,
        "same_auth_source": ordinary["raw_sha256"] == cache_busted["raw_sha256"],
        "revisions": revisions, "revisions_error": revisions_error,
        "public": public_fingerprint(), "remote_post_attempts": 0,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        run()
    except (PublishError, OSError, ValueError, TypeError, AttributeError) as error:
        print(json.dumps({"state": "READ_ONLY_INCIDENT_FAILED", "reason": str(error),
                          "remote_post_attempts": 0}))
        raise SystemExit(2)
