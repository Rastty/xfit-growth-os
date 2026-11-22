/* Real mobile verification of one existing internal decision-route source.
 * Does not click any commercial/affiliate links or transmit analytics data. */
const {chromium}=require("playwright");
const fs=require("fs");
const {navigatePublicGet}=require("../scripts/xfit_mobile_navigation.cjs");
const URL="https://xfit.cz/je-vhodne-uzivat-kreatin-a-protein-spolecne-pri-cviceni/";
const TARGET="https://xfit.cz/xfit-os-kreatin-nebo-protein/";
const PHRASE="Potřebujete kreatin, protein, oba, nebo ani jeden?";
(async()=>{
 fs.mkdirSync("reports/browser-qa",{recursive:true});
 const browser=await chromium.launch({headless:true});
 let results=[];
 try{
  for(const width of [320,375,768]){
   const ctx=await browser.newContext({viewport:{width,height:812},
      deviceScaleFactor:1,hasTouch:width<768,isMobile:width<768,
      locale:"cs-CZ"});
   const page=await ctx.newPage();
   let failures=[];
   try{
    const {response}=await navigatePublicGet(page,URL,{timeout:60000});
    if(!response||response.status()!==200)failures.push("HTTP_NOT_200");
    const data=await page.evaluate(()=>{
      const article=document.querySelector(".td-post-content") ||
                    document.querySelector(".entry-content") ||
                    document.querySelector("article");
      const p=article?.querySelector(
        'p[data-xfit-handoff="xfit-joint-creatine-protein-chooser-20261122"]');
      const a=p?.querySelector("a[href]");
      const rect=p?.getBoundingClientRect();
      const h2=article?.querySelector("h2")?.getBoundingClientRect();
      return {
       articleFound:!!article,
       h1:document.querySelector("h1")?.textContent?.trim()||"",
       text:p?.textContent?.trim()||"",
       href:a?.href||"",
       markerCount:article?.querySelectorAll(
        'p[data-xfit-handoff="xfit-joint-creatine-protein-chooser-20261122"]').length||0,
       top:rect?.top??null,firstH2Top:h2?.top??null,
       paragraphWidth:rect?.width??null,viewportWidth:innerWidth,
      };
    });
    if(!data.articleFound)failures.push("ARTICLE_NOT_FOUND");
    if(!data.h1.toLocaleLowerCase("cs").includes("kreatin")||
       !data.h1.toLocaleLowerCase("cs").includes("protein"))
       failures.push("TITLE_SCOPE_CHANGED");
    if(data.markerCount!==1)failures.push("REVIEWED_HANDOFF_MISSING_OR_DUPLICATE");
    if(!data.text.includes(PHRASE))failures.push("BUYER_DECISION_NOT_VISIBLE");
    if(data.href!==TARGET)failures.push("WRONG_DECISION_DESTINATION");
    if(data.top!==null&&data.firstH2Top!==null&&data.top>data.firstH2Top)
       failures.push("EARLY_HANDOFF_BELOW_FIRST_SECTION");
    if(data.paragraphWidth!==null&&data.paragraphWidth>data.viewportWidth+15)
       failures.push("PARAGRAPH_OVERFLOW");
    await page.screenshot({path:"reports/browser-qa/joint-creatine-protein-"+width+".png",
       fullPage:false,animations:"disabled",timeout:15000});
   }catch(e){failures.push("BROWSER_"+e.constructor.name);}
   results.push({width,failures});
   await ctx.close();
  }
 }finally{await browser.close();}
 console.log(JSON.stringify({scope:"joint_4763_reader_route",results,
     merchant_clicks:0,wp_writes:0}));
 if(results.some(x=>x.failures.length))process.exitCode=2;
})().catch(e=>{console.error("JOINT_4763_MOBILE_ERROR:"+e.constructor.name);process.exitCode=2;});
