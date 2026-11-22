/* Independent mobile Chrome proof for exact original WP #8713 after source-CAS release. */
const {chromium} = require("playwright");
const fs = require("fs");
const {navigatePublicGet} = require("../scripts/xfit_mobile_navigation.cjs");
const URL = process.env.XFIT_CANONICAL_8713_URL || "";
if (!/^https:\/\/xfit\.cz\/[a-z0-9]+(?:-[a-z0-9]+)*\/$/.test(URL)) {
 console.error("MISSING_PINNED_8713_URL");
 process.exit(2);
}
(async()=>{
 fs.mkdirSync("reports/browser-qa",{recursive:true});
 const browser=await chromium.launch({headless:true});
 const results=[];
 try{
  for(const width of [320,375,768]){
   const ctx=await browser.newContext({
     viewport:{width,height:812},deviceScaleFactor:1,
     isMobile:width<768,hasTouch:width<768,locale:"cs-CZ"
   });
   const page=await ctx.newPage();
   const errors=[];
   try{
    const {response}=await navigatePublicGet(page,URL,{timeout:60000});
    if(!response||response.status()!==200)errors.push("HTTP_NOT_200");
    const d=await page.evaluate(()=>{
      const canonicalLinks=[...document.querySelectorAll("link[rel~='canonical']")]
        .map(x=>x.href);
      const main=document.querySelector(".td-post-content")
        || document.querySelector(".entry-content")
        || document.querySelector("article");
      return {
        canonicalLinks,
        h1:document.querySelector("h1")?.textContent?.trim()||"",
        articleFound:!!main,
        viewportWidth:innerWidth,
        contentOverflows:main?main.getBoundingClientRect().width>innerWidth+15:null
      };
    });
    if(!d.articleFound)errors.push("ARTICLE_BODY_NOT_FOUND");
    if(d.h1.length<8)errors.push("ORIGINAL_H1_NOT_FOUND");
    if(d.canonicalLinks.length!==1||d.canonicalLinks[0]!==URL)
      errors.push("PUBLIC_CANONICAL_NOT_UNIQUE_SELF");
    if(d.contentOverflows)errors.push("ARTICLE_CONTENT_OVERFLOWS_VIEWPORT");
    await page.screenshot({path:"reports/browser-qa/canonical-8713-"+width+".png",
      fullPage:false,animations:"disabled",timeout:15000});
    results.push({width,errors});
   }catch(e){
     results.push({width,errors:["BROWSER_"+e.constructor.name]});
   }
   await ctx.close();
  }
 }finally{await browser.close();}
 console.log(JSON.stringify({scope:"xfit_8713_public_canonical",results,
  wordpress_writes:0,commercial_clicks:0}));
 if(results.some(r=>r.errors.length))process.exitCode=2;
})().catch(e=>{
 console.error("CANONICAL_8713_MOBILE_ERROR:"+e.constructor.name);
 process.exitCode=2;
});
