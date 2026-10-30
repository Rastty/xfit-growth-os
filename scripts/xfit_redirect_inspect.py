#!/usr/bin/env python3
"""Inspect WordPress Redirection plugin REST API read-only before any redirect mutation."""
import base64
import json
import os
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from scripts.wp_publish import normalized_base, PublishError
def fetch(path):
    base=normalized_base()
    user=os.getenv("WP_USERNAME","").strip()
    password=os.getenv("WP_APP_PASSWORD","").strip()
    if not user or not password:raise PublishError("WP app password not configured")
    h={"Authorization":"Basic "+base64.b64encode((user+":"+password).encode()).decode(),
       "User-Agent":"XfitGrowthOS-RedirectionRead/1.0",
       "Accept":"application/json"}
    req=Request(base+"/wp-json/redirection/v1/"+path,headers=h)
    try:
        with urlopen(req,timeout=20) as resp:
            data=json.load(resp)
            return {"status":resp.status,"shape":type(data).__name__,
                    "keys":sorted(data.keys()) if isinstance(data,dict) else [],
                    "count":len(data.get("items",[])) if isinstance(data,dict) else len(data) if isinstance(data,list) else None,
                    "sample_public_fields":[
                        {k:x.get(k) for k in ("id","url","status","action_type","action_code","group_id") if k in x}
                        for x in (data.get("items",[]) if isinstance(data,dict) else data if isinstance(data,list) else [])[:3]
                    ]}
    except HTTPError as e:return {"status":e.code,"error":"endpoint unavailable"}
    except (URLError,ValueError,OSError) as e:return {"status":"error","error_type":type(e).__name__}
if __name__=="__main__":
    print(json.dumps({"state":"redirection_rest_read_only","groups":fetch("group?per_page=10"),
      "redirects":fetch("redirect?per_page=4"),"remote_writes":0},ensure_ascii=False))
