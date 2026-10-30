#!/usr/bin/env python3
"""Read-only Redirection API diagnosis with official v1 list parameter variants.

Avoid exposing live redirect targets or user/IP logs in public CI.
"""
import base64,json,os
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from scripts.wp_publish import normalized_base,PublishError

def fetch(path):
    base=normalized_base()
    username=os.getenv("WP_USERNAME","").strip()
    password=os.getenv("WP_APP_PASSWORD","").strip()
    if not username or not password:raise PublishError("Missing WordPress credentials")
    headers={
      "Authorization":"Basic "+base64.b64encode((username+":"+password).encode()).decode(),
      "Accept":"application/json",
      "User-Agent":"XfitGrowthOS-RedirectionDiagnostic/1.1"
    }
    req=Request(base+"/wp-json/redirection/v1/"+path,headers=headers)
    try:
        with urlopen(req,timeout=25) as response:
            data=json.load(response)
            return {"http":response.status,"kind":type(data).__name__,
              "keys":sorted(data.keys()) if isinstance(data,dict) else [],
              "total":data.get("total") if isinstance(data,dict) else None,
              "count":len(data.get("items",[])) if isinstance(data,dict) and isinstance(data.get("items"),list) else None}
    except HTTPError as error:
        # Only stable public WordPress error code: no response body or URL leaks.
        code=None
        try:
            body=json.loads(error.read(2048).decode("utf-8","replace"))
            if isinstance(body,dict):
                identifier=body.get("code","")
                if isinstance(identifier,str) and len(identifier)<100:
                    code=identifier
        except (ValueError,TypeError):pass
        return {"http":error.code,"wp_error_code":code}
    except (URLError,OSError,ValueError) as error:
        return {"http":"unavailable","type":type(error).__name__}

if __name__=="__main__":
    result={
       "state":"redirection_rest_diagnostics_read_only",
       "group":fetch("group?per_page=10&page=0"),
       "redirect_default":fetch("redirect"),
       "redirect_page_zero":fetch("redirect?per_page=25&page=0"),
       "redirect_page_one":fetch("redirect?per_page=25&page=1"),
       "redirect_filter":fetch("redirect?per_page=25&page=0&orderby=id&direction=desc"),
       "settings":fetch("setting"),
       "no_wp_writes":True
    }
    print(json.dumps(result,ensure_ascii=False))
