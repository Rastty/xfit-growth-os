"""Add one reviewed responsive chooser to the existing functional training URL."""
import hashlib
import json
import sys
from pathlib import Path
from scripts.wp_publish import normalized_base, wp_request, PublishError, verify_public, editorial_links
from scripts.xfit_legacy_mat_release import stable_metadata
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_legacy_functional_training import read, URL, TITLE, MARKER
from scripts.xfit_equipment_refresh import read_source as read_equipment, URL as GEAR, TITLE as GEAR_TITLE
from scripts import (xfit_legacy_arm_training as arm, xfit_legacy_glute_training as glute,
                     xfit_legacy_thigh_training as thigh, xfit_legacy_calf_training as calf,
                     xfit_legacy_home_gym_workout as gym, xfit_legacy_muscle_recovery as recovery)

POST_ID = 638
BLOCK = Path("content/revisions/home-training-chooser.html")
BACKUP = Path("reports/backups/xfit-home-training-chooser-original.json")
CHOOSER = 'id="xfit-home-training-chooser-v1"'
ANCHOR = "<h2>Co znamená funkční trénink podle odborníků</h2>"
PLAN_OLD = "<h3>Modelová dvacetiminutová jednotka</h3>"
PLAN_NEW = '<h3 id="xfit-home-first-session" style="scroll-margin-top:100px;">Modelová dvacetiminutová jednotka</h3>'
TARGETS = ((arm,9362),(glute,951),(thigh,994),(calf,13285),(gym,1002),(recovery,626))

def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def splice(raw):
    if not raw.startswith('<section '+MARKER+'>') or raw.count(MARKER)!=1:
        raise PublishError("Expected reviewed functional training source")
    if CHOOSER in raw or "xfit-home-first-session" in raw:
        raise PublishError("Already revised or ambiguous chooser marker")
    if raw.count(ANCHOR)!=1 or raw.count(PLAN_OLD)!=1:
        raise PublishError("Exact reviewed placement unavailable")
    block=BLOCK.read_text(encoding="utf-8").strip()
    expected=["#xfit-home-first-session",arm.URL,glute.URL,thigh.URL,calf.URL,GEAR,gym.URL,recovery.URL]
    if block.count(CHOOSER)!=1 or editorial_links(block)!=expected:
        raise PublishError("Reviewed route list differs")
    new=raw.replace(ANCHOR,block+"\n"+ANCHOR,1).replace(PLAN_OLD,PLAN_NEW,1)
    if new.replace(block+"\n","",1).replace(PLAN_NEW,PLAN_OLD,1)!=raw:
        raise PublishError("Unexpected change outside reviewed insertion")
    check_document({"content":new},commercial=False)
    return new

def snapshot():
    row=read()
    if row["id"]!=POST_ID:raise PublishError("Unexpected post ID")
    verify_public(URL,TITLE,row["content"]["rendered"])
    new=splice(row["content"]["raw"])
    for module,pid in TARGETS:
        target=module.read()
        if target["id"]!=pid or target["link"]!=module.URL or module.MARKER not in target["content"]["raw"]:
            raise PublishError("Reviewed destination missing: "+module.SLUG)
        verify_public(module.URL,target["title"]["raw"],target["content"]["rendered"])
    gear,_=read_equipment()
    verify_public(GEAR,GEAR_TITLE,gear)
    if BACKUP.exists():raise PublishError("Never overwrite backup")
    BACKUP.parent.mkdir(parents=True,exist_ok=True)
    BACKUP.write_text(json.dumps({"schema":1,"before":row,"after_sha":sha(new),"wordpress_writes":0},ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"HOME_TRAINING_CHOOSER_BACKUP_READY","post_id":POST_ID,"verified_destinations":7,"wordpress_writes":0}))

def apply():
    saved=json.loads(BACKUP.read_text(encoding="utf-8"))
    before=read()
    new=splice(before["content"]["raw"])
    if before["id"]!=POST_ID or saved.get("schema")!=1 or saved.get("wordpress_writes")!=0 or saved.get("before")!=before or saved.get("after_sha")!=sha(new):
        raise PublishError("Source changed after backup")
    try:
        wp_request(normalized_base(),"posts/"+str(POST_ID),payload={"content":new})
    except (PublishError,OSError,ValueError,TypeError):
        pass
    after=read()
    if after["content"]["raw"]!=new or stable_metadata(after)!=stable_metadata(before):
        raise PublishError("Exact source and metadata not verified; no retry")
    verify_public(URL,TITLE,after["content"]["rendered"])
    print(json.dumps({"state":"PUBLIC_HOME_TRAINING_CHOOSER_VERIFIED","post_id":POST_ID,"url":URL,"choices":8,"verified_destinations":7,"posts_changed":1,"post_attempts":1,"public_site_modified":True,"new_posts":0}))

if __name__=="__main__":
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("snapshot","apply"):raise PublishError("Unknown scope")
        (snapshot if sys.argv[1]=="snapshot" else apply)()
    except (PublishError,OSError,ValueError,KeyError,TypeError) as exc:
        print("XFIT_HOME_TRAINING_CHOOSER_BLOCKED: "+(str(exc) if isinstance(exc,PublishError) else type(exc).__name__))
        raise SystemExit(2)
