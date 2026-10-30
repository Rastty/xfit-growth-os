#!/usr/bin/env python3
"""Find expired 2022 discount code in live WordPress source; no edits."""
import json
import re
import urllib.parse
from scripts.wp_publish import normalized_base, wp_request
COUPON="5NM2022"
def run():
    base=normalized_base()
    data=[]
    for page in range(1,11):
        query=urllib.parse.urlencode({"search":COUPON,"context":"edit","status":"publish",
          "per_page":100,"page":page,"_fields":"id,slug,title,link,status,content,modified"})
        try:posts=wp_request(base,"posts?"+query)
        except Exception as e:
            if page>1 and "HTTP 400" in str(e):break
            raise
        for p in posts:
            raw=(p.get("content") or {}).get("raw") or ""
            if COUPON.lower() in raw.lower():
                data.append({"id":p["id"],"slug":p["slug"],"link":p.get("link"),
                    "coupon_mentions":raw.lower().count(COUPON.lower()),
                    "shortcode_mentions":len(re.findall(r"\[su_button[^\]]{0,700}\][^\[]*5NM2022\[/su_button\]",raw,re.I))})
        if len(posts)<100:break
    report={"state":"legacy_coupon_read_only","matched_posts":len(data),
      "total_coupon_mentions":sum(x["coupon_mentions"] for x in data),
      "total_button_shortcodes":sum(x["shortcode_mentions"] for x in data),
      "sample":data[:15],"no_remote_writes":True}
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":run()
