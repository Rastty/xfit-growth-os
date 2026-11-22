/* Real Chrome proof of exactly one self canonical on the original WP #7268. */
const {chromium}=require("playwright");
const fs=require("fs");
const {navigatePublicGet}=require("../scripts/xfit_mobile_navigation.cjs");
const URL="https://xfit.cz/jak-mohu-dosahnout-svalu-na-brise-bez-nutnosti-pouziti-vybaveni/";
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
     const canonicals=[...document.querySelectorAll("link[rel~='canonical']")]
       .map(e=>e.href);
     const main=document.querySelector(".td-post-content")
       ||document.querySelector(".entry-content")
       ||document.querySelector("article");
     return {canonicals,articleFound:!!main,
      h1:document.querySelector("h1")?.textContent?.trim()||"",
      articleOverflow:!!main&&main.getBoundingClientRect().width>innerWidth+15};
    });
    if(d.canonicals.length!==1||d.canonicals[0]!==URL)
      errors.push("PUBLIC_CANONICAL_NOT_UNIQUE_SELF");
    if(!d.articleFound)errors.push("ARTICLE_BODY_MISSING");
    if(d.h1.length<8)errors.push("H1_MISSING");
    if(d.articleOverflow)errors.push("ARTICLE_HORIZONTAL_OVERFLOW");
    await page.screenshot({path:"reports/browser-qa/canonical-7268-"+width+".png",
     fullPage:false,animations:"disabled",timeout:15000});
   }catch(e){errors.push("BROWSER_"+e.constructor.name);}
   results.push({width,errors});
   await ctx.close();
  }
 }finally{await browser.close();}
 console.log(JSON.stringify({state:"PUBLIC_7268_CHROME_VERIFIED",
  results,wp_writes:0,commercial_clicks:0}));
 if(results.some(r=>r.errors.length))process.exitCode=2;
})().catch(e=>{console.error("7268_CHROME_"+e.constructor.name);process.exitCode=2;});
