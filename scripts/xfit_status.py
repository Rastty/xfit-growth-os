#!/usr/bin/env python3
"""Evidence-only four-hour Xfit status. Writes one GitHub issue comment.

Cannot substitute for an autonomous developer. Does not touch WP content.
Only uses the repository's ephemeral GitHub Actions token.
"""
from datetime import datetime, timedelta, timezone
import json
import os
import sys
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ISSUE=1
SLUGS=[
    ("xfit-os-protein-guide","Průvodce proteinem"),
    ("xfit-os-kreatin-poradce","Výběr kreatinu"),
    ("xfit-os-syrovatkovy-protein-porovnani","Porovnání syrovátkových proteinů"),
    ("jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates","Pilates přehled")
]
EXPECTED_REPO="Rastty/xfit-growth-os"

def get_json(url, token=None, method="GET", payload=None):
    data=json.dumps(payload).encode() if payload is not None else None
    headers={"Accept":"application/vnd.github+json" if token else "application/json",
             "User-Agent":"XfitGrowthOS-Status/1.0"}
    if token:
        headers["Authorization"]="Bearer "+token
        headers["X-GitHub-Api-Version"]="2022-11-28"
    if data:
        headers["Content-Type"]="application/json"
    request=Request(url,data=data,headers=headers,method=method)
    with urlopen(request,timeout=25) as response:
        return json.load(response)

def wordpress_state():
    rows=[]
    for slug,label in SLUGS:
        try:
            url="https://xfit.cz/wp-json/wp/v2/posts?"+urlencode({"slug":slug,"per_page":1,"_fields":"id,slug,status,link,title"})
            posts=get_json(url)
            matching=[p for p in posts if p.get("slug")==slug and p.get("status")=="publish"]
            if matching:
                p=matching[0]
                link=p.get("link","")
                if link.startswith("https://xfit.cz/"):
                    rows.append((label,"publikováno ve WP REST",link))
                else:
                    rows.append((label,"NEOVĚŘENO – permalink", ""))
            else:
                rows.append((label,"NEOVĚŘENO – nelze nalézt publikovaný článek", ""))
        except (HTTPError,URLError,TimeoutError,ValueError):
            rows.append((label,"NEOVĚŘENO – WP REST nedostupné",""))
    return rows

def github_activity(token, since):
    runs=get_json("https://api.github.com/repos/"+EXPECTED_REPO+"/actions/runs?per_page=100",token)
    items=[]
    for r in runs.get("workflow_runs",[]):
        stamp=r.get("created_at","")
        try:
            dt=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        except ValueError:
            continue
        if dt>=since and r.get("name")!="XFIT Four-hour Status":
            items.append(r)
    return items

def render(runs, states, now):
    successes=[x for x in runs if x.get("conclusion")=="success"]
    failures=[x for x in runs if x.get("conclusion") in ("failure","timed_out","cancelled")]
    ongoing=[x for x in runs if x.get("status")!="completed"]
    lines=[
        "### Xfit.cz — čtyřhodinový status",
        "",
        "Kontrola: **"+now.strftime("%d. %m. %Y %H:%M UTC")+"**. Zdroj: GitHub Actions a veřejné WordPress REST API.",
        "",
        "**Co ověřeně existuje na webu:**"
    ]
    for label,state,url in states:
        lines.append("- "+("["+label+"]("+url+")" if url else label)+" — "+state)
    lines += [
        "",
        "**Běhy GitHub Actions v posledních 4 hodinách:**",
        "- Úspěšné: **"+str(len(successes))+"**, neúspěšné/zrušené: **"+str(len(failures))+"**, stále běží: **"+str(len(ongoing))+"**."
    ]
    if failures:
        lines.append("- **Vyžaduje opravu:** "+", ".join(
            "["+x.get("name","?")+"]("+x.get("html_url","")+")" for x in failures[:5]))
    if successes:
        latest=successes[:5]
        lines.append("- Poslední úspěchy: "+", ".join(
            "["+x.get("name","?")+"]("+x.get("html_url","")+")" for x in latest))
    lines += [
        "",
        "**Hranice důkazů:** Publikovaný stav ve WP REST je jiný než test vzhledu, připsaná affiliate objednávka nebo skutečný příjem. Bez přístupu k Affial a GA4 konverzím zde žádný prodej netvrdíme.",
        "",
        "**Další prioritní krok:** Zlepšovat opravdu užitečné výběrové průvodce a top existující landing pages; čisticí zásahy do archivu jen po záloze, ověřené kanibalizaci a kontrole URL/traffic. Každá změna musí projít testy a veřejným ověřením.",
        "",
        "_Automatický report z GitHub Actions. Kód mimo plánované Actions nemá samostatného AI vývojáře._"
    ]
    return "\n".join(lines)

def main():
    repo=os.environ.get("GITHUB_REPOSITORY","")
    token=os.environ.get("GH_TOKEN","")
    if repo!=EXPECTED_REPO or not token:
        raise RuntimeError("Unexpected GitHub repo or missing Actions token")
    now=datetime.now(timezone.utc)
    runs=github_activity(token, now-timedelta(hours=4))
    states=wordpress_state()
    body=render(runs,states,now)
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as f:f.write(body+"\n")
    result=get_json("https://api.github.com/repos/"+repo+"/issues/"+str(ISSUE)+"/comments",
                  token,method="POST",payload={"body":body})
    print(json.dumps({"state":"status_issued","issue":ISSUE,
          "comment_id":result.get("id"),"runs_in_period":len(runs),
          "no_wordpress_writes":True},ensure_ascii=False))
if __name__=="__main__":
    try:
        main()
    except Exception as ex:
        # Avoid printing authorization values.
        print("XFIT_STATUS_ERROR: "+type(ex).__name__,file=sys.stderr)
        sys.exit(2)
