#!/usr/bin/env python3
"""Read-only inventory for two high-intent protein pages before editing them."""
import hashlib,json,html,re
from scripts.wp_publish import normalized_base,wp_request
IDS=[13717,13734]
def clean(s):
    return " ".join(html.unescape(re.sub("<[^>]+>"," ",s or "")).split())
def main():
    out=[]
    for id in IDS:
        p=wp_request(normalized_base(),"posts/"+str(id)+"?context=edit&_fields=id,slug,status,title,content,excerpt,modified,link,featured_media,categories")
        raw=(p.get("content") or {}).get("raw","")
        text=clean(raw)
        out.append({
          "id":id,"slug":p.get("slug"),"status":p.get("status"),
          "title":(p.get("title") or {}).get("raw"),"modified":p.get("modified"),
          "body_chars":len(raw),"plain_words":len(text.split()),
          "sha256":hashlib.sha256(raw.encode()).hexdigest(),
          "featured_media":p.get("featured_media"),"categories":p.get("categories"),
          "existing_headings":re.findall(r"<h[2-3][^>]*>(.*?)</h[2-3]>",raw,re.S|re.I)[:16],
          "existing_affiliate_links":len(re.findall("namaximum.cz|affial.com",raw,re.I)),
          "text_preview":text[:3500],
          "url":p.get("link")
        })
    print(json.dumps({"state":"protein_original_review","posts":out,"remote_writes":0},ensure_ascii=False))
if __name__=="__main__":main()
