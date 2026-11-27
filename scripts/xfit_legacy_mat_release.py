"""Pinned legacy editorial rewrites: two separately reviewed Pilates mat pages."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from scripts.wp_publish import PublishError, normalized_base, wp_request, verify_public, editorial_links
from scripts.xfit_editorial_gate import check_document
from scripts.xfit_equipment_refresh import read_source, URL, TITLE
from scripts.xfit_affiliate_public_audit import read_public_page

TARGET = URL + "#xfit-gear-mat"

@dataclass(frozen=True)
class Scope:
    pid: int
    slug: str
    old_sha: str
    modified: str
    file: str
    lane: str = "mat"

    @property
    def target(self):
        return TARGET if self.lane == "mat" else "https://xfit.cz/xfit-os-kreatin-poradce/"

    @property
    def cta(self):
        return "Zobrazit aktuální nabídky podložek" if self.lane == "mat" else "Zobrazit aktuální nabídky kreatinu"

    @property
    def url(self):
        return "https://xfit.cz/" + self.slug + "/"

    @property
    def marker(self):
        return "xfit-legacy-" + self.lane + "-revision-" + str(self.pid) + "-20261127"

    @property
    def backup(self):
        return Path("reports/backups/xfit-legacy-" + self.lane + "-" + str(self.pid) + ".json")

SCOPES = {
    "3377": Scope(3377, "vybaveni-do-fitka-jak-vybrat-vhodnou-podlozku-na-pilates-cviceni",
        "f561e45ec5c75321e15ebb2cfa679675d7dff3b5e2954e5fb719a2d7a67da858",
        "2023-04-19T04:03:58", "content/revisions/pilates-mat-home-studio-3377.json"),
    "7487": Scope(7487, "jak-vybrat-spravnou-podlozku-pro-cviceni-pilates",
        "99f663d2eb6065a0820047ead13b1dda46051e42cea883a5a78ef7e989d01d21",
        "2023-05-15T10:40:02", "content/revisions/pilates-mat-choice-7487.json"),
}

def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def content(cfg):
    doc=json.loads(Path(cfg.file).read_text(encoding="utf-8"))
    body=doc.get("content")
    if (doc.get("wp_post_id")!=cfg.pid or doc.get("slug")!=cfg.slug
            or not isinstance(body,str) or body.count(cfg.marker)!=1
            or editorial_links(body).count(cfg.target)!=1
            or any("namaximum.cz" in u for u in editorial_links(body))
            or "5NM2022" in body
            or re.search(r"<\s*(?:script|iframe|form)\b|\bon\w+\s*=",body,re.I)):
        raise PublishError("Reviewed revision identity or safety failed")
    check_document(doc, commercial=False)
    return body

def identity(cfg, post):
    if (not isinstance(post,dict) or type(post.get("id")) is not int or post["id"]!=cfg.pid
            or post.get("slug")!=cfg.slug or post.get("link")!=cfg.url
            or post.get("status")!="publish" or not isinstance((post.get("title") or {}).get("raw"),str)
            or not isinstance((post.get("content") or {}).get("raw"),str)
            or not isinstance(post.get("modified_gmt"),str)):
        raise PublishError("Pinned existing post identity mismatch")
    return post

def read(cfg):
    return identity(cfg,wp_request(normalized_base(),f"posts/{cfg.pid}?context=edit&_fields=id,slug,status,link,title,content,excerpt,categories,tags,sticky,featured_media,modified_gmt"))

def prepare(cfg,post):
    identity(cfg,post)
    raw=post["content"]["raw"]
    new=content(cfg)
    if raw==new:
        return raw,new
    if sha(raw)!=cfg.old_sha or post["modified_gmt"]!=cfg.modified or cfg.marker in raw:
        raise PublishError("Source differs from independent reviewed SHA; no write")
    return raw,new

def stable_metadata(post):
    """Compare persisted metadata, not content-derived REST render output.

    WordPress generates excerpt.rendered from content when excerpt.raw is
    empty. That must change after a rewrite; the stored excerpt must not.
    Require all requested identity/metadata fields; do not silently drop
    raw title or excerpt, categories, tags or featured media.
    """
    values = {}
    for key in ("id", "slug", "status", "link", "categories", "tags", "sticky", "featured_media"):
        if key not in post:
            raise PublishError("Missing stored metadata field")
        values[key] = post[key]
    for key in ("title", "excerpt"):
        obj = post.get(key)
        if not isinstance(obj, dict) or not isinstance(obj.get("raw"), str):
            raise PublishError("Missing stored title or excerpt")
        values[key] = obj["raw"]
    return values


def prove_prior_release(cfg, backup_path):
    """Independent GET-only proof from the original immutable release backup."""
    saved=json.loads(Path(backup_path).read_text(encoding="utf-8"))
    before=identity(cfg,saved.get("before"))
    old=before["content"]["raw"]
    expected=content(cfg)
    if (saved.get("schema")!=1 or saved.get("id")!=cfg.pid
            or saved.get("wordpress_writes")!=0 or sha(old)!=cfg.old_sha
            or before["modified_gmt"]!=cfg.modified
            or saved.get("raw_sha")!=sha(old) or saved.get("after_sha")!=sha(expected)):
        raise PublishError("Untrusted original release backup")
    after=read(cfg)
    if after["content"]["raw"]!=expected:
        raise PublishError("Exact intended current article not retained")
    old_meta,new_meta=stable_metadata(before),stable_metadata(after)
    changed=[key for key in old_meta if old_meta[key]!=new_meta[key]]
    render_changed=[key for key in ("title","excerpt")
                    if before[key].get("rendered")!=after[key].get("rendered")]
    print(json.dumps({"state":"LEGACY_MAT_STORED_METADATA_CHECK","post_id":cfg.pid,
        "changed_stored_fields":changed,"changed_rendered_fields":render_changed,
        "original_excerpt_empty":before["excerpt"]["raw"]=="","wordpress_writes":0}))
    if changed:
        raise PublishError("Stored metadata changed; no retry")
    verify_public(cfg.url,after["title"]["raw"],expected)
    public=read_public_page(cfg.slug)
    if TARGET not in editorial_links(public):
        raise PublishError("Missing live target")
    print(json.dumps({"state":"LEGACY_MAT_PRIOR_RELEASE_READONLY_VERIFIED",
        "post_id":cfg.pid,"slug":cfg.slug,"url":cfg.url,
        "original_run_id":46050150293,"stored_metadata_preserved":True,
        "new_posts":0,"wordpress_writes":0,"public_site_modified":False}))


def snapshot(cfg):
    if cfg.lane == "mat":
        gear,_=read_source()
        verify_public(URL,TITLE,gear)
        if 'id="xfit-gear-mat"' not in gear:
            raise PublishError("Missing intended live section")
    elif cfg.lane == "creatine":
        from scripts.xfit_affiliate_public_audit import Cards
        guide=wp_request(normalized_base(),"posts/25455?context=edit&_fields=id,slug,status,link,title,content")
        if (guide.get("id")!=25455 or guide.get("slug")!="xfit-os-kreatin-poradce"
                or guide.get("status")!="publish" or guide.get("link")!=cfg.target):
            raise PublishError("Missing exact live creatine guide")
        verify_public(cfg.target,guide["title"]["raw"],guide["content"]["raw"])
        p=Cards()
        p.feed(read_public_page("xfit-os-kreatin-poradce"))
        if not 2<=len(p.cards)<=6:
            raise PublishError("Missing actual creatine offers")
    else:
        raise PublishError("Unknown release lane")
    post=read(cfg)
    raw,new=prepare(cfg,post)
    if cfg.backup.exists():
        raise PublishError("Never overwrite backup")
    cfg.backup.parent.mkdir(parents=True,exist_ok=True)
    cfg.backup.write_text(json.dumps({"schema":1,"id":cfg.pid,"before":post,
        "raw_sha":sha(raw),"after_sha":sha(new),"wordpress_writes":0},ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"state":"LEGACY_"+cfg.lane.upper()+"_PREWRITE_BACKUP_READY","post_id":cfg.pid,"wordpress_writes":0,"change_required":raw!=new}))

def apply(cfg):
    saved=json.loads(cfg.backup.read_text(encoding="utf-8"))
    before=read(cfg)
    raw,new=prepare(cfg,before)
    if (saved.get("schema")!=1 or saved.get("id")!=cfg.pid or saved.get("wordpress_writes")!=0
            or saved.get("before")!=before or saved.get("raw_sha")!=sha(raw) or saved.get("after_sha")!=sha(new)):
        raise PublishError("Source changed after backup")
    if raw!=new:
        try:
            wp_request(normalized_base(),"posts/"+str(cfg.pid),payload={"content":new})
        except (PublishError,OSError,ValueError,TypeError):
            pass
        after=read(cfg)
        if after["content"]["raw"]!=new or stable_metadata(after)!=stable_metadata(before):
            raise PublishError("Exact source and metadata not verified; no retry")
    verify_public(cfg.url,before["title"]["raw"],new)
    public=read_public_page(cfg.slug)
    if cfg.target not in editorial_links(public) or cfg.cta not in public:
        raise PublishError("Exact public buyer route not verified")
    print(json.dumps({"state":"PUBLIC_LEGACY_"+cfg.lane.upper()+"_REVISION_VERIFIED","post_id":cfg.pid,"slug":cfg.slug,
        "url":cfg.url,"post_attempts":int(raw!=new),"posts_changed":int(raw!=new),
        "new_posts":0,"deletes":0,"redirects":0,"public_site_modified":raw!=new}))

if __name__=="__main__":
    try:
        if len(sys.argv)!=3 or sys.argv[1] not in SCOPES or sys.argv[2] not in {"snapshot","apply"}:
            raise PublishError("Unknown pinned revision")
        (snapshot if sys.argv[2]=="snapshot" else apply)(SCOPES[sys.argv[1]])
    except (PublishError,ValueError,OSError,KeyError,TypeError) as exc:
        print("XFIT_LEGACY_MAT_REVISION_BLOCKED: "+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
