"""Read-only REST route OPTIONS probe for XFIT's two guarded WordPress posts.

This is intentionally NOT a canary POST. OPTIONS only checks whether the route
advertises update methods for the same Basic auth and User-Agent as the existing
publisher. A passing result does NOT prove that a real POST payload will succeed.
Do not infer that a previous ambiguous POST may safely be retried.
"""
import base64
import json
import os
import time
from urllib import error as url_error
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.wp_publish import PublishError, normalized_base

REVIEWED_IDS = (9371, 9462)
MAX_RESPONSE_BYTES = 524_288
TIMEOUT_SECONDS = 25


def endpoint(base, post_id):
    if post_id not in REVIEWED_IDS or type(post_id) is not int:
        raise PublishError("Only the two independently reviewed XFIT post IDs are allowed")
    path = "/wp-json/wp/v2/posts/" + str(post_id)
    return base + path, path


def known_rest_target(value, path):
    parsed = urlsplit(value)
    return (parsed.scheme == "https" and parsed.hostname in ("xfit.cz", "www.xfit.cz")
            and parsed.port is None and parsed.username is None and parsed.password is None
            and parsed.path == path and not parsed.query and not parsed.fragment)


def auth_headers():
    user = os.getenv("WP_USERNAME", "").strip()
    password = os.getenv("WP_APP_PASSWORD", "").strip()
    if not user or not password:
        raise PublishError("Missing authenticated WordPress read permissions")
    encoded = base64.b64encode((user + ":" + password).encode()).decode()
    return {
        "Authorization": "Basic " + encoded,
        "User-Agent": "XfitGrowthOS/0.1",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
    }


def response_methods(headers, source):
    result = set()
    for value in (headers.get("Allow"), headers.get("Access-Control-Allow-Methods")):
        if value:
            result.update(part.strip().upper() for part in value.split(",") if part.strip())
    # WordPress OPTIONS body may list methods per endpoint instead of an Allow header.
    if isinstance(source, dict):
        for route in source.get("endpoints") or []:
            if isinstance(route, dict) and isinstance(route.get("methods"), (list, dict)):
                result.update(str(method).upper() for method in route["methods"])
    return result


def probe(post_id, *, base=None):
    base = base or normalized_base()
    url, path = endpoint(base, post_id)
    request = Request(url, headers=auth_headers(), data=None, method="OPTIONS")
    start = time.monotonic()
    status = None
    methods = set()
    response_ok = False
    problem = "NONE"
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            if not known_rest_target(response.geturl(), path):
                raise PublishError("REST route redirected to unexpected identity")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise PublishError("OPTIONS response exceeded safe read limit")
            parsed = None
            if payload:
                try:
                    parsed = json.loads(payload)
                except (UnicodeDecodeError, ValueError):
                    parsed = None
            methods = response_methods(response.headers, parsed)
            response_ok = status in (200, 204)
    except url_error.HTTPError as exc:
        status = exc.code
        problem = "HTTP_" + str(exc.code)
    except TimeoutError:
        problem = "TRANSPORT_TIMEOUT"
    except (OSError, ValueError, PublishError) as exc:
        # Do not emit server response text or exception arguments.
        problem = "UNEXPECTED_RESPONSE" if isinstance(exc, (PublishError, ValueError)) else "TRANSPORT_ERROR"
    duration = round((time.monotonic() - start) * 1000)
    return {
        "state": "READ_ONLY_OPTIONS_OBSERVED" if response_ok else "READ_ONLY_OPTIONS_BLOCKED",
        "post_id": post_id,
        "http_status": status,
        "advertises_post": "POST" in methods,
        "advertises_get": "GET" in methods,
        "duration_ms": duration,
        "problem_category": problem,
        "method_used": "OPTIONS",
        "body_sent": False,
        "wordpress_writes": 0,
        "post_success_proven": False,
    }


def run():
    base = normalized_base()
    reports = [probe(pid, base=base) for pid in REVIEWED_IDS]
    aggregate = {
        "state": "READ_ONLY_WP_ROUTE_PREFLIGHT",
        "results": reports,
        "post_attempts": 0,
        "permits_post_release": False,
        "note": "OPTIONS cannot prove a real WordPress POST will succeed",
    }
    print(json.dumps(aggregate, sort_keys=True))
    if any(report["state"] != "READ_ONLY_OPTIONS_OBSERVED" for report in reports):
        raise SystemExit(2)


if __name__ == "__main__":
    run()
