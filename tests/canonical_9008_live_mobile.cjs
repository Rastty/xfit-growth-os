/* Real Chromium public SEO canonical check, only exact reviewed WP #9008. */
const {chromium}=require("playwright");
const fs=require("fs");
const {navigatePublicGet}=require("../scripts/xfit_mobile_navigation.cjs");
const URL="https://xfit.cz/jaky-je-nejlepsi-cas-pro-uzivani-kreatinu-v-ramci-fitness-treninku/";
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
      const links=[...document.querySelectorAll("link[rel~='canonical']")]
        .map(x=>x.href);
      const main=document.querySelector(".td-post-content")
         ||document.querySelector(".entry-content")
         ||document.querySelector("article");
      const rect=main?.getBoundingClientRect();
      return {
        canonicalLinks:links,
        h1:document.querySelector("h1")?.textContent?.trim()||"",
        articleFound:!!main,
        articleOverflows:rect?rect.width>innerWidth+15:null,
        viewportWidth:innerWidth,
      };
    });
    if(!d.articleFound)errors.push("ARTICLE_BODY_NOT_FOUND");
    if(!d.h1.toLowerCase().includes("kreatin"))
      errors.push("EXPECTED_CREATIVE_TIMING_H1_MISSING");
    if(d.canonicalLinks.length!==1||d.canonicalLinks[0]!==URL)
      errors.push("PUBLIC_CANONICAL_NOT_UNIQUE_SELF");
    await page.screenshot({path:"reports/browser-qa/creatine-timing-canonical-"+width+".png",
      fullPage:false,animations:"disabled",timeout:15000});
    results.push({width,errors,articleOverflows:d.articleOverflows});
   }catch(e){
     results.push({width,errors:["BROWSER_"+e.constructor.name],articleOverflows:null});
   }
   await ctx.close();
  }
 }finally{await browser.close();}
 console.log(JSON.stringify({scope:"creatine_timing_9008_public_canonical",
   results,wp_writes:0,commercial_clicks:0}));
 if(results.some(x=>x.errors.length))process.exitCode=2;
})().catch(e=>{console.error("CANONICAL_9008_MOBILE_ERROR:"+e.constructor.name);process.exitCode=2;});
