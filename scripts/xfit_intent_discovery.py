#!/usr/bin/env python3
"""Find credible existing Xfit posts that should link to relevant decision tools.

Read-only. Candidate ranking is editorial heuristic, not traffic attribution.
Use this result only to select and review a bounded backup-first linking wave.
"""
import json,re
from urllib.parse import urlencode
from scripts.wp_publish import normalized_base,wp_request,PublishError,plain
CAMPAIGNS={
  "kreatin":"https://xfit.cz/xfit-os-kreatin-poradce/",
  "protein":"https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
}
ALREADY={"xfit-os-doplnky-pro-zacatecniky","xfit-os-kreatin-poradce",
         "xfit-os-protein-guide","xfit-os-syrovatkovy-protein-porovnani",
         "xfit-os-kreatin-nebo-protein","kreatin-a-jeho-vliv-na-ledviny-a-jatra"}
def clean(text):return " ".join(plain(text or "").split())
def main():
    result={"state":"internal_link_opportunities_read_only",
        "audited_queries":list(CAMPAIGNS),"candidates":[],"remote_writes":0}
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
