"""Evidence-only counting of real XFIT WordPress releases from GitHub Actions.

A successful CI run is NOT a publication. Canonical publisher receipts and
guarded coupon-wave receipts are separate proof channels. A failed coupon
wave can still prove individual public updates; unknown outcomes never
become successes. Never expose raw job logs or secrets.
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
    "XFIT Plant Protein Comparison First Live Release",
    "XFIT Plant Protein Daily Live Refresh",
    "XFIT Beginner Plant Commerce Onepost",
    "XFIT Home Equipment Comparison First Live Release",
    "XFIT Home Equipment Daily Live Refresh",
    "XFIT Equipment Mat Commerce Onepost",
    "XFIT Equipment Band Commerce Onepost",
    "XFIT Beginner Four Lane Hub Onepost",
    "XFIT Protein Guide Commerce Routes",
    "XFIT Protein Price Commerce Routes",
    "XFIT Direct Publish",
    "XFIT Autonomous Approved Editorial Publish",
    "XFIT AI Author and Source-Bound Live Publisher",
    "XFIT Protein Intake Editorial Upgrade",
    "XFIT Protein Physiology Editorial Upgrade",
    "XFIT Pilates Cardio Editorial Upgrade",
    "XFIT Pilates Revision",
    "XFIT Coupon Post 11600 Recovery",
    "XFIT Coupon Post 11595 Recovery",
    "XFIT Pilates GSC Query-Intent Title Onepost",
    "XFIT Protein Pack-use One-post Live Release",
    "XFIT Protein Table Opt-out One-post Live Release",
    "XFIT Beginner Goal Handoffs One-post Live",
})
COMMERCIAL = {
    "xfit-os-kreatin-poradce": 25455,
    "xfit-os-syrovatkovy-protein-porovnani": 25456,
    "xfit-os-rostlinne-proteiny-porovnani": 26152,
    "xfit-os-vybaveni-na-domaci-cviceni-nabidky": 26154,
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


PLANT_FIRST = "XFIT Plant Protein Comparison First Live Release"
PLANT_DAILY = "XFIT Plant Protein Daily Live Refresh"
PLANT_HANDOFF = "XFIT Beginner Plant Commerce Onepost"
PLANT_NAMES = frozenset({PLANT_FIRST, PLANT_DAILY, PLANT_HANDOFF})


def inspect_plant_log(log, run):
    """Actual apply and later live browser evidence only; ignore unit fixtures."""
    name = run.get("name")
    if name not in PLANT_NAMES:
        return [], False
    marker = {
        PLANT_FIRST: "##[group]Run python -m scripts.xfit_plant_comparison apply",
        PLANT_DAILY: "##[group]Run python -m scripts.xfit_plant_refresh apply",
        PLANT_HANDOFF: "##[group]Run set -o pipefail",
    }[name]
    if log.count(marker) != 1:
        return [], False
    command, sep, output = log.split(marker, 1)[1].partition("##[endgroup]")
    if not sep or (name == PLANT_HANDOFF and
            "python -m scripts.xfit_verified_inlink_release beginner_plant_commerce_25458 apply" not in command):
        return [], False
    receipts = [v for line in output.splitlines() if (v := _receipt(line))]
    expected_id, slug = ((25458, "xfit-os-doplnky-pro-zacatecniky") if name == PLANT_HANDOFF
                         else (26152, "xfit-os-rostlinne-proteiny-porovnani"))
    url = "https://xfit.cz/" + slug + "/"
    result_states = {"PUBLIC_VERIFIED_NEW_POST", "live_verified", "PUBLIC_VERIFIED",
                     "unchanged_public_verified", "ALREADY_LINKED_NO_WRITE"}
    final = [v for v in receipts if v.get("state") in result_states]
    mobile_state = "PLANT_BEGINNER_MOBILE_VERIFIED" if name == PLANT_HANDOFF else "PLANT_MOBILE_LIVE_VERIFIED"
    mobile = [v for v in receipts if v.get("state") == mobile_state]
    if len(final) != 1 or len(mobile) != 1 or receipts.index(final[0]) >= receipts.index(mobile[0]):
        return [], False
    v, browser = final[0], mobile[0]
    if (v.get("post_id") != expected_id or v.get("url") != url or
            v.get("slug", slug) != slug or browser.get("width") != 375):
        return [], False
    if name == PLANT_HANDOFF:
        if browser.get("target") != "https://xfit.cz/xfit-os-rostlinne-proteiny-porovnani/":
            return [], False
    elif (type(browser.get("cards")) is not int or not 2 <= browser["cards"] <= 6
            or browser.get("clicked_merchant_links") != 0):
        return [], False
    if v.get("state") == ("ALREADY_LINKED_NO_WRITE" if name == PLANT_HANDOFF else "unchanged_public_verified"):
        if (v.get("public_site_modified") is False
                and (name == PLANT_FIRST or v.get("post_attempts") == 0)):
            return [], True
        return [], False
    if v.get("public_site_modified") is not True:
        return [], False
    if name == PLANT_FIRST:
        if v.get("state") != "PUBLIC_VERIFIED_NEW_POST" or v.get("new_posts") != 1:
            return [], False
        kind = "new"
    else:
        if (v.get("state") != ("PUBLIC_VERIFIED" if name == PLANT_HANDOFF else "live_verified")
                or v.get("posts_changed") != 1 or v.get("post_attempts") != 1
                or v.get("new_posts") != 0):
            return [], False
        if name == PLANT_DAILY and (v.get("deletes") != 0 or v.get("redirects") != 0):
            return [], False
        kind = "updated"
    return [{"kind": kind, "slug": slug, "post_id": expected_id, "url": url,
             "run_id": run["id"], "run_url": "https://github.com/" + REPO + "/actions/runs/" + str(run["id"])}], False


EQUIPMENT_FIRST = "XFIT Home Equipment Comparison First Live Release"
EQUIPMENT_DAILY = "XFIT Home Equipment Daily Live Refresh"
EQUIPMENT_HANDOFFS = {
    "XFIT Equipment Mat Commerce Onepost": (25554, "xfit-os-vyber-podlozky-na-cviceni", "equipment_mat_25554", "#xfit-gear-mat"),
    "XFIT Equipment Band Commerce Onepost": (25561, "xfit-os-vyber-odporove-gumy", "equipment_band_25561", "#xfit-gear-band"),
}
EQUIPMENT_NAMES = frozenset({EQUIPMENT_FIRST, EQUIPMENT_DAILY, *EQUIPMENT_HANDOFFS})


def inspect_equipment_log(log, run):
    name = run.get("name")
    if name not in EQUIPMENT_NAMES:
        return [], False
    handoff = EQUIPMENT_HANDOFFS.get(name)
    if handoff:
        pid, slug, key, fragment = handoff
        marker = "##[group]Run set -o pipefail"
    else:
        pid, slug = 26154, "xfit-os-vybaveni-na-domaci-cviceni-nabidky"
        marker = ("##[group]Run python -m scripts.xfit_equipment_comparison apply"
                  if name == EQUIPMENT_FIRST else
                  "##[group]Run python -m scripts.xfit_equipment_refresh apply")
    if log.count(marker) != 1:
        return [], False
    command, sep, output = log.split(marker, 1)[1].partition("##[endgroup]")
    if not sep or (handoff and ("python -m scripts.xfit_verified_inlink_release " + key + " apply") not in command):
        return [], False
    receipts = [v for line in output.splitlines() if (v := _receipt(line))]
    url = "https://xfit.cz/" + slug + "/"
    final = [v for v in receipts if v.get("state") in {
        "PUBLIC_VERIFIED_NEW_POST", "live_verified", "PUBLIC_VERIFIED",
        "unchanged_public_verified", "ALREADY_LINKED_NO_WRITE"}]
    mobile = [v for v in receipts if v.get("state") ==
              ("EQUIPMENT_HANDOFF_MOBILE_VERIFIED" if handoff else "EQUIPMENT_MOBILE_LIVE_VERIFIED")]
    if len(final) != 1 or len(mobile) != 1 or receipts.index(final[0]) >= receipts.index(mobile[0]):
        return [], False
    v, browser = final[0], mobile[0]
    if v.get("post_id") != pid or v.get("url") != url or v.get("slug", slug) != slug or browser.get("width") != 375:
        return [], False
    if handoff:
        if browser.get("post_id") != pid or browser.get("target") != (
                "https://xfit.cz/xfit-os-vybaveni-na-domaci-cviceni-nabidky/" + fragment):
            return [], False
    elif (type(browser.get("cards")) is not int or not 2 <= browser["cards"] <= 6
            or browser.get("clicked_merchant_links") != 0):
        return [], False
    if v.get("state") == ("ALREADY_LINKED_NO_WRITE" if handoff else "unchanged_public_verified"):
        return [], (v.get("public_site_modified") is False
                    and (name == EQUIPMENT_FIRST or v.get("post_attempts") == 0))
    if v.get("public_site_modified") is not True:
        return [], False
    if name == EQUIPMENT_FIRST:
        if v.get("state") != "PUBLIC_VERIFIED_NEW_POST" or v.get("new_posts") != 1:
            return [], False
        kind = "new"
    else:
        if (v.get("state") != ("PUBLIC_VERIFIED" if handoff else "live_verified")
                or v.get("post_attempts") != 1 or v.get("posts_changed") != 1 or v.get("new_posts") != 0):
            return [], False
        if not handoff and (v.get("deletes") != 0 or v.get("redirects") != 0):
            return [], False
        kind = "updated"
    return [{"kind": kind, "slug": slug, "post_id": pid, "url": url, "run_id": run["id"],
             "run_url": "https://github.com/" + REPO + "/actions/runs/" + str(run["id"])}], False


ROUTE_RELEASES = {
    "XFIT Beginner Four Lane Hub Onepost": (25458, "xfit-os-doplnky-pro-zacatecniky", 6,
        "python -m scripts.xfit_beginner_four_lane_hub apply", "PUBLIC_FOUR_LANE_HUB_VERIFIED",
        "FOUR_LANE_MOBILE_LIVE_VERIFIED", "public_choices"),
    "XFIT Protein Guide Commerce Routes": (25451, "xfit-os-protein-guide", 4,
        "python -m scripts.xfit_protein_commerce_routes protein-guide apply", "PUBLIC_PROTEIN_ROUTES_VERIFIED",
        "PROTEIN_ROUTES_MOBILE_LIVE_VERIFIED", "choices"),
    "XFIT Protein Price Commerce Routes": (25541, "xfit-os-cena-proteinu-podle-etikety", 2,
        "python -m scripts.xfit_protein_commerce_routes protein-price apply", "PUBLIC_PROTEIN_ROUTES_VERIFIED",
        "PROTEIN_ROUTES_MOBILE_LIVE_VERIFIED", "choices"),
}


def inspect_route_log(log, run):
    pid, slug, count, command, state, mobile_state, count_key = ROUTE_RELEASES[run["name"]]
    marker = "##[group]Run " + command
    if log.count(marker) != 1:
        return [], False
    _, sep, output = log.split(marker, 1)[1].partition("##[endgroup]")
    if not sep:
        return [], False
    receipts = [v for line in output.splitlines() if (v := _receipt(line))]
    final = [v for v in receipts if v.get("state") == state]
    mobile = [v for v in receipts if v.get("state") == mobile_state]
    url = "https://xfit.cz/" + slug + "/"
    if len(final) != 1 or len(mobile) != 1 or receipts.index(final[0]) >= receipts.index(mobile[0]):
        return [], False
    v, browser = final[0], mobile[0]
    if (v.get("post_id") != pid or v.get("url") != url or v.get(count_key) != count
            or v.get("new_posts") != 0 or browser.get("width") != 375
            or browser.get("choices") != count or browser.get("merchant_clicks") != 0):
        return [], False
    if pid == 25458:
        if v.get("home_rank") != 1 or v.get("category_rank") != 1:
            return [], False
    elif browser.get("post_id") != pid:
        return [], False
    if v.get("public_site_modified") is False:
        return [], v.get("post_attempts") == 0 and v.get("posts_changed") == 0
    if v.get("public_site_modified") is not True or v.get("post_attempts") != 1 or v.get("posts_changed") != 1:
        return [], False
    return [{"kind": "updated", "slug": slug, "post_id": pid, "url": url,
             "run_id": run["id"], "run_url": "https://github.com/" + REPO + "/actions/runs/" + str(run["id"])}], False


def inspect_log(log, run):
    if run.get("name") in ROUTE_RELEASES:
        return inspect_route_log(log, run)
    if run.get("name") in EQUIPMENT_NAMES:
        return inspect_equipment_log(log, run)
    if run.get("name") in PLANT_NAMES:
        return inspect_plant_log(log, run)
    events = []
    noop = False
    production_apply = {
        "XFIT Coupon Post 11600 Recovery":
            "python -m scripts.xfit_coupon_recovery apply",
        "XFIT Coupon Post 11595 Recovery":
            "python -m scripts.xfit_coupon_recovery_11595 apply",
        "XFIT Pilates GSC Query-Intent Title Onepost":
            "python -m scripts.xfit_pilates_gsc_title_release apply",
        "XFIT Protein Pack-use One-post Live Release":
            "python -m scripts.xfit_protein_pack_release apply",
        "XFIT Protein Table Opt-out One-post Live Release":
            "python -m scripts.xfit_protein_table_optout_release apply",
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
        if run.get("name") == "XFIT Pilates GSC Query-Intent Title Onepost":
            if state != "PUBLIC_VERIFIED":
                continue
            # Only after production apply, not the synthetic test fixtures
            # printed before the prewrite artifact has been uploaded.
            if (entry.get("post_id") != 3660
                    or entry.get("url") !=
                    "https://xfit.cz/jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates/"
                    or entry.get("posts_changed") != 1
                    or entry.get("post_attempts") != 1
                    or entry.get("title_changed") is not True
                    or entry.get("existing_html_preserved") is not True
                    or entry.get("public_site_modified") is not True
                    or entry.get("new_posts") != 0
                    or entry.get("deletes") != 0 or entry.get("redirects") != 0):
                continue
            kind = "updated"
        elif run.get("name") == "XFIT Coupon Post 11595 Recovery":
            if state != "PUBLIC_VERIFIED":
                continue
            # The new isolated release emits fixture receipts during tests:
            # count ONLY the post-backup production apply and its exact post.
            if (entry.get("post_id") != 11595 or
                    entry.get("url") !=
                    "https://xfit.cz/nove-trendy-v-tekutem-spalovaci-tuku-pro-fitness-nadsence/" or
                    entry.get("shortcodes_removed") != 3 or
                    entry.get("posts_changed") != 1 or
                    entry.get("post_attempts") != 1 or
                    entry.get("new_posts", 0) != 0 or
                    entry.get("public_site_modified") is not True or
                    entry.get("deletes") != 0 or entry.get("redirects") != 0):
                continue
            kind = "updated"
        elif run.get("name") == "XFIT Coupon Post 11600 Recovery":
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
        elif run.get("name") == "XFIT Protein Table Opt-out One-post Live Release":
            if state != "PUBLIC_VERIFIED":
                continue
            # Count only a post-backup production apply receipt for the pinned
            # protein decision table; pre-release unit tests print fixtures.
            if (entry.get("post_id") != 25451
                    or entry.get("slug") != "xfit-os-protein-guide"
                    or entry.get("url") != "https://xfit.cz/xfit-os-protein-guide/"
                    or entry.get("new_table_rows_inserted") != 1
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



COUPON_WORKFLOW = "XFIT Expired Coupon Cleanup"
COUPON_APPLY = "python -m scripts.xfit_coupon_cleanup apply"
COUPON_STATES = {"coupon_wave_verified", "coupon_wave_partial",
                 "coupon_wave_public_unverified"}


def _positive_id_list(values, *, records=False):
    if not isinstance(values, list) or len(values) > 8:
        raise ValueError("Invalid bounded coupon ID list")
    ids = []
    for value in values:
        if records and not isinstance(value, dict):
            raise ValueError("Coupon outcome must be an ID record")
        pid = value.get("id") if records else value
        if type(pid) is not int or pid <= 0 or pid in ids:
            raise ValueError("Invalid or duplicate coupon post ID")
        ids.append(pid)
    return ids


def inspect_coupon_log(log, run):
    """Accept only the real guarded apply receipts, never unit-test fixtures.

    IDs, not invented slugs/URLs, identify legacy posts. Shortcode totals are
    public-confirmed only when every authenticated changed post has public
    proof; a partial public subset cannot establish its own shortcode total.
    """
    if (run.get("name") != COUPON_WORKFLOW
            or run.get("status") != "completed"
            or run.get("conclusion") not in {"success", "failure"}):
        raise ValueError("Coupon run has no final eligible outcome")
    marker = "##[group]Run set -o pipefail"
    if log.count(marker) != 1:
        raise ValueError("Missing or ambiguous actual coupon apply step")
    tail = log.split(marker, 1)[1]
    command, sep, output = tail.partition("##[endgroup]")
    if not sep or COUPON_APPLY not in command:
        raise ValueError("Unexpected coupon apply command")
    receipts = [v for line in output.splitlines() if (v := _receipt(line))]
    reservations = [v for v in receipts if
                    v.get("state") == "COUPON_ATTEMPTS_RESERVED_BEFORE_WP"]
    finals = [v for v in receipts if v.get("state") in COUPON_STATES]
    if len(reservations) != 1 or len(finals) != 1:
        raise ValueError("Missing or ambiguous coupon reservation/final receipt")
    reservation, final = reservations[0], finals[0]
    if receipts.index(reservation) >= receipts.index(final):
        raise ValueError("Coupon reservation did not precede the final receipt")
    attempted = reservation.get("new_attempt_ids")
    total_attempts = reservation.get("total_attempts")
    changed = final.get("posts_changed")
    removed = final.get("shortcodes_removed")
    if (type(attempted) is not int or not 0 <= attempted <= 8
            or type(total_attempts) is not int or total_attempts < attempted
            or type(reservation.get("issue")) is not int
            or reservation["issue"] != 363
            or type(reservation.get("wordpress_writes")) is not int
            or reservation["wordpress_writes"] != 0
            or type(changed) is not int or not 0 <= changed <= attempted
            or type(removed) is not int or removed < changed
            or (changed == 0 and removed != 0)
            or any(type(final.get(k)) is not int or final[k] != 0
                   for k in ("deletes", "redirects"))):
        raise ValueError("Coupon count or reservation invariant failed")
    verified = _positive_id_list(final.get("public_verified_post_ids"))
    unchanged = _positive_id_list(final.get("unchanged_failures"), records=True)
    uncertain = _positive_id_list(final.get("uncertain_posts"), records=True)
    unverified = _positive_id_list(final.get("public_not_verified"), records=True)
    combined = verified + unchanged + uncertain + unverified
    if (len(combined) != attempted or len(set(combined)) != attempted
            or changed != len(verified) + len(unverified)):
        raise ValueError("Coupon proof does not partition the reserved posts")
    state = ("coupon_wave_public_unverified" if unverified else
             "coupon_wave_partial" if unchanged or uncertain else
             "coupon_wave_verified")
    expected_conclusion = "success" if state == "coupon_wave_verified" else "failure"
    if final.get("state") != state or run["conclusion"] != expected_conclusion:
        raise ValueError("Coupon workflow conclusion disagrees with final proof")
    return {
        "run_id": run["id"], "state": state, "attempted": attempted,
        "public_verified_post_ids": verified,
        "unchanged_post_ids": unchanged, "uncertain_post_ids": uncertain,
        "public_unverified_post_ids": unverified,
        "public_verified_shortcodes": None if unverified else removed,
    }


def coupon_cleanup_evidence(runs, token, *, fetch_jobs, fetch_log=job_log):
    """Bounded, read-only coupon receipt inventory; no WP requests or retries."""
    candidates = [r for r in runs if r.get("name") == COUPON_WORKFLOW]
    waves, unknown, seen = [], [], set()
    for run in candidates[:15]:
        rid = run.get("id")
        if type(rid) is not int or rid <= 0:
            unknown.append(None)
            continue
        if rid in seen:
            continue
        seen.add(rid)
        try:
            if (run.get("status") != "completed"
                    or run.get("conclusion") not in {"success", "failure"}):
                raise ValueError("Coupon wave is not final")
            joblist = fetch_jobs(rid, token).get("jobs")
            if not isinstance(joblist, list) or len(joblist) != 1:
                raise ValueError("Unexpected coupon job inventory")
            job = joblist[0]
            if (job.get("name") != "cleanup" or job.get("status") != "completed"
                    or job.get("conclusion") != run["conclusion"]
                    or type(job.get("id")) is not int or job["id"] <= 0):
                raise ValueError("Unexpected coupon job outcome")
            steps = job.get("steps")
            if not isinstance(steps, list):
                raise ValueError("Missing coupon job step proof")
            required = {
                "Repository tests": "success",
                "Read-only paginated preview of up to eight never-attempted coupon posts": "success",
                "Backup artifact is mandatory before any WordPress writes": "success",
                "Reserve all post IDs in issue 363 BEFORE any WP POST; then verify public pages":
                    run["conclusion"],
            }
            positions = []
            for name, conclusion in required.items():
                matches = [(i, s) for i, s in enumerate(steps) if s.get("name") == name]
                if (len(matches) != 1 or matches[0][1].get("status") != "completed"
                        or matches[0][1].get("conclusion") != conclusion):
                    raise ValueError("Required coupon prewrite/apply proof missing")
                positions.append(matches[0][0])
            if positions != sorted(positions) or len(set(positions)) != len(positions):
                raise ValueError("Coupon backup/apply order invalid")
            waves.append(inspect_coupon_log(fetch_log(job["id"], token), run))
        except (KeyError, TypeError, ValueError, OSError, AttributeError,
                urllib.error.HTTPError, urllib.error.URLError):
            unknown.append(rid)
    if len(candidates) > 15:
        unknown.append(None)
    verified_ids = {pid for wave in waves for pid in wave["public_verified_post_ids"]}
    return {
        "runs_seen": len(candidates), "waves": waves,
        "unknown_run_ids": unknown,
        "public_verified_unique_posts": len(verified_ids),
        "public_verified_update_events": sum(len(w["public_verified_post_ids"]) for w in waves),
        "known_public_verified_shortcodes": sum(w["public_verified_shortcodes"] or 0
                                                 for w in waves),
        "shortcode_count_incomplete": bool(unknown) or any(
            w["public_verified_shortcodes"] is None or bool(w["uncertain_post_ids"])
            for w in waves),
    }


def real_release_evidence(runs, token, *, fetch_jobs, fetch_log=job_log):
    """Inspect only successful publisher jobs; fail closed for inaccessible proof.

    Callers supply GitHub REST fetch_jobs returning a jobs-list JSON object.
    No user content, raw logs, URL tracking parameters or secrets are returned.
    """
    runs = list(runs)
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
        "coupon_cleanup": coupon_cleanup_evidence(
            runs, token, fetch_jobs=fetch_jobs, fetch_log=fetch_log),
        "proof_scope": "canonical_publisher_and_separate_guarded_coupon_receipts",
    }
