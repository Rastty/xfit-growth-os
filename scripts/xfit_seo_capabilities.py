#!/usr/bin/env python3
"""Read-only WordPress SEO capability inventory. Never print auth or secret data."""
import json
import re
import urllib.request
from urllib.parse import urlencode
from scripts.wp_publish import normalized_base, wp_request, PublishError

SLUGS=("xfit-os-doplnky-pro-zacatecniky","xfit-os-kreatin-poradce",
       "xfit-os-syrovatkovy-protein-porovnani","xfit-os-protein-guide")

def main():
    base=normalized_base()
    result={"stage":"seo_capabilities_read_only","wp_mutations":0}
    try:
        plugins=wp_request(base,"plugins?context=edit&per_page=100&_fields=plugin,name,status")
        result["plugins"]=sorted([{"slug":p.get("plugin"),"name":p.get("name"),"status":p.get("status")} for p in plugins],key=lambda x:str(x["slug"]))
    except PublishError as e:
        result["plugins"]="unavailable:"+str(e)
    rows=[]
    for slug in SLUGS:
        posts=wp_request(base,"posts?context=edit&slug="+slug+"&per_page=1")
        if not posts:continue
        p=posts[0]
        keys=sorted(k for k in p if not k.startswith("_"))
        meta_keys=sorted((p.get("meta") or {}).keys()) if isinstance(p.get("meta"),dict) else []
        rows.append({"slug":slug,"id":p["id"],"top_level_fields":keys,
           "registered_meta_keys":meta_keys,"excerpt_len":len((p.get("excerpt") or {}).get("raw","")),
           "has_yoast_head_json":bool(p.get("yoast_head_json")),"has_rank_math_head":bool(p.get("rank_math_head"))})
    result["pages"]=rows
    # Public page meta presence, without leaking article body.
    request=urllib.request.Request(base+"/xfit-os-kreatin-poradce/",
        headers={"User-Agent":"XfitGrowthOS-SEOCapability/1.0"})
    with urllib.request.urlopen(request,timeout=25) as response:
        raw=response.read(500000).decode("utf-8","replace")
    head=raw.split("</head>",1)[0]
    result["public_meta_count"]=len(re.findall(r'<meta\s+name=["\\x27]description',head,re.I))
    result["has_og_description"]="og:description" in head
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__":main()
