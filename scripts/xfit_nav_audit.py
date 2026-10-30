#!/usr/bin/env python3
"""Read-only WordPress navigation audit: menus, menu-items and sitewide header options.

Posts no edits, outputs only public labels and structural metadata. Identify
actual menu assignment before a staged navigation change.
"""
import json
import urllib.parse
from scripts.wp_publish import normalized_base,wp_request,PublishError
MAX_ITEMS=100
def endpoint(name):
    try:
        return wp_request(normalized_base(),name)
    except PublishError as exc:
        return {"unavailable":str(exc).split("(")[0].strip()}
def main():
    menus=endpoint("menus?context=edit&per_page=100")
    out={"state":"navigation_audit_read_only","site":"xfit.cz",
      "menu_api":type(menus).__name__,"menu_count":len(menus) if isinstance(menus,list) else None,
      "menus":[],"no_site_writes":True}
    if isinstance(menus,list):
        for menu in menus[:15]:
            id=menu.get("id")
            if not isinstance(id,int):continue
            rows=endpoint("menu-items?menus="+str(id)+"&context=edit&per_page=100&orderby=menu_order&order=asc")
            itemlist=[]
            if isinstance(rows,list):
                for p in rows[:MAX_ITEMS]:
                    itemlist.append({"id":p.get("id"),"title":(p.get("title") or {}).get("raw"),
                        "parent":p.get("parent"),"menu_order":p.get("menu_order"),
                        "object":p.get("object"),"object_id":p.get("object_id"),
                        "status":p.get("status"),"url_host":urllib.parse.urlsplit(p.get("url","")).hostname})
            out["menus"].append({"id":id,"name":menu.get("name"),
              "locations":menu.get("locations"),"item_count":len(itemlist),
              "items":itemlist,"item_api_unavailable":rows if not isinstance(rows,list) else None})
    # Theme information uses public theme identifier only, no credentials.
    theme=endpoint("themes?status=active&_fields=stylesheet,name,status,template")
    out["active_themes"]=theme if isinstance(theme,list) else "unavailable"
    print(json.dumps(out,ensure_ascii=False))
if __name__=="__main__":main()
