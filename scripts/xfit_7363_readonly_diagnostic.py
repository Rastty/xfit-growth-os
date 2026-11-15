"""Read-only follow-up to the unresolved one-shot WP article 7363 update.

Never sends a POST. Emits bounded boolean evidence, not article bodies or secrets.
"""
import json
import time

from scripts.wp_publish import PublishError, normalized_base, wp_request
from scripts.xfit_verified_inlink_release import ALLOWLIST, digest, real_links, public_verified


CFG = ALLOWLIST["whey_training_7363"]
FIELDS = "id,slug,status,content,modified_gmt"


def fingerprint(post):
    if not isinstance(post, dict):
        raise PublishError("Unexpected REST response")
    raw = (post.get("content") or {}).get("raw")
    if not isinstance(raw, str):
        raise PublishError("Read-only source body is unavailable")
    return {
        "id_correct": post.get("id") == CFG.post_id,
        "slug_correct": post.get("slug") == CFG.slug,
        "published": post.get("status") == "publish",
        "source_length": len(raw),
        "source_sha256": digest(raw),
        "marker_present": CFG.marker in raw,
        "target_anchor_present": CFG.target in real_links(raw),
        "modified_gmt": post.get("modified_gmt"),
    }


def main():
    base = normalized_base()
    path = "posts/7363?context=edit&_fields=" + FIELDS
    ordinary = fingerprint(wp_request(base, path))
    uncached = fingerprint(wp_request(base, path + "&xfit_probe=" + str(time.time_ns())))
    latest_revisions = []
    revisions_error = None
    try:
        revisions = wp_request(base, "posts/7363/revisions?per_page=3&_fields=id,modified,content")
        if not isinstance(revisions, list):
            raise PublishError("Unexpected revisions response")
        latest_revisions = [
            {
                "has_marker": CFG.marker in ((row.get("content") or {}).get("raw") or ""),
                "has_target_anchor": CFG.target in real_links((row.get("content") or {}).get("raw") or ""),
                "modified": row.get("modified"),
            }
            for row in revisions
        ]
    except (PublishError, TypeError, ValueError) as exc:
        revisions_error = type(exc).__name__
    try:
        public_has_verified_handoff = public_verified(CFG)
        public_error = None
    except (PublishError, OSError, ValueError) as exc:
        public_has_verified_handoff = False
        public_error = type(exc).__name__
    print(json.dumps({
        "status": "READ_ONLY_DIAGNOSTIC_NO_REMOTE_WRITES",
        "ordinary": ordinary,
        "cache_busted": uncached,
        "same_source_hash": ordinary["source_sha256"] == uncached["source_sha256"],
        "latest_revisions": latest_revisions,
        "revisions_error": revisions_error,
        "public_has_verified_handoff": public_has_verified_handoff,
        "public_error": public_error,
        "remote_post_attempts": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
