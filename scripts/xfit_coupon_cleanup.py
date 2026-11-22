#!/usr/bin/env python3
"""Bounded rollback-safe removal of obsolete 2022 su_button promos only."""
import hashlib,json,re,sys,time
from pathlib import Path
from urllib.parse import urlencode
from scripts.wp_publish import PublishError,normalized_base,wp_request
from scripts.xfit_public_coupon_watch import exact_article_url,expected_url,probe

MAX_COUNT=8
# This post repeatedly refused a safe WP REST write while all neighbors succeeded.
# Quarantine until its encoding/permissions are inspected independently.
# WP 11595 was unchanged in run 42465256593 after seven successful edits;
# recovery is isolated to one post; see issue #75.
# WP 11264 was the sole unchanged item in run 43630700797 (14 Nov):
# seven neighboring posts were verified, but its write_request did not persist.
# Keep it out of the recurring batch while one-post recovery investigates it.
# WP 10995 remained byte-for-byte unchanged after its one guarded POST in
# 44793630877; seven neighboring posts were independently public-verified.
# Never attempt 10995 again in the recurring wave. It requires its own pinned
# diagnostic/recovery, just like the earlier isolated failures above.
# WP #10860 was demonstrably unchanged after exactly one POST in run
# 45008217157 (2026-11-22); seven neighboring posts were public verified.
# Do not reattempt it in future recurring waves; needs isolated diagnosis.
QUARANTINE_IDS={11945,11595,11264,10995,10860}
BACKUP=Path("reports/backups/xfit-expired-coupon-wave01.json")
PROMO=re.compile(r"\[su_button\b[^\]]{0,1200}\][^\[]*?5NM2022\[/su_button\]",re.I|re.S)
def sha(s):return hashlib.sha256(s.encode("utf-8")).hexdigest()
def stripped(raw):
    return PROMO.subn("",raw)
def retry_read(path):
    for attempt in range(4):
        try:
            data=wp_request(normalized_base(),path)
            time.sleep(0.35)
            return data
        except PublishError as exc:
            if "URLError" not in str(exc) and "HTTP 503" not in str(exc) and "HTTP 502" not in str(exc) and "HTTP 504" not in str(exc):
                raise
            if attempt==3:raise
            time.sleep(min(2**attempt,6))
    raise PublishError("Read failed")
def get_post(id):
    return retry_read("posts/"+str(id)+"?context=edit&_fields=id,slug,status,content,link")
def validate(p,e=None):
    if (p.get("status")!="publish" or type(p.get("id")) is not int
            or not isinstance(p.get("slug"),str)
            or not exact_article_url(p.get("link"),p["slug"])):
        raise PublishError("Unexpected public post identity/host/status")
    if e and (p.get("id")!=e["id"] or p.get("slug")!=e["slug"]):
        raise PublishError("ID/slug changed")
    text=(p.get("content") or {}).get("raw") or ""
    if e and sha(text)!=e["before_sha256"]:
        raise PublishError("Original source hash changed")
    return text


def public_readback(entries, *, reader=None, sleeper=None):
    """Independently prove the live, exact canonical page lacks visible code.

    Runs only after *authenticated* successful reads; never updates WordPress.
    A stale cache or unknown response is not a verified clean public article.
    """
    reader = reader or probe
    sleeper = sleeper or time.sleep
    verified=[];unverified=[]
    for entry in entries:
        post_id,slug=entry["id"],entry["slug"]
        if (type(post_id) is not int or not isinstance(slug,str)
                or not exact_article_url(entry.get("link"),slug)):
            raise PublishError("Public verification input identity mismatch")
        expected=expected_url(slug)
        status="UNVERIFIED_FETCH"
        for attempt in range(3):
            try:
                result=reader(post_id,slug)
                if (not isinstance(result,dict) or result.get("id")!=post_id
                        or result.get("url")!=expected):
                    status="UNVERIFIED_IDENTITY"
                else:
                    status=result.get("state")
                    if not isinstance(status,str):
                        status="UNVERIFIED_RESPONSE"
                    if (status=="PUBLIC_NO_COUPON_OBSERVED"
                            and result.get("visible_mentions")!=0):
                        status="UNVERIFIED_RESPONSE"
                if status=="PUBLIC_NO_COUPON_OBSERVED":
                    verified.append(post_id)
                    break
            except (OSError,ValueError,TypeError,KeyError,PublishError):
                status="UNVERIFIED_FETCH"
            if attempt<2:
                sleeper(4)
        else:
            unverified.append({"id":post_id,"state":status})
    return {"verified_post_ids":verified,"not_verified":unverified,
            "public_verified_count":len(verified)}
def snapshot():
    query=urlencode({"search":"5NM2022","context":"edit","status":"publish",
                    "per_page":100,"_fields":"id,slug,status,content,link"})
    posts=retry_read("posts?"+query)
    if not isinstance(posts,list):raise PublishError("Unexpected WordPress search response")
    entries=[];ids=set()
    for p in posts:
        if p.get("id") in ids or p.get("id") in QUARANTINE_IDS:continue
        ids.add(p.get("id"))
        source=validate(p)
        result,count=stripped(source)
        if count<1 or len(result)<500 or "5nm2022" in result.casefold():continue
        entries.append({"id":p["id"],"slug":p["slug"],"link":p["link"],
          "original_raw":source,"before_sha256":sha(source),"after_sha256":sha(result),
          "shortcodes_removed":count})
        if len(entries)>=MAX_COUNT:break
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    if BACKUP.exists():raise PublishError("Rollback backup already exists")
    BACKUP.write_text(json.dumps({"wave":"coupon01","entries":entries,
      "source":"authenticated preflight","remote_writes":0},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"state":"backup_ready","post_count":len(entries),
      "shortcodes_to_remove":sum(x["shortcodes_removed"] for x in entries),"no_remote_writes":True}))
def apply():
    if not BACKUP.exists():raise PublishError("Pre-write rollback backup missing")
    doc=json.loads(BACKUP.read_text(encoding="utf-8"))
    entries=doc["entries"]
    if doc.get("wave")!="coupon01" or len(entries)>MAX_COUNT or len({e["id"] for e in entries})!=len(entries):
        raise PublishError("Unexpected backup manifest")
    for e in entries:
        before=validate(get_post(e["id"]),e)
        after,count=stripped(before)
        if count!=e["shortcodes_removed"] or sha(after)!=e["after_sha256"]:
            raise PublishError("Preflight coupon replacement changed")
    # Each article is an independent atomic action. Earlier posts with
    # authenticated successful readback must remain fixed even if WEDOS
    # times out later in the wave.
    successful=[]
    uncertain=[]
    failed=[]
    for e in entries:
        after,_=stripped(e["original_raw"])
        attempted_write=False
        stage="prewrite"
        try:
            stage="write_request"
            attempted_write=True
            response=wp_request(normalized_base(),"posts/"+str(e["id"]),payload={"content":after})
            if response.get("id")!=e["id"] or response.get("status")!="publish":
                raise PublishError("write_response_identity")
            stage="readback"
            check=get_post(e["id"])
            if check.get("slug")!=e["slug"] or sha((check.get("content") or {}).get("raw",""))!=e["after_sha256"]:
                raise PublishError("readback_hash_mismatch")
            successful.append(e)
        except (PublishError,OSError,ValueError,KeyError) as error:
            # A failed POST might have committed. Always inspect its final
            # state before deciding to retry, skip, or compensate.
            try:
                current=get_post(e["id"])
                current_text=(current.get("content") or {}).get("raw","")
                current_hash=sha(current_text)
                if current.get("slug")==e["slug"] and current_hash==e["after_sha256"]:
                    successful.append(e)
                    continue
                if current.get("slug")==e["slug"] and current_hash==e["before_sha256"]:
                    failed.append({"id":e["id"],"stage":stage,"state":"unchanged"})
                    continue
                # Do NOT clobber concurrent editors / Wordpress transformed
                # markup whose byte identity can no longer be trusted.
                uncertain.append({"id":e["id"],"stage":stage,"state":"manual_review_needed"})
            except (PublishError,OSError,ValueError,KeyError):
                uncertain.append({"id":e["id"],"stage":stage,"state":"readback_unavailable"})
        # Large cheap-hosting sites may throttle write/read traffic.
        time.sleep(1.1)
    # Public page validation is independent of WP REST. A successful API
    # write does not imply a fresh cached HTML page for readers.
    proof=public_readback(successful)
    report={"state":"coupon_wave_partial" if failed or uncertain else "coupon_wave_verified",
        "posts_changed":len(successful),
        "shortcodes_removed":sum(e["shortcodes_removed"] for e in successful),
        "unchanged_failures":failed,"uncertain_posts":uncertain,
        "public_verified_post_ids":proof["verified_post_ids"],
        "public_not_verified":proof["not_verified"],
        "deletes":0,"redirects":0}
    if proof["not_verified"]:
        report["state"]="coupon_wave_public_unverified"
    print(json.dumps(report,ensure_ascii=False))
    # Uncertain writes must remain visible as a failure to operators.
    if uncertain:
        raise PublishError("One or more coupon writes have unknown final state")
    # Deterministic partial failure is not a successful batch, but previous
    # verified changes were intentionally kept; next run may continue.
    if failed:
        raise PublishError("Some posts stayed unchanged; successful posts preserved")
    if proof["not_verified"]:
        raise PublishError("Authenticated writes verified, public cached pages not all proven clean")

if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","apply"):raise PublishError("Select snapshot|apply")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,ValueError,OSError,KeyError,TypeError) as e:
        print("XFIT_COUPON_ERROR: "+str(e),file=sys.stderr)
        sys.exit(2)
