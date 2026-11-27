#!/usr/bin/env python3
"""Evidence-only four-hour Xfit status. Writes one GitHub issue comment.

Cannot substitute for an autonomous developer. Does not touch WP content.
Only uses the repository's ephemeral GitHub Actions token.
"""
from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from scripts.xfit_home_sticky_guide_onepost import HeadlineCards
    from scripts.xfit_supplements_category_hub_onepost import CategoryH1, CAT_NAME, CAT_URL
except ModuleNotFoundError:
    from xfit_home_sticky_guide_onepost import HeadlineCards
    from xfit_supplements_category_hub_onepost import CategoryH1, CAT_NAME, CAT_URL

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
    ("xfit-os-rostlinne-proteiny-porovnani","Porovnání rostlinných proteinů"),
    ("xfit-os-vybaveni-na-domaci-cviceni-nabidky","Domácí fitness vybavení"),
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

HOMEPAGE_GUIDE_SLUGS = (
    "xfit-os-doplnky-pro-zacatecniky",
    "xfit-os-syrovatkovy-protein-porovnani",
    "xfit-os-kreatin-poradce",
)


def homepage_buyer_placement(*, reader=None):
    """One ordinary public homepage GET, no cache bypass or WordPress writes.

    Source: actual reader-visible headline-card anchors, not WP sticky flags,
    metadata or successful release workflow. A stale CDN response is a
    separate observation, not proof that the origin sticky settings reverted.
    """
    result = {
        "state": "PUBLIC_HOME_READ_UNKNOWN",
        "scope": "ORDINARY_PUBLIC_HTML_NO_CACHE_BYPASS",
        "reader_first_rank": None, "whey_rank": None,
        "creatine_rank": None, "wordpress_writes": 0,
    }
    try:
        if reader is None:
            req = Request("https://xfit.cz/", headers={
                "User-Agent": "XFITFourHourHomePositionReadonly/1.0",
                "Accept": "text/html",
            }, method="GET")
            with urlopen(req, timeout=20) as response:
                final = urlsplit(response.geturl())
                if (response.status != 200 or final.scheme != "https"
                        or final.hostname not in ("xfit.cz", "www.xfit.cz")
                        or final.path not in ("/", "") or final.query
                        or final.fragment or final.username
                        or final.password or final.port is not None):
                    return result
                blob = response.read(2_000_001)
                if len(blob) > 2_000_000:
                    return result
                body = blob.decode("utf-8", errors="replace")
        else:
            body = reader()
        if not isinstance(body, str) or not 250 <= len(body) <= 2_000_000:
            return result
        parser = HeadlineCards()
        parser.feed(body)
        paths = list(dict.fromkeys(parser.hrefs))
        if not 8 <= len(paths) <= 200:
            return result
        ranks = [paths.index("/" + slug + "/") + 1
                 if "/" + slug + "/" in paths else None
                 for slug in HOMEPAGE_GUIDE_SLUGS]
        result.update({
            "reader_first_rank": ranks[0], "whey_rank": ranks[1],
            "creatine_rank": ranks[2],
            "state": ("ORDINARY_PUBLIC_HOME_TOP3_VERIFIED"
                      if ranks == [1, 2, 3]
                      else "PUBLIC_HOME_ORDER_DIFFERS_OR_CACHE_STALE"),
        })
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
        pass
    return result



def supplement_category_buyer_placement(*, reader=None):
    """One ordinary public category GET; no cache bypass, auth or WP writes.

    The previously verified edit-context category memberships are not
    inferred from this one cache observation. A stale CDN copy must be
    reported as a separate state, not a rollback or a request to POST again.
    """
    result = {
        "state":"PUBLIC_SUPPLEMENT_CATEGORY_READ_UNKNOWN",
        "scope":"ORDINARY_PUBLIC_HTML_NO_CACHE_BYPASS",
        "guide_rank":None, "whey_rank":None, "creatine_rank":None,
        "wordpress_writes":0,
    }
    try:
        if reader is None:
            request=Request(CAT_URL, headers={
                "User-Agent":"XFITFourHourSupplementCategoryReadonly/1.0",
                "Accept":"text/html",
            }, method="GET")
            with urlopen(request, timeout=20) as response:
                target=urlsplit(response.geturl())
                expected=urlsplit(CAT_URL)
                if (response.status != 200 or target.scheme != "https"
                        or target.hostname not in ("xfit.cz","www.xfit.cz")
                        or target.path != expected.path or target.query
                        or target.fragment or target.username or target.password
                        or target.port is not None):
                    return result
                data=response.read(2_000_001)
                if len(data)>2_000_000:
                    return result
                body=data.decode("utf-8",errors="replace")
        else:
            body=reader()
        if not isinstance(body,str) or not 400<=len(body)<=2_000_000:
            return result
        heading=CategoryH1()
        heading.feed(body)
        if heading.h1 != [CAT_NAME]:
            return result
        cards=HeadlineCards()
        cards.feed(body)
        links=list(dict.fromkeys(cards.hrefs))
        if not 8<=len(links)<=250:
            return result
        ranks=[
            links.index("/"+slug+"/")+1 if "/"+slug+"/" in links else None
            for slug in HOMEPAGE_GUIDE_SLUGS
        ]
        result.update({
            "guide_rank":ranks[0], "whey_rank":ranks[1],
            "creatine_rank":ranks[2],
            "state":("ORDINARY_PUBLIC_SUPPLEMENT_TOP3_VERIFIED"
                     if ranks==[1,2,3]
                     else "PUBLIC_SUPPLEMENT_CATEGORY_ORDER_DIFFERS_OR_CACHE_STALE")
        })
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError):
        pass
    return result


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

LANE_PREFIX={2:"ux",3:"archive",4:"editor",5:"revenue"}
CODEX_BRANCH=re.compile(r"xfit/codex-(ux|archive|editor|revenue)-[0-9]+-[0-9]+\Z")


def github_open_agent_prs(token):
    """Only verified, in-repository, currently OPEN Codex proposals.

    Missing PR permissions or an incomplete 100-row listing must be shown
    as UNKNOWN, never interpreted as no active Codex proposal.
    """
    try:
        pulls=get_json("https://api.github.com/repos/"+EXPECTED_REPO+
                       "/pulls?state=open&per_page=100",token)
        if not isinstance(pulls,list) or len(pulls)>=100:
            return None
        by_lane={lane:[] for lane in LANE_PREFIX.values()}
        for p in pulls:
            if not isinstance(p,dict) or p.get("state")!="open":
                continue
            head=p.get("head") or {}
            branch=head.get("ref") or ""
            repo=(head.get("repo") or {}).get("full_name")
            m=CODEX_BRANCH.fullmatch(branch)
            number=p.get("number")
            if not m or repo!=EXPECTED_REPO or type(number) is not int or number<1:
                continue
            by_lane[m.group(1)].append(number)
        return {lane:sorted(set(numbers),reverse=True)
                for lane,numbers in by_lane.items()}
    except (HTTPError,URLError,TimeoutError,ValueError,KeyError,TypeError):
        return None


def github_lanes(token):
    """Report actual reviewable Codex PRs, NOT issue assignee guesses."""
    open_prs=github_open_agent_prs(token)
    results=[]
    for number,label in LANES.items():
        try:
            issue=get_json("https://api.github.com/repos/"+EXPECTED_REPO+
                           "/issues/"+str(number),token)
            if issue.get("pull_request"):
                results.append((number,label,"issue_neplatné",""))
                continue
            if open_prs is None:
                mode="NEOVĚŘENO – seznam agentních PR nelze načíst"
            else:
                prs=open_prs.get(LANE_PREFIX[number],[])
                if prs:
                    links=[
                        "[PR #"+str(n)+"](https://github.com/"+EXPECTED_REPO+
                        "/pull/"+str(n)+")" for n in prs[:3]
                    ]
                    mode=", ".join(links)+" — otevřený návrh k revizi, ještě nepublikováno"
                    if len(prs)>3:
                        mode+=" (a další "+str(len(prs)-3)+" PR)"
                else:
                    mode="bez otevřeného Codex PR; případnou práci ověřují jen Actions běhy"
            results.append((number,label,mode,issue.get("html_url","")))
        except (HTTPError,URLError,TimeoutError,ValueError,KeyError,TypeError):
            results.append((number,label,"stav issue nepodařilo se ověřit",""))
    return results

def render(runs, states, now, lanes=None, production=None, homepage=None, supplement_category=None):
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
    if homepage is not None:
        def rank_text(value):
            return "#" + str(value) if type(value) is int and value > 0 else "NEOVĚŘENO"
        lines += [
            "",
            "**Běžná veřejná homepage (jeden GET bez obejití cache):**",
            "- Stav: **" + homepage["state"] + "**; průvodce bez nákupu " +
            rank_text(homepage["reader_first_rank"]) + ", syrovátkový poradce " +
            rank_text(homepage["whey_rank"]) + ", kreatinový poradce " +
            rank_text(homepage["creatine_rank"]) + ".",
            "- Jedno veřejné načtení neprokazuje globální cache ani nárůst kliknutí; případná odchylka neznamená, že WordPress sticky příznak byl vrácen.",
        ]
    if supplement_category is not None:
        def category_rank_text(value):
            return "#"+str(value) if type(value) is int and value>0 else "NEOVĚŘENO"
        lines += [
            "",
            "**Běžný veřejný archiv Doplňky stravy (jeden GET bez obejití cache):**",
            "- Stav: **"+supplement_category["state"]+"**; nezávislý průvodce "+
            category_rank_text(supplement_category["guide_rank"])+", syrovátkový poradce "+
            category_rank_text(supplement_category["whey_rank"])+", kreatinový poradce "+
            category_rank_text(supplement_category["creatine_rank"])+".",
            "- Odlišná odpověď v jedné CDN cache není důkaz, že byly WordPress kategorie vráceny; žádné automatické opakované zápisy.",
        ]
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
        elif production["publisher_runs_seen"] == 0 and not production.get("coupon_cleanup", {}).get("runs_seen"):
            lines.append("- V tomto intervalu nebyl zaznamenán žádný " +
                         "schválený publikační běh.")
        lines.append("- Tyto počty nezahrnují samostatnou evidenci kuponových dávek, "
                     "ruční úpravy WordPressu ani prodeje/affiliate provize.")
        recovery = production.get("mat_recovery", {})
        if recovery.get("runs_seen"):
            lines.append("")
            lines.append("**Samostatně: dodatečné ověření dřívější úpravy podložek (bez nového zápisu):**")
            if recovery.get("verified_post_ids"):
                ids = ", ".join(str(pid) for pid in recovery["verified_post_ids"])
                base = "https://github.com/" + EXPECTED_REPO + "/actions/runs/"
                lines.append("- WP ID " + ids + ": zachovaná metadata, přesný živý obsah a mobil 375 px ověřeny; "
                             "[původní neúspěšný release](" + base + str(recovery["original_run_id"]) +
                             "), [nezávislý úspěšný GET-only důkaz](" + base + str(recovery["proof_run_id"]) +
                             "). 0 nových zápisů; nepřičítat k aktuálním změnám.")
            if recovery.get("unknown_run_ids"):
                lines.append("- NEOVĚŘENO: " + str(len(recovery["unknown_run_ids"])) +
                             " běhů dodatečné kontroly; výsledek nepředpokládat.")
        coupon = production.get("coupon_cleanup", {})
        if coupon.get("runs_seen"):
            lines += [
                "",
                "**Samostatně: ověřené opravy starých kuponů (včetně částečných dávek):**",
                "- Veřejně ověřené opravy: **" + str(coupon["public_verified_update_events"]) +
                "** na **" + str(coupon["public_verified_unique_posts"]) +
                "** různých WP ID; doložené odstraněné shortcode bloky: **" +
                str(coupon["known_public_verified_shortcodes"]) + "**" +
                (" (neúplný počet; další výsledek NEOVĚŘENO)." if
                 coupon["shortcode_count_incomplete"] else "."),
                "- Jde o úpravy existujících článků, nikoli nové články; "
                "tyto počty nelze prostě přičíst k unikátním stránkám výše.",
            ]
            for wave in coupon["waves"][:8]:
                ids = ", ".join(str(pid) for pid in wave["public_verified_post_ids"]) or "žádné"
                link = "https://github.com/" + EXPECTED_REPO + "/actions/runs/" + str(wave["run_id"])
                lines.append(
                    "- [Dávka " + str(wave["run_id"]) + "](" + link + "): **" +
                    str(len(wave["public_verified_post_ids"])) + "/" + str(wave["attempted"]) +
                    "** veřejně ověřeno; WP ID " + ids +
                    "; nezměněné " + str(len(wave["unchanged_post_ids"])) +
                    ", nejisté zápisy " + str(len(wave["uncertain_post_ids"])) +
                    ", veřejně neověřené " + str(len(wave["public_unverified_post_ids"])) + "."
                )
            if coupon["unknown_run_ids"]:
                lines.append("- **NEOVĚŘENO: " + str(len(coupon["unknown_run_ids"])) +
                             " kuponových běhů** — chybí kompletní důkaz; nelze je vykázat jako nulu.")
            lines.append("- Pokusy s nejasným nebo nezměněným výsledkem neopakovat automaticky.")
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
    homepage=homepage_buyer_placement()
    supplement_category=supplement_category_buyer_placement()
    body=render(runs,states,now,lanes,production,homepage=homepage,
                supplement_category=supplement_category)
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as f:f.write(body+"\n")
    result=get_json("https://api.github.com/repos/"+repo+"/issues/"+str(ISSUE)+"/comments",
                  token,method="POST",payload={"body":body})
    print(json.dumps({"state":"status_issued","issue":ISSUE,
          "comment_id":result.get("id"),"runs_in_period":len(runs),
          "verified_wp_changes":len(production["verified_events"]),
          "unverified_publisher_runs":len(production["unverified_runs"]),
          "no_wordpress_writes":True,
          "homepage_observation":homepage["state"],
          "supplement_category_observation":supplement_category["state"]},ensure_ascii=False))
if __name__=="__main__":
    try:
        main()
    except Exception as ex:
        # Avoid printing authorization values.
        print("XFIT_STATUS_ERROR: "+type(ex).__name__,file=sys.stderr)
        sys.exit(2)
