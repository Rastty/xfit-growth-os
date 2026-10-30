#!/usr/bin/env python3
"""Minimum publish-quality gates for native Xfit WordPress REST releases.

This protects against demonstrably bad content; it cannot certify that an
article is 'the best in the world'. That still requires editorial judgment,
genuine sourcing, visual/accessibility QA and real user feedback.
"""
import html
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit, parse_qs

TRUSTED_EVIDENCE=("ods.od.nih.gov","pmc.ncbi.nlm.nih.gov","pubmed.ncbi.nlm.nih.gov",
                  "efsa.europa.eu","food.ec.europa.eu","knowledge-for-policy.ec.europa.eu",
                  "who.int","acsm.org")
FORBIDDEN=re.compile(r"(garantovaně\s+(vyléčí|odstraní)|100\s*%\s*(vyléčí|účinnost)|jediný\s+zázračný|klikni zde|nejlepší na světě)",re.I)
NAVIGATION_KW=("na xfit.cz","xfit.cz")
MIN_WORDS=320
MIN_SECTION_HEADERS=3
class EditorialError(ValueError):
    pass

class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headers=[];self.paragraphs=[];self.links=[];self.images=[];self.tables=0;self.product_cards=0
        self._capture=None;self._buf=[]
        self.visible=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag in ("h2","h3","p"):
            self._capture=tag;self._buf=[]
        if tag=="a":self.links.append((a.get("href",""),a.get("rel","")))
        if tag=="img":self.images.append(a)
        if tag=="table":self.tables+=1
        if tag=="article" and "xfit-product-card" in (a.get("class") or "").split():self.product_cards+=1
    def handle_data(self,data):
        self.visible.append(data)
        if self._capture:self._buf.append(data)
    def handle_endtag(self,tag):
        if tag==self._capture:
            content=" ".join(" ".join(self._buf).split())
            if tag in ("h2","h3"):self.headers.append((tag,content))
            if tag=="p":self.paragraphs.append(content)
            self._capture=None;self._buf=[]

def check_document(doc, commercial=None):
    body=doc.get("content","")
    if not isinstance(body,str):
        raise EditorialError("Missing editorial body")
    p=Inspector();p.feed(body)
    text=" ".join(p.visible)
    words=len(re.findall(r"\b[\wÀ-ž]+\b",text,re.U))
    if words<MIN_WORDS:
        raise EditorialError(f"Too short for cornerstone editorial content ({words} words)")
    if sum(k=="h2" for k,_ in p.headers)<MIN_SECTION_HEADERS:
        raise EditorialError("Missing structured H2 sections")
    norm_headers=[re.sub(r"\W+"," ",h.casefold()).strip() for _,h in p.headers]
    if len(norm_headers)!=len(set(norm_headers)):
        raise EditorialError("Exact repeated heading; likely boilerplate content")
    long_pars=[re.sub(r"\W+"," ",x.casefold()).strip() for x in p.paragraphs if len(x)>110]
    if len(long_pars)!=len(set(long_pars)):
        raise EditorialError("Duplicated long paragraphs")
    if FORBIDDEN.search(text):
        raise EditorialError("Unverifiable medical/performance marketing claim")
    if not p.links:
        raise EditorialError("Missing supporting links and relevant navigation")
    for href, rel in p.links:
        if href.startswith("#"):continue
        u=urlsplit(html.unescape(href))
        if u.scheme!="https" or not u.hostname:
            raise EditorialError("Invalid or insecure external/internal URL")
        if u.username or u.password or u.port:
            raise EditorialError("Unsafe URL credentials/port in editorial link")
        if u.hostname in ("www.namaximum.cz","namaximum.cz"):
            if "sponsored" not in rel.split():
                raise EditorialError("Affiliate outbound link lacks sponsored rel")
            q=parse_qs(u.query)
            if q.get("utm_source")==["heureka"]:
                raise EditorialError("Heureka CPC link is not an Affial link")
    for image in p.images:
        if not (image.get("alt") or "").strip():
            raise EditorialError("Product/editorial image missing alt text")
        if image.get("loading")!="lazy":
            raise EditorialError("Non-decorative image must lazy-load")
    evidence_hosts=set()
    for href,_ in p.links:
        host=urlsplit(href).hostname
        if host in TRUSTED_EVIDENCE:evidence_hosts.add(host)
    if len(evidence_hosts)<1:
        raise EditorialError("No recognizable independent scientific/public-health source")
    is_commercial=any(urlsplit(x[0]).hostname in ("namaximum.cz","www.namaximum.cz") for x in p.links)
    if commercial is True and not is_commercial:
        raise EditorialError("Commercial article has no tracked real merchant links")
    if is_commercial and "provizi" not in text.casefold() and "affiliate" not in text.casefold():
        raise EditorialError("Commercial content lacks plain-language affiliate disclosure")
    if is_commercial and p.tables==0 and p.product_cards<2:
        raise EditorialError("Comparison lacks tabular results or multiple accessible product cards")
    return {
        "passed":True,"word_count":words,"h2_count":sum(k=="h2" for k,_ in p.headers),
        "source_hosts":sorted(evidence_hosts),"image_count":len(p.images),
        "commerce":is_commercial,"product_cards":p.product_cards
    }
