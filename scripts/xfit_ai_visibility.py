"""Human + AI search readiness, read-only. No 'AI SEO' magic files needed."""
import json
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser
from datetime import datetime, timezone
from urllib.parse import urlsplit
BASE="https://xfit.cz"
PAGES=[
 "/xfit-os-doplnky-pro-zacatecniky/",
 "/xfit-os-kreatin-poradce/",
 "/xfit-os-syrovatkovy-protein-porovnani/",
 "/xfit-os-protein-guide/"
]
class Reader(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True)
  self.h1=[];self.h2=[];self.description=[];self.canonical=[];self.robots=[];self.links=[];self.images=[];self.jsonld=0;self.title=False
  self.capture=None;self.acc=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in ("h1","h2","title"):self.capture=tag;self.acc=[]
  if tag=="meta":
   if a.get("name","").lower()=="description":self.description.append(a.get("content",""))
   if a.get("name","").lower()=="robots":self.robots.append(a.get("content",""))
  if tag=="link" and a.get("rel")=="canonical":self.canonical.append(a.get("href",""))
  if tag=="a":self.links.append(a.get("href",""))
  if tag=="img":self.images.append(a)
  if tag=="script" and a.get("type","").lower()=="application/ld+json":self.jsonld+=1
 def handle_data(self,data):
  if self.capture:self.acc.append(data)
 def handle_endtag(self,tag):
  if tag==self.capture:
   value=" ".join(" ".join(self.acc).split())
   if tag=="h1":self.h1.append(value)
   if tag=="h2":self.h2.append(value)
   if tag=="title":self.title=bool(value)
   self.capture=None;self.acc=[]
def inspect(body,path):
 r=Reader();r.feed(body)
 flags=[]
 if not r.title:flags.append("missing_title")
 if len(r.h1)!=1:flags.append("h1_count_not_one")
 if len(r.h2)<3:flags.append("thin_structure")
 if not r.description or not r.description[0]:flags.append("missing_meta_description")
 if not r.canonical:flags.append("missing_canonical")
 elif urlsplit(r.canonical[0]).hostname not in ("xfit.cz","www.xfit.cz") or urlsplit(r.canonical[0]).path.rstrip("/")!=path.rstrip("/"):
  flags.append("canonical_mismatch")
 if "noindex" in " ".join(r.robots).lower():flags.append("noindex")
 if len(r.links)<5:flags.append("few_internal_navigation_opportunities")
 if any(x.get("alt") is None for x in r.images):flags.append("images_missing_alt")
 if r.jsonld==0:flags.append("jsonld_absent_optional")
 return {"flags":flags,"h1":r.h1[:2],"h2_count":len(r.h2),"canonical":r.canonical[:1],
  "jsonld_blocks":r.jsonld,"link_count":len(r.links),"image_count":len(r.images)}
def fetch(path):
 req=Request(BASE+path,headers={"User-Agent":"XfitGrowthOS-VisibilityAudit/1.0"})
 with urlopen(req,timeout=30) as resp:
  return resp.status,resp.read(2500000).decode("utf-8","replace"),resp.url
def main():
 report={"checked_at":datetime.now(timezone.utc).isoformat(),"mode":"read_only","pages":{}}
 for path in PAGES:
  try:
   status,body,url=fetch(path)
   report["pages"][path]={"status":status,"actual_url":url,**inspect(body,path)}
  except (OSError,ValueError,HTTPError,URLError) as exc:
   report["pages"][path]={"state":"unavailable","error_type":type(exc).__name__}
 for path in ("/robots.txt","/wp-sitemap.xml","/sitemap_index.xml"):
  try:
   status,body,url=fetch(path)
   report["pages"][path]={"status":status,"body_preview":body[:300] if path=="/robots.txt" else "xml-or-redirect"}
  except (OSError,ValueError,HTTPError,URLError) as exc:
   report["pages"][path]={"state":"unavailable","error_type":type(exc).__name__}
 Path("reports").mkdir(exist_ok=True)
 Path("reports/xfit-ai-visibility.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"state":"AI_VISIBILITY_AUDIT","ok":sum(x.get("status")==200 for x in report["pages"].values()),"pages":{k:v.get("flags",[]) for k,v in report["pages"].items()},"remote_writes":0},ensure_ascii=False))
if __name__=="__main__":main()
