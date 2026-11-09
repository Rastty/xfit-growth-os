#!/usr/bin/env python3
"""Find credible existing Xfit posts that should link to relevant decision tools.

Read-only. Candidate ranking is editorial heuristic, not traffic attribution.
Use this result only to select and review a bounded backup-first linking wave.
"""
import json,re
from html.parser import HTMLParser
from urllib.parse import urlencode,urlsplit
from scripts.wp_publish import normalized_base,wp_request,PublishError,plain
CAMPAIGNS={
  "kreatin":"https://xfit.cz/xfit-os-kreatin-poradce/",
  "protein":"https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
}
ALREADY={"xfit-os-doplnky-pro-zacatecniky","xfit-os-kreatin-poradce",
         "xfit-os-protein-guide","xfit-os-syrovatkovy-protein-porovnani",
         "xfit-os-kreatin-nebo-protein","kreatin-a-jeho-vliv-na-ledviny-a-jatra"}
def clean(text):return " ".join(plain(text or "").split())

# Owner-provided historical GSC/GA4 review: public slugs only, no private metrics.
# These are editorial review candidates, not permission for automatic WP writes.
PRIORITY_LEGACY=(
    ("nejlepsi-zpusoby-jak-kombinovat-kreatin-s-dalsimi-doplnky-stravy-a-treninkovymi-metodami-pro-uspech-v-fitness",
     "https://xfit.cz/xfit-os-kreatin-poradce/", "creatine-training-decision"),
    ("kreatin-monohydrat-a-jeho-bezpecnostni-rizika-pri-uzivani-jak-se-chranit-pred-nezadoucimi-ucinky",
     "https://xfit.cz/kreatin-a-jeho-vliv-na-ledviny-a-jatra/", "safety-evidence-handoff"),
)


class Anchors(HTMLParser):
    """Count real href destinations, not unlinked URL text or JS attributes."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls=set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.urls.update(value for key,value in attrs
                             if key == "href" and isinstance(value,str))


def links(body):
    parser=Anchors()
    parser.feed(body)
    return parser.urls


def verified_post_identity(post,slug):
    if not isinstance(post,dict) or post.get("status")!="publish":
        return False
    if post.get("slug")!=slug or not isinstance(post.get("id"),int):
        return False
    link=post.get("link") or ""
    try:
        u=urlsplit(link)
    except ValueError:
        return False
    return (u.scheme=="https" and u.netloc=="xfit.cz"
            and not u.query and not u.fragment
            and u.path=="/"+slug+"/")


def inspect_priority(*,request=None,base=None):
    """Exactly two bounded WP GETs. Return no article body, secrets or traffic."""
    request=request or wp_request
    out=[]
    for slug,target,intent in PRIORITY_LEGACY:
        item={"slug":slug,"intent":intent,
              "target":target,"state":"UNKNOWN_NO_VERIFIED_SOURCE",
              "target_already_linked":None,"next_action":"RECHECK_SOURCE"}
        try:
            rows=request(normalized_base() if base is None else base,"posts?"+urlencode({
                "slug":slug,"status":"publish","context":"edit","per_page":2,
                "_fields":"id,slug,status,link,title,content,modified"}))
            matches=[p for p in rows if verified_post_identity(p,slug)]
            if len(matches)==1:
                post=matches[0]
                source=(post.get("content") or {}).get("raw")
                if isinstance(source,str) and len(source)>400:
                    already=target in links(source)
                    item.update({"state":"SOURCE_VERIFIED",
                                 "wp_post_id":post["id"],
                                 "target_already_linked":already,
                                 "next_action":("ALREADY_LINKED" if already else
                                                "EDITORIAL_REVIEW_BEFORE_ONE_POST")})
        except (PublishError,OSError,ValueError,TypeError,KeyError,AttributeError):
            # Public diagnostics may not reveal credentials or response bodies.
            pass
        out.append(item)
    return out


SEARCH_LIMIT=100
MAX_SEARCH_PAGES=8  # 800 posts per keyword; cap is a hard stop, not complete discovery.
TOPIC_TERMS={
    "kreatin":("kreatin","creatine"),
    "protein":("protein","bílkovin","bilkovin"),
}
# REST title search is term-based: searching only "protein" misses articles
# whose genuine title says "bílkoviny". Each term has separate bounded
# pagination; deduplicate by canonical WP post ID before editorial ranking.
SEARCH_TERMS={
    "kreatin":("kreatin","creatine"),
    "protein":("protein","bílkovin","bilkovin"),
}
# Safety/medical-intent posts should lead to independent explanations,
# never automatically to a commercial offer comparison.
MEDICAL_INTENT_TERMS=(
    "rizik","bezpečnost","bezpecnost","vedlejší","vedlejsi",
    "nežádouc","nezadouc","ledvin","játr","jatr","kreatinin",
    "kontraindikac","onemocn","poškoz","poskoz","těhot","tehot",
    "krev","diagnost","alerg","léky","leky",
)
CANDIDATE_DISPLAY_LIMIT=55
MIN_SLOTS_PER_TOPIC=25

def rank_search_results(rows_by_topic, *, coverage=None):
    """Pure read-only ranking; unverified or incomplete source is never called complete.

    Each (post, topic) pair is an editorial idea, NOT permission to write WP.
    With explicit page metadata, completeness is determined by completed
    pagination, not by combined result length. Without metadata (unit tests),
    a full page is conservatively UNKNOWN coverage.
    """
    candidates=[]
    saturated=[]
    incomplete=[]
    audited_posts={}
    medical_excluded={topic:0 for topic in CAMPAIGNS}
    for topic,target in CAMPAIGNS.items():
        rows=rows_by_topic[topic]
        if coverage is not None:
            state=coverage[topic]["status"]
            if state=="PAGE_CAP_REACHED":
                saturated.append(topic)
            if state!="COMPLETE":
                incomplete.append(topic)
        elif len(rows)>=SEARCH_LIMIT:
            saturated.append(topic)
            incomplete.append(topic)
        audited_posts[topic]=len(rows)
        seen=set()
        for p in rows:
            slug=p.get("slug") or ""
            post_id=p.get("id")
            if (post_id in seen or slug in ALREADY
                    or slug.startswith("xfit-os-")
                    or not verified_post_identity(p,slug)):
                continue
            seen.add(post_id)
            body=(p.get("content") or {}).get("raw") or ""
            title=clean((p.get("title") or {}).get("raw",""))
            title_and_slug=(title+" "+slug).casefold()
            if (len(body)<1500
                    or not any(term in title_and_slug
                               for term in TOPIC_TERMS[topic])):
                continue
            if any(term in title_and_slug for term in MEDICAL_INTENT_TERMS):
                medical_excluded[topic]+=1
                continue
            actual_links=links(body)
            missing=target not in actual_links
            score=(3 if any(term in title_and_slug for term in (
                "jak vybrat","jaký","jakou","koupit","účinky","účinnost",
                "dávkování","zkušenosti")) else 0)
            score+=2  # Relevant topic is proven in canonical title/slug.
            score+=1 if missing else 0
            candidates.append({
                "id":post_id,"slug":slug,"title":title[:125],
                "topic":topic,"body_chars":len(body),
                "already_has_target_link":not missing,
                "already_has_any_product_guide_link":any(
                    u in actual_links for u in CAMPAIGNS.values()),
                "ranking_heuristic":score,"link":p.get("link"),
                "next_action":("ALREADY_LINKED" if not missing else
                               "EDITORIAL_REVIEW_BEFORE_ONE_POST"),
            })
    candidates.sort(key=lambda x:(-x["ranking_heuristic"],
                                  -x["body_chars"],x["slug"],x["topic"]))
    # The first topic often has longer generated articles. Global truncation
    # would hide all protein ideas regardless of actual user demand. Preserve
    # separate reader-intent lanes, then fill remaining slots fairly.
    selected=[]
    chosen=set()
    for topic in CAMPAIGNS:
        for item in (x for x in candidates if x["topic"]==topic):
            if sum(x["topic"]==topic for x in selected)>=MIN_SLOTS_PER_TOPIC:
                break
            key=(item["id"],item["topic"])
            selected.append(item)
            chosen.add(key)
    for item in candidates:
        if len(selected)>=CANDIDATE_DISPLAY_LIMIT:
            break
        key=(item["id"],item["topic"])
        if key not in chosen:
            selected.append(item)
            chosen.add(key)
    selected.sort(key=lambda x:(-x["ranking_heuristic"],
                                -x["body_chars"],x["slug"],x["topic"]))
    return {"candidates":selected,
            "candidate_count_before_limit":len(candidates),
            "medical_intent_excluded":medical_excluded,
            "searched_post_rows":audited_posts,
            "search_results_saturated_topics":saturated,
            "search_topics_incomplete":incomplete,
            "search_coverage_complete":not bool(incomplete)}


def fetch_topic_posts(topic, *, request=None, base=None,
                      page_size=SEARCH_LIMIT, max_pages=MAX_SEARCH_PAGES,
                      search_term=None):
    """Bounded, read-only, complete-until-proven-otherwise WP search paging.

    No WP mutation, no retries of POST. Never print raw WP response/content.
    A partial result on failure/cap is not assumed to be complete.
    """
    if search_term is None:
        search_term=topic  # Preserve callers of the original single-term scan.
    if (topic not in CAMPAIGNS or search_term not in SEARCH_TERMS[topic]
            or type(page_size) is not int
            or not 1<=page_size<=100 or type(max_pages) is not int
            or not 1<=max_pages<=MAX_SEARCH_PAGES):
        raise ValueError("Invalid bounded source scan parameters")
    request=request or wp_request
    rows=[]
    seen=set()
    status="PAGE_CAP_REACHED"
    pages=0
    for page in range(1,max_pages+1):
        # WP REST Posts Controller (WordPress 6.2+) can restrict search to
        # post_title. Default search includes post_content and silently
        # buries high-intent titles behind hundreds of incidental mentions.
        q=urlencode({"search":search_term,"context":"edit","status":"publish",
                     "search_columns[]":"post_title",
                     "page":page,"per_page":page_size,
                     "_fields":"id,slug,status,title,content,modified,link"})
        try:
            response=request(normalized_base() if base is None else base,
                             "posts?"+q)
            if not isinstance(response,list) or len(response)>page_size:
                status="INVALID_RESPONSE"
                break
            # Partial or empty page ends a complete search. The next page
            # beyond a full response is still needed to PROVE termination.
            for item in response:
                if not isinstance(item,dict):
                    raise ValueError("Invalid source row")
                ident=item.get("id")
                if type(ident) is not int or ident<=0:
                    raise ValueError("Invalid source identity")
                if ident not in seen:
                    rows.append(item)
                    seen.add(ident)
            pages+=1
            if len(response)<page_size:
                status="COMPLETE"
                break
        except (PublishError,OSError,ValueError,TypeError,KeyError,
                AttributeError):
            status="READ_ERROR"
            break
    return rows,{"status":status,"pages_fetched":pages,
                 "unique_rows":len(rows)}


def fetch_campaign_posts(topic, *, request=None, base=None,
                         page_size=SEARCH_LIMIT, max_pages=MAX_SEARCH_PAGES):
    """Read all approved title synonyms, deduplicate, and retain every cap/error.

    A failed synonym scan never turns the combined inventory into COMPLETE.
    No WP write is available on this discovery path.
    """
    if topic not in CAMPAIGNS:
        raise ValueError("Unsupported campaign")
    merged=[]
    seen=set()
    query_coverage={}
    for term in SEARCH_TERMS[topic]:
        rows,info=fetch_topic_posts(
            topic,request=request,base=base,page_size=page_size,
            max_pages=max_pages,search_term=term)
        query_coverage[term]=info
        for row in rows:
            if row["id"] not in seen:
                merged.append(row)
                seen.add(row["id"])
    statuses=[item["status"] for item in query_coverage.values()]
    status=("PAGE_CAP_REACHED" if "PAGE_CAP_REACHED" in statuses
            else next((item for item in statuses if item!="COMPLETE"),"COMPLETE"))
    return merged,{
        "status":status,"unique_rows":len(merged),
        "per_title_query":query_coverage,
    }


def main():
    rows_by_topic={}
    coverage={}
    for topic in CAMPAIGNS:
        rows_by_topic[topic],coverage[topic]=fetch_campaign_posts(topic)
    ranked=rank_search_results(rows_by_topic,coverage=coverage)
    result={"state":"internal_link_opportunities_read_only",
            "audited_queries":list(CAMPAIGNS),
            "priority_legacy_link_checks":inspect_priority(),
            "topic_pagination":coverage,
            "remote_writes":0,**ranked}
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    main()
