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

try:
    from scripts.xfit_status_evidence import real_release_evidence
except ModuleNotFoundError:
    from xfit_status_evidence import real_release_evidence

ISSUE=1
SLUGS=[
    ("xfit-os-protein-guide","Průvodce proteinem"),
    ("xfit-os-doplnky-pro-zacatecniky","Doplňky pro začátečníky"),
    ("xfit-os-kreatin-poradce","Výběr kreatinu"),
    ("xfit-os-syrovatkovy-protein-porovnani","Porovnání syrovátkových proteinů"),
    ("jaky-je-rozdil-mezi-klasickym-pilates-a-power-pilates","Pilates přehled")
]
EXPECTED_REPO="Rastty/xfit-growth-os"
LANES={2:"UX a poradci",3:"SEO archiv",4:"Redakční kvalita",5:"Affiliate a měření"}

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

def github_lanes(token):
    """Display coding assignment truth; a prepared issue is not an active agent."""
    results=[]
    for number,label in LANES.items():
        try:
            issue=get_json("https://api.github.com/repos/"+EXPECTED_REPO+"/issues/"+str(number),token)
            if issue.get("pull_request"):
                results.append((number,label,"issue_neplatné",""))
                continue
            assignees=[x.get("login","") for x in issue.get("assignees",[])]
            agents=[n for n in assignees if "copilot" in n.lower() or "codex" in n.lower() or "claude" in n.lower()]
            mode="AI agent přiřazen; čeká na ověření PR" if agents else "připravené zadání; žádný AI agent není přiřazen"
            results.append((number,label,mode,issue.get("html_url","")))
        except (HTTPError,URLError,TimeoutError,ValueError,KeyError):
            results.append((number,label,"stav nepodařilo se ověřit",""))
    return results

def render(runs, states, now, lanes=None, production=None):
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
    if production is not None:
        c = production["counts"]
        lines += [
            "",
            "**Skutečné publikace a změny (jen veřejně potvrzené publikační běhy):**",
            "- Nové články: **" + str(c["new"]) +
            "**; ověřené aktualizační zásahy: **" + str(c["updated"]) +
            "** na **" + str(c["unique_updated_pages"]) +
            "** různých stránkách; zápisy bez rozlišení nová/úprava: **" +
            str(c["publication_or_update"]) + "**.",
            "- Úspěšné publikační běhy bez nové změny: **" +
            str(production["verified_no_change_runs"]) + "**.",
        ]
        grouped = {}
        for event in production["verified_events"]:
            key = (event["kind"], event["url"])
            if key not in grouped:
                grouped[key] = {"event": event, "count": 0}
            grouped[key]["count"] += 1
        for item in list(grouped.values())[:10]:
            event = item["event"]
            label = ("nová publikace" if event["kind"] == "new"
                     else "ověřená aktualizace" if event["kind"] == "updated"
                     else "publikace nebo úprava")
            lines.append("- **" + label + " (" + str(item["count"]) +
                         "× v období)**: [" + event["slug"] +
                         "](" + event["url"] + ") · [nejnovější produkční doklad](" +
                         event["run_url"] + ")")
        if production["unverified_runs"]:
            lines.append("- **NEOVĚŘENO: " + str(len(production["unverified_runs"])) +
                         " publikačních běhů.** Bez jednoznačného produkčního " +
                         "dokladu nelze tvrdit, že bylo provedeno 0 změn.")
            for item in production["unverified_runs"][:5]:
                if item["run_id"] is not None:
                    run_link = "https://github.com/" + EXPECTED_REPO + "/actions/runs/" + str(item["run_id"])
                    lines.append("- [" + item["name"] + "](" + run_link + ") — " +
                                 "nelze potvrdit výsledek na WordPressu")
        elif production["publisher_runs_seen"] == 0:
            lines.append("- V tomto intervalu nebyl zaznamenán žádný " +
                         "schválený publikační běh.")
        lines.append("- Tyto počty nepokrývají ruční úpravy WordPressu " +
                     "ani prodeje/affiliate provize.")
    if failures:
        lines.append("- **Vyžaduje opravu:** "+", ".join(
            "["+x.get("name","?")+"]("+x.get("html_url","")+")" for x in failures[:5]))
    if successes:
        latest=successes[:5]
        lines.append("- Poslední úspěchy: "+", ".join(
            "["+x.get("name","?")+"]("+x.get("html_url","")+")" for x in latest))
    if lanes:
        lines += ["", "**Pracovní větve pro paralelní vývoj:**"]
        for number,label,state,url in lanes:
            lines.append("- "+("["+label+" #"+str(number)+"]("+url+")" if url else label+" #"+str(number))+" — "+state)
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
    lanes=github_lanes(token)
    production=real_release_evidence(
        runs, token,
        fetch_jobs=lambda run_id, auth: get_json(
            "https://api.github.com/repos/" + EXPECTED_REPO +
            "/actions/runs/" + str(run_id) + "/jobs?per_page=100", auth))
    body=render(runs,states,now,lanes,production)
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as f:f.write(body+"\n")
    result=get_json("https://api.github.com/repos/"+repo+"/issues/"+str(ISSUE)+"/comments",
                  token,method="POST",payload={"body":body})
    print(json.dumps({"state":"status_issued","issue":ISSUE,
          "comment_id":result.get("id"),"runs_in_period":len(runs),
          "verified_wp_changes":len(production["verified_events"]),
          "unverified_publisher_runs":len(production["unverified_runs"]),
          "no_wordpress_writes":True},ensure_ascii=False))
if __name__=="__main__":
    try:
        main()
    except Exception as ex:
        # Avoid printing authorization values.
        print("XFIT_STATUS_ERROR: "+type(ex).__name__,file=sys.stderr)
        sys.exit(2)
