"""One-pinned-post release: make four beginner goals actionable without plugins.

The live WordPress body, not stale checked-in editorial JSON, is the source
of truth. Only the reviewed four-goal section may change. A full rollback
artifact must be uploaded BEFORE a single possible POST. Network failure
may mean WordPress already committed; never retry blindly.
"""
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

from scripts.wp_publish import MARKER, PublishError, normalized_base, wp_request
from scripts.xfit_editorial_gate import Inspector, check_document

POST_ID = 25458
SLUG = "xfit-os-doplnky-pro-zacatecniky"
URL = "https://xfit.cz/" + SLUG + "/"
REVISION = Path("content/revisions/beginner-goal-handoffs-20261108.json")
BACKUP = Path("reports/backups/xfit-beginner-goal-handoffs-25458.json")
LINKS = (
    "#zacatecnik-rozpocet",
    "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
    "https://xfit.cz/kolik-bilkovin-potrebujete-pro-budovani-svalu-pruvodce-spravnym-stravovanim/",
    "https://xfit.cz/xfit-os-protein-guide/",
)
TARGET_TEXT = (
    "První odpověď je otevřená",
    "Podívejte se, proč může být rozpočet na doplňky 0 Kč",
    "Pokračovat: jak se rozhodnout mezi jídlem, proteinem a kreatinem",
    "Pokračovat: jak orientačně posoudit celkový příjem bílkovin",
    "Pokračovat: druhy proteinů včetně rostlinných možností",
)
MAX_BYTES = 450000


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GoalDetails(HTMLParser):
    """Collect details elements and link targets in the reviewed section."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.open_flags = []
        self.links = []
        self.summaries = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "details":
            self.open_flags.append("open" in a)
        elif tag == "summary":
            self.summaries += 1
        elif tag == "a":
            self.links.append(html.unescape(a.get("href") or ""))


def proposal():
    data = json.loads(REVISION.read_text(encoding="utf-8"))
    if (not isinstance(data, dict)
            or data.get("status") != "editorial_proposal_approved_for_single_post_release"
            or data.get("operation") != "replace_exact_once"
            or type(data.get("wp_post_id")) is not int or data["wp_post_id"] != POST_ID
            or data.get("slug") != SLUG
            or data.get("source_file") != "content/ready/xfit-os-doplnky-pro-zacatecniky.json"
            or data.get("expected_details") != 4
            or data.get("expected_new_links") != len(LINKS)):
        raise PublishError("Unexpected editorial revision identity")
    old, new = data.get("original"), data.get("replacement")
    if (not isinstance(old, str) or not isinstance(new, str)
            or not 1200 <= len(old) <= 2800
            or not len(old) < len(new) < 3600
            or old.count("<details") != 4 or new.count("<details") != 4
            or old.count("<h2 ") != 1 or new.count("<h2 ") != 1
            or "<script" in new.casefold() or "<iframe" in new.casefold()
            or "onclick=" in new.casefold()):
        raise PublishError("Goal section is incomplete or unsafe")
    p0, p1 = GoalDetails(), GoalDetails()
    p0.feed(old)
    p1.feed(new)
    if (p0.links or p0.open_flags != [False]*4 or p1.open_flags !=
            [True, False, False, False] or p1.summaries != 4
            or tuple(p1.links) != LINKS):
        raise PublishError("Goal links or accessible disclosure defaults differ from review")
    if not all(t in new for t in TARGET_TEXT):
        raise PublishError("Missing reviewed reader paths")
    reviewed = json.loads(Path(data["source_file"]).read_text(encoding="utf-8"))
    body = reviewed.get("content")
    if reviewed.get("slug") != SLUG or not isinstance(body, str) or body.count(old) != 1:
        raise PublishError("Reviewed original no longer appears once in source file")
    check_document({"content":body.replace(old, new, 1)})
    return data


def remote():
    return wp_request(normalized_base(), "posts/" + str(POST_ID) +
                      "?context=edit&_fields=id,slug,status,content,link,modified_gmt")


def prepare(p, edit):
    if (not isinstance(p, dict) or type(p.get("id")) is not int
            or p.get("id") != POST_ID or p.get("status") != "publish"
            or p.get("slug") != SLUG):
        raise PublishError("Unexpected owned article identity/status")
    url = urllib.parse.urlsplit(p.get("link") or "")
    if (url.scheme != "https" or url.hostname not in ("xfit.cz","www.xfit.cz")
            or url.username or url.password or url.port or url.query
            or url.fragment or url.path.rstrip("/") != "/" + SLUG):
        raise PublishError("Unexpected canonical WordPress permalink")
    raw = (p.get("content") or {}).get("raw")
    if (not isinstance(raw, str) or not 1000 < len(raw)
            or len(raw.encode("utf-8")) > MAX_BYTES or MARKER not in raw):
        raise PublishError("Missing or unexpected owned content")
    old, new = edit["original"], edit["replacement"]
    if raw.count(old) == 0 and raw.count(new) == 1:
        return {"mode":"already_applied","before":raw,"after":raw,
                "hash":digest(raw),"modified":p.get("modified_gmt")}
    if raw.count(old) != 1 or raw.count(new) != 0:
        raise PublishError("Live goal section drifted or is repeated")
    changed = raw.replace(old, new, 1)
    if changed.replace(new, old, 1) != raw:
        raise PublishError("Nonreversible source change")
    a, b = Inspector(), Inspector()
    a.feed(raw)
    b.feed(changed)
    if a.headers != b.headers or a.images != b.images:
        # The source heading/image list must remain unchanged; links are
        # checked as an exact inserted subsequence below.
        raise PublishError("Headings/images unexpectedly changed")
    # Other parts of the same article may ALREADY link to the same
    # destinations. Removing URLs by value would erase an unrelated earlier
    # occurrence and falsely reject a correct patch. Compare exact positions
    # across the one immutable splice, not set/list multiset membership.
    left,right=raw.split(old,1)
    prefix,suffix=Inspector(),Inspector()
    prefix.feed(left)
    suffix.feed(right)
    expected=prefix.links+[(href,"") for href in LINKS]+suffix.links
    if b.links != expected:
        raise PublishError("Non-goal link identity or order changed")
    check_document({"content":changed})
    return {"mode":"update","before":raw,"after":changed,
            "hash":digest(raw),"modified":p.get("modified_gmt")}


def snapshot():
    edit=proposal()
    state=prepare(remote(),edit)
    if BACKUP.exists():
        raise PublishError("Rollback backup already exists")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({
        "schema":1,"post_id":POST_ID,"slug":SLUG,
        "revision_sha":digest(REVISION.read_text(encoding="utf-8")),
        "mode":state["mode"],"before_sha":state["hash"],
        "after_sha":digest(state["after"]),
        "original_raw":state["before"],"modified":state["modified"],
        "remote_writes":0,
    },ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"BEGINNER_GOALS_BACKUP_READY",
                      "post_id":POST_ID,"write_needed":state["mode"]=="update",
                      "remote_writes":0}))


def verify_public(*,reader=None):
    """Check only the real public article for the exact new visible path."""
    def accepted(body):
        if not isinstance(body, str):
            return False
        text=" ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())
        if not all(t in text for t in TARGET_TEXT):
            return False
        if not all(('href="' + link + '"') in body for link in LINKS):
            return False
        # A WordPress-sanitized <details> with missing open attribute makes
        # the most useful 'no-buy' answer invisible, so reject it.
        match = re.search(r"<details\b([^>]*)>\s*<summary>\s*<strong>Chci začít cvičit",
                          body,re.I)
        return bool(match and re.search(r"\bopen(?:\s|=|$)", match.group(1),re.I))
    if reader is not None:
        return accepted(reader(URL))
    for attempt in range(3):
        req=urllib.request.Request(URL,headers={
            "User-Agent":"XFITBeginnerGoalReadback/1.0",
            "Cache-Control":"no-cache","Pragma":"no-cache"})
        try:
            with urllib.request.urlopen(req,timeout=25) as response:
                final=urllib.parse.urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https"
                        or final.hostname not in ("xfit.cz","www.xfit.cz")
                        or final.username or final.password or final.port
                        or final.query or final.fragment
                        or final.path.rstrip("/") != "/" + SLUG):
                    raise PublishError("Public article redirected or changed identity")
                data=response.read(2_500_001)
                if len(data) > 2_500_000:
                    raise PublishError("Public page too large")
                if accepted(data.decode("utf-8",errors="replace")):
                    return True
        except (OSError,ValueError) as exc:
            if attempt == 2:
                raise PublishError("Public body readback unavailable") from exc
        if attempt < 2:
            time.sleep(3)
    return False


def apply():
    if not BACKUP.exists():
        raise PublishError("Mandatory rollback snapshot missing")
    edit=proposal()
    manifest=json.loads(BACKUP.read_text(encoding="utf-8"))
    if (manifest.get("schema")!=1 or manifest.get("post_id")!=POST_ID
            or manifest.get("slug")!=SLUG or manifest.get("remote_writes")!=0
            or manifest.get("revision_sha")!=digest(
                REVISION.read_text(encoding="utf-8"))):
        raise PublishError("Incorrect rollback manifest")
    current=prepare(remote(),edit)
    if (current["mode"]!=manifest.get("mode")
            or current["before"]!=manifest.get("original_raw")
            or current["hash"]!=manifest.get("before_sha")
            or current["modified"]!=manifest.get("modified")
            or digest(current["after"])!=manifest.get("after_sha")):
        raise PublishError("WordPress source changed after backup; do not write")
    if current["mode"]=="already_applied":
        if not verify_public():
            raise PublishError("Already-applied WordPress source not public")
        print(json.dumps({"state":"ALREADY_APPLIED_NO_WRITE","post_id":POST_ID,
                          "public_site_modified":False,"post_attempts":0,"url":URL}))
        return
    write_error=False
    try:
        accepted=wp_request(normalized_base(),"posts/"+str(POST_ID),
                            payload={"content":current["after"]})
        if (not isinstance(accepted,dict)
                or accepted.get("id")!=POST_ID or accepted.get("status")!="publish"):
            write_error=True
    except (PublishError,OSError,ValueError,TypeError,KeyError):
        write_error=True
    # Always reconcile after one ambiguous POST, do not retry.
    try:
        after=remote()
        if (after.get("id")!=POST_ID or after.get("slug")!=SLUG
                or after.get("status")!="publish"):
            raise PublishError("WordPress readback identity drift")
        raw=(after.get("content") or {}).get("raw")
        final_sha=digest(raw) if isinstance(raw,str) else None
    except (PublishError,OSError,ValueError,TypeError,KeyError):
        print(json.dumps({"state":"BLOCKED_MANUAL_REVIEW","post_id":POST_ID,
                          "reason":"readback_unknown","write_response_uncertain":write_error}))
        raise PublishError("Post final state unknown; no blind retry")
    if final_sha == current["hash"]:
        print(json.dumps({"state":"UNRESOLVED_UNCHANGED","post_id":POST_ID,
                          "post_attempts":1,"public_site_modified":False}))
        raise PublishError("Single attempted WordPress write left content unchanged")
    if final_sha != digest(current["after"]):
        print(json.dumps({"state":"BLOCKED_MANUAL_REVIEW","post_id":POST_ID,
                          "reason":"unexpected_body_after_write","post_attempts":1}))
        raise PublishError("Unexpected WordPress modification after write")
    if not verify_public():
        print(json.dumps({"state":"API_VERIFIED_PUBLIC_STALE","post_id":POST_ID,
                          "post_attempts":1,"public_site_modified":True}))
        raise PublishError("Published source not yet visible on public page")
    print(json.dumps({"state":"PUBLIC_VERIFIED","post_id":POST_ID,
                      "slug":SLUG,"url":URL,"posts_changed":1,
                      "new_posts":0,"post_attempts":1,
                      "new_goal_links":len(LINKS),"open_no_buy_answer":True,
                      "public_site_modified":True,"deletes":0,"redirects":0}))


if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","apply"):
            raise PublishError("Usage: snapshot|apply")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,OSError,ValueError,TypeError,KeyError) as exc:
        print("XFIT_BEGINNER_RELEASE_ERROR: "+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
