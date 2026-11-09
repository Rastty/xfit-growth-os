#!/usr/bin/env python3
"""Find credible existing Xfit posts that should link to relevant decision tools.

Read-only. Candidate ranking is editorial heuristic, not traffic attribution.
Use this result only to select and review a bounded backup-first linking wave.
"""
import json,re
from html.parser import HTMLParser
from urllib.parse import urlencode,urlsplit
from scripts.wp_publish import normalized_base,wp_request,PublishError,plain
CAMPAIGNS={
  "kreatin":"https://xfit.cz/xfit-os-kreatin-poradce/",
  "protein":"https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
}
ALREADY={"xfit-os-doplnky-pro-zacatecniky","xfit-os-kreatin-poradce",
         "xfit-os-protein-guide","xfit-os-syrovatkovy-protein-porovnani",
         "xfit-os-kreatin-nebo-protein","kreatin-a-jeho-vliv-na-ledviny-a-jatra"}
def clean(text):return " ".join(plain(text or "").split())

# Owner-provided historical GSC/GA4 review: public slugs only, no private metrics.
# These are editorial review candidates, not permission for automatic WP writes.
PRIORITY_LEGACY=(
    ("nejlepsi-zpusoby-jak-kombinovat-kreatin-s-dalsimi-doplnky-stravy-a-treninkovymi-metodami-pro-uspech-v-fitness",
     "https://xfit.cz/xfit-os-kreatin-poradce/", "creative-training-decision"),
    ("kreatin-monohydrat-a-jeho-bezpecnostni-rizika-pri-uzivani-jak-se-chranit-pred-nezadoucimi-ucinky",
     "https://xfit.cz/kreatin-a-jeho-vliv-na-ledviny-a-jatra/", "safety-evidence-handoff"),
)


class Anchors(HTMLParser):
    """Count real href destinations, not unlinked URL text or JS attributes."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls=set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.urls.update(value for key,value in attrs
                             if key == "href" and isinstance(value,str))


def links(body):
    parser=Anchors()
    parser.feed(body)
    return parser.urls


def verified_post_identity(post,slug):
    if not isinstance(post,dict) or post.get("status")!="publish":
        return False
    if post.get("slug")!=slug or not isinstance(post.get("id"),int):
        return False
    link=post.get("link") or ""
    try:
        u=urlsplit(link)
    except ValueError:
        return False
    return (u.scheme=="https" and u.netloc=="xfit.cz"
            and not u.query and not u.fragment
            and u.path=="/"+slug+"/")


def inspect_priority(*,request=None):
    """Exactly two bounded WP GETs. Return no article body, secrets or traffic."""
    request=request or wp_request
    out=[]
    for slug,target,intent in PRIORITY_LEGACY:
        item={"slug":slug,"intent":intent,
              "target":target,"state":"UNKNOWN_NO_VERIFIED_SOURCE",
              "target_already_linked":None,"next_action":"RECHECK_SOURCE"}
        try:
            rows=request(normalized_base(),"posts?"+urlencode({
                "slug":slug,"status":"publish","context":"edit","per_page":2,
                "_fields":"id,slug,status,link,title,content,modified"}))
            matches=[p for p in rows if verified_post_identity(p,slug)]
            if len(matches)==1:
                post=matches[0]
                source=(post.get("content") or {}).get("raw")
                if isinstance(source,str) and len(source)>400:
                    already=target in links(source)
                    item.update({"state":"SOURCE_VERIFIED",
                                 "wp_post_id":post["id"],
                                 "target_already_linked":already,
                                 "next_action":("ALREADY_LINKED" if already else
                                                "EDITORIAL_REVIEW_BEFORE_ONE_POST")})
        except (PublishError,OSError,ValueError,TypeError,KeyError):
            # Public diagnostics may not reveal credentials or response bodies.
            pass
        out.append(item)
    return out

def main():
    result={"state":"internal_link_opportunities_read_only",
        "audited_queries":list(CAMPAIGNS),"candidates":[],
        "priority_legacy_link_checks":inspect_priority(),
        "remote_writes":0}
    seen=set()
    for topic,url in CAMPAIGNS.items():
        q=urlencode({"search":topic,"context":"edit","status":"publish","per_page":70,
           "_fields":"id,slug,title,content,excerpt,modified,date,link"})
        rows=wp_request(normalized_base(),"posts?"+q)
        for p in rows:
            id=p.get("id");slug=p.get("slug") or ""
            if id in seen or slug in ALREADY or slug.startswith("xfit-os-"):
                continue
            seen.add(id)
            body=(p.get("content") or {}).get("raw") or ""
            title=clean((p.get("title") or {}).get("raw",""))
            lower=(title+" "+slug).casefold()
            if len(body)<1500 or not any(t in lower for t in ("kreatin","creatine","protein","bílkovin","bilkovin")):
                continue
            target=CAMPAIGNS[topic]
            missing=target not in body
            both=all(x not in body for x in CAMPAIGNS.values())
            score=(3 if any(t in lower for t in ("jak vybrat","jaký","jakou","koupit","účinky","účinnost","dávkování","zkušenosti")) else 0)
            score+=(2 if "kreatin" in lower or "protein" in lower else 0)
            score+=1 if missing else 0
            result["candidates"].append({"id":id,"slug":slug,"title":title[:125],
              "topic":topic,"body_chars":len(body),"already_has_target_link":not missing,
              "already_has_any_product_guide_link":not both,
              "ranking_heuristic":score,"link":p.get("link")})
    result["candidates"].sort(key=lambda x:(-x["ranking_heuristic"],-x["body_chars"]))
    result["candidates"]=result["candidates"][:55]
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    main()
