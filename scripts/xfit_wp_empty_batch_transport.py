"""Single empty-batch POST transport diagnostic: zero WordPress subrequests.

The immutable payload {"requests":[]} invokes WordPress Core /batch/v1 with
zero child requests. It does not update any article. It is NOT a substitute for
a source-pinned content release, and must never lift #9462 quarantine.
No retry after any POST result, including HTTP errors and timeouts.
"""
import hashlib
import json
import time
from urllib import error as url_error
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import PublishError, normalized_base
from scripts.xfit_wp_rest_options_probe import auth_headers
from scripts import xfit_canonical_preflight as read_only

EXPECTED = {
    9371: {
        "slug": "jak-spravne-pouzivat-bcaa-pro-lepsi-regeneraci-a-svalovy-rust",
        "raw_sha256": "e6deec0b5bba9c52457d3cb3dbd141f4ef8eeb3b2d531408054084e8a2e8de20",
        "modified_gmt": "2023-10-21T07:44:55",
    },
    9462: {
        "slug": "japonske-cviceni-na-hubnuti-objasnujeme-zakladni-principy",
        "raw_sha256": "9eb41216364cdee0bf77b8c584ba537ce1539bd096642dbd39767cacfb13cb76",
        "modified_gmt": "2023-10-22T02:51:47",
    },
}
BATCH_PATH = "/wp-json/batch/v1"
EMPTY_BATCH_BYTES = b'{"requests":[]}'
MAX_RESPONSE_BYTES = 131_072


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def exact_response_path(value, path):
    p = urlsplit(value)
    return (p.scheme == "https" and p.hostname in ("xfit.cz", "www.xfit.cz")
            and p.port is None and p.username is None and p.password is None
            and p.path == path and not p.query and not p.fragment)


def fingerprint(post_id):
    expected = EXPECTED[post_id]
    post = read_only.wp_authenticated(post_id, cache_bust=True)
    body = read_only.source(post, "raw", post_id)
    link = "https://xfit.cz/" + expected["slug"] + "/"
    if post.get("slug") != expected["slug"] or post.get("link") != link:
        raise PublishError("Unexpected authenticated article identity")
    digest = sha(body)
    if digest != expected["raw_sha256"] or post.get("modified_gmt") != expected["modified_gmt"]:
        raise PublishError("Reviewed authenticated article changed; no batch POST")
    public = json.loads(read_only.public_get(
        "https://xfit.cz/wp-json/wp/v2/posts/" + str(post_id)
        + "?_fields=id,slug,status,link,modified_gmt,content"))
    rendered = read_only.source(public, "rendered", post_id)
    if (public.get("slug") != expected["slug"] or public.get("link") != link
            or public.get("modified_gmt") != expected["modified_gmt"]):
        raise PublishError("Public source does not match reviewed WordPress identity")
    return {
        "post_id": post_id,
        "raw_sha256": digest,
        "public_rendered_sha256": sha(rendered),
        "modified_gmt": post["modified_gmt"],
    }


def all_fingerprints():
    return [fingerprint(post_id) for post_id in EXPECTED]


def empty_batch_transport(base):
    # No arbitrary caller payloads. WordPress core iterates over requests; [] => no subrequests.
    if EMPTY_BATCH_BYTES != b'{"requests":[]}' or json.loads(EMPTY_BATCH_BYTES) != {"requests": []}:
        raise PublishError("Empty batch contract changed; no POST")
    url = base + BATCH_PATH
    request = Request(url, headers=auth_headers(), data=EMPTY_BATCH_BYTES, method="POST")
    start = time.monotonic()
    status, problem, response_is_empty = None, "NONE", False
    try:
        with urlopen(request, timeout=25) as result:
            status = result.status
            if not exact_response_path(result.geturl(), BATCH_PATH):
                raise PublishError("Batch redirected to unexpected URL")
            response_bytes = result.read(MAX_RESPONSE_BYTES + 1)
            if len(response_bytes) > MAX_RESPONSE_BYTES:
                raise PublishError("Batch response too large")
            result_data = json.loads(response_bytes)
            response_is_empty = (isinstance(result_data, dict)
                                 and result_data.get("responses") == []
                                 and "failed" not in result_data)
            if not response_is_empty:
                problem = "UNEXPECTED_BATCH_RESPONSE"
    except url_error.HTTPError as exc:
        status, problem = exc.code, "HTTP_" + str(exc.code)
    except TimeoutError:
        problem = "TRANSPORT_TIMEOUT"
    except (PublishError, OSError, ValueError, UnicodeError) as exc:
        problem = "UNEXPECTED_RESPONSE" if isinstance(exc, (PublishError, ValueError)) else "TRANSPORT_ERROR"
    return {
        "http_status": status,
        "problem_category": problem,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
        "empty_batch_response": response_is_empty,
        "http_post_attempts": 1,
        "wordpress_child_requests": 0,
        "wordpress_content_mutations_requested": 0,
        "post_retry": False,
    }


def run():
    base = normalized_base()
    report = {
        "state": "EMPTY_BATCH_PREFLIGHT",
        "http_post_attempts": 0,
        "wordpress_content_mutations_requested": 0,
        "wordpress_child_requests": 0,
        "post_retry": False,
        "release_allowed": False,
    }
    try:
        before = all_fingerprints()
        report["reviewed_sources_before"] = before
    except (PublishError, ValueError, OSError, TypeError, KeyError):
        report["state"] = "SOURCE_DRIFT_NO_POST"
        print(json.dumps(report, sort_keys=True))
        raise SystemExit(2) from None

    result = empty_batch_transport(base)
    report.update(result)

    try:
        after = all_fingerprints()
        report["sources_unchanged"] = after == before
    except (PublishError, ValueError, OSError, TypeError, KeyError):
        report["sources_unchanged"] = None

    accepted = (result["http_status"] in (200, 207) and result["empty_batch_response"]
                and result["problem_category"] == "NONE"
                and report["sources_unchanged"] is True)
    report["state"] = ("EMPTY_BATCH_TRANSPORT_CONFIRMED_NO_ARTICLE_CHANGE" if accepted
                       else "EMPTY_BATCH_TRANSPORT_UNVERIFIED")
    print(json.dumps(report, sort_keys=True))
    if not accepted:
        raise SystemExit(2)


if __name__ == "__main__":
    run()
