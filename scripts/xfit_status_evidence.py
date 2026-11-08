"""Evidence-only counting of real XFIT WordPress releases from GitHub Actions.

A successful CI run is NOT a publication. Only a success-concluded publisher
run with an explicit canonical public-verification receipt counts as a site
change. Read failures remain UNKNOWN. Never expose raw job logs or secrets.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

REPO = "Rastty/xfit-growth-os"
PUBLISHER_NAMES = frozenset({
    "XFIT Creatine Advisor Live",
    "XFIT Whey Advisor Live",
    "XFIT Direct Publish",
    "XFIT Autonomous Approved Editorial Publish",
    "XFIT AI Author and Source-Bound Live Publisher",
    "XFIT Protein Intake Editorial Upgrade",
    "XFIT Protein Physiology Editorial Upgrade",
    "XFIT Pilates Cardio Editorial Upgrade",
    "XFIT Pilates Revision",
    "XFIT Coupon Post 11600 Recovery",
    "XFIT Protein Pack-use One-post Live Release",
    "XFIT Beginner Goal Handoffs One-post Live",
})
COMMERCIAL = {
    "xfit-os-kreatin-poradce": 25455,
    "xfit-os-syrovatkovy-protein-porovnani": 25456,
}
NO_CHANGE = {"ALL_PINNED_ARTICLES_PUBLIC_VERIFIED",
             "NO_APPROVED_TARGET", "unchanged_public_verified",
             "ALREADY_PUBLIC_VERIFIED", "ALREADY_CLEAN_NO_WRITE",
             "ALREADY_APPLIED_NO_WRITE"}
MAX_LOG_BYTES = 8_000_000


class NoTokenRedirect(urllib.request.HTTPRedirectHandler):
    """Use signed HTTPS log download without forwarding the GitHub bearer."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(req.full_url)
        new = urllib.parse.urlsplit(newurl)
        if new.scheme != "https":
            raise ValueError("Non-HTTPS GitHub log redirect")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and old.hostname != new.hostname:
            redirected.remove_header("Authorization")
        return redirected


def job_log(job_id, token):
    if type(job_id) is not int or job_id <= 0 or not token:
        raise ValueError("Invalid Github Actions job request")
    endpoint = "https://api.github.com/repos/" + REPO + "/actions/jobs/" + str(job_id) + "/logs"
    request = urllib.request.Request(endpoint, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "User-Agent": "XFITRealReleaseStatus/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    opener = urllib.request.build_opener(NoTokenRedirect)
    with opener.open(request, timeout=22) as response:
        data = response.read(MAX_LOG_BYTES + 1)
    if len(data) > MAX_LOG_BYTES:
        raise ValueError("Oversized job logs cannot be trusted as complete")
    return data.decode("utf-8", errors="replace")


def _receipt(line):
    # Logs include the runner UTC prefix before a stand-alone JSON record.
    # Do not scan arbitrary fragments, script output or inline HTML.
    hit = re.search(r'(?:^|\s)(\{\s*"(?:state|status|stage)"\s*:)', line)
    if not hit:
        return None
    try:
        value = json.loads(line[hit.start(1):])
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def canonical(slug, url, post_id):
    if (not isinstance(slug, str) or not isinstance(url, str)
            or type(post_id) is not int or post_id <= 0
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", slug)):
        return None
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ("xfit.cz", "www.xfit.cz")
            or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment or parsed.path.rstrip("/") != "/" + slug):
        return None
    if slug in COMMERCIAL and COMMERCIAL[slug] != post_id:
        return None
    return "https://xfit.cz/" + slug + "/"


def inspect_log(log, run):
    events = []
    noop = False
    production_apply = {
        "XFIT Coupon Post 11600 Recovery":
            "python -m scripts.xfit_coupon_recovery apply",
        "XFIT Protein Pack-use One-post Live Release":
            "python -m scripts.xfit_protein_pack_release apply",
        "XFIT Beginner Goal Handoffs One-post Live":
            "python -m scripts.xfit_beginner_goal_release apply",
    }
    if run.get("name") in production_apply:
        # Full job logs also contain synthetic PUBLIC_VERIFIED fixtures from
        # unit tests. Accept receipts ONLY AFTER the real production 'apply'
        # step, which runs after a mandatory prewrite backup artifact upload.
        step = "##[group]Run set -o pipefail"
        if step not in log:
            return [], False
        tail = log.split(step, 1)[1]
        if "##[endgroup]" not in tail:
            return [], False
        command, log = tail.split("##[endgroup]", 1)
        if production_apply[run["name"]] not in command:
            return [], False
    for line in log.splitlines():
        entry = _receipt(line)
        if entry is None:
            continue
        state = entry.get("state") or entry.get("stage") or entry.get("status")
        if state in NO_CHANGE and entry.get("new_posts", 0) == 0:
            noop = True
            continue
        if state == "live_verified" and entry.get("public_site_modified") is False:
            noop = True
            continue
        if run.get("name") == "XFIT Coupon Post 11600 Recovery":
            if state != "PUBLIC_VERIFIED":
                continue
            # A specific proven one-post repair; never count synthetic
            # test output or any unrelated URL/post as a production update.
            if (entry.get("post_id") != 11600 or
                    entry.get("url") !=
                    "https://xfit.cz/test-a-recenze-nejlepsich-tekutych-spalovacu-tuku-pro-fitnesscviky/" or
                    entry.get("shortcodes_removed") != 3 or
                    entry.get("posts_changed") != 1 or
                    entry.get("post_attempts") != 1 or
                    entry.get("public_site_modified") is not True or
                    entry.get("deletes") != 0 or entry.get("redirects") != 0):
                continue
            kind = "updated"
        elif run.get("name") == "XFIT Protein Pack-use One-post Live Release":
            if state != "PUBLIC_VERIFIED":
                continue
            # One approved existing post; reject test receipts, wrong URLs,
            # new posts and any write beyond the exact editorial list item.
            if (entry.get("post_id") != 25451
                    or entry.get("slug") != "xfit-os-protein-guide"
                    or entry.get("url") != "https://xfit.cz/xfit-os-protein-guide/"
                    or entry.get("old_paragraphs_replaced") != 1
                    or entry.get("posts_changed") != 1
                    or entry.get("post_attempts") != 1
                    or entry.get("new_posts") != 0
                    or entry.get("deletes") != 0
                    or entry.get("redirects") != 0
                    or entry.get("public_site_modified") is not True):
                continue
            kind = "updated"
        elif run.get("name") == "XFIT Beginner Goal Handoffs One-post Live":
            if state != "PUBLIC_VERIFIED":
                continue
            if (entry.get("post_id") != 25458
                    or entry.get("slug") != "xfit-os-doplnky-pro-zacatecniky"
                    or entry.get("url") != "https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/"
                    or entry.get("posts_changed") != 1
                    or entry.get("new_posts") != 0
                    or entry.get("post_attempts") != 1
                    or entry.get("new_goal_links") != 4
                    or entry.get("open_no_buy_answer") is not True
                    or entry.get("public_site_modified") is not True
                    or entry.get("deletes") != 0 or entry.get("redirects") != 0):
                continue
            kind = "updated"
        elif state == "PUBLIC_VERIFIED_NEW_POST" and entry.get("new_posts") == 1:
            kind = "new"
        elif state == "live_verified":
            if entry.get("public_site_modified") is not True:
                # Legacy revisions intentionally use stage=live_verified and
                # verify post identity, original backup and public page.
                if entry.get("stage") != "live_verified":
                    continue
            kind = ("updated" if run.get("name") in {
                "XFIT Creatine Advisor Live", "XFIT Whey Advisor Live",
                "XFIT Protein Intake Editorial Upgrade",
                "XFIT Protein Physiology Editorial Upgrade",
                "XFIT Pilates Cardio Editorial Upgrade",
                "XFIT Pilates Revision",
            } else "publication_or_update")
        else:
            continue
        slug = entry.get("slug")
        url = entry.get("url")
        if not slug and isinstance(url, str):
            slug = urllib.parse.urlsplit(url).path.strip("/")
        public = canonical(slug, url, entry.get("post_id"))
        if not public:
            continue
        events.append({
            "kind": kind,
            "slug": slug,
            "post_id": entry["post_id"],
            "url": public,
            "run_id": run["id"],
            "run_url": "https://github.com/" + REPO + "/actions/runs/" + str(run["id"]),
        })
    # Repeated summaries of the same verified post never count twice.
    unique = {}
    for event in events:
        unique[(event["run_id"], event["post_id"])] = event
    return list(unique.values()), noop


def real_release_evidence(runs, token, *, fetch_jobs, fetch_log=job_log):
    """Inspect only successful publisher jobs; fail closed for inaccessible proof.

    Callers supply GitHub REST fetch_jobs returning a jobs-list JSON object.
    No user content, raw logs, URL tracking parameters or secrets are returned.
    """
    publishers = [r for r in runs if r.get("name") in PUBLISHER_NAMES]
    changed = []
    nochange = 0
    unknown = []
    for run in publishers[:15]:
        rid = run.get("id")
        if type(rid) is not int or rid <= 0:
            unknown.append({"run_id": None, "name": run.get("name", "?")})
            continue
        if run.get("conclusion") != "success" or run.get("status") != "completed":
            unknown.append({"run_id": rid, "name": run["name"]})
            continue
        try:
            jobs = fetch_jobs(rid, token)
            joblist = jobs.get("jobs")
            if not isinstance(joblist, list) or not joblist:
                raise ValueError("Missing GitHub jobs")
            if any(j.get("conclusion") not in ("success", "skipped") for j in joblist):
                raise ValueError("Not all publisher jobs passed")
            observed = []
            noop = False
            inspected = 0
            for job in joblist:
                if job.get("conclusion") == "skipped":
                    continue
                log = fetch_log(job["id"], token)
                found, unchanged = inspect_log(log, run)
                observed.extend(found)
                noop = noop or unchanged
                inspected += 1
            if observed:
                changed.extend(observed)
            elif inspected and noop:
                nochange += 1
            else:
                unknown.append({"run_id": rid, "name": run["name"]})
        except (KeyError, TypeError, ValueError, OSError,
                urllib.error.HTTPError, urllib.error.URLError):
            unknown.append({"run_id": rid, "name": run["name"]})
    if len(publishers) > 15:
        unknown.append({"run_id": None, "name": "More publisher runs than safely inspected"})
    counts = {
        # Never present repeated publishes of the SAME URL as distinct pages.
        "new": len({x["url"] for x in changed if x["kind"] == "new"}),
        "updated": sum(x["kind"] == "updated" for x in changed),
        "unique_updated_pages": len({
            x["url"] for x in changed if x["kind"] == "updated"
        }),
        "publication_or_update": sum(
            x["kind"] == "publication_or_update" for x in changed
        ),
        "unique_changed_pages": len({x["url"] for x in changed}),
    }
    return {
        "verified_events": changed,
        "counts": counts,
        "verified_no_change_runs": nochange,
        "unverified_runs": unknown,
        "publisher_runs_seen": len(publishers),
        "proof_scope": "successful_authorized_github_publisher_job_receipts_only",
    }
