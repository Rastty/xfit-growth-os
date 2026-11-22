/* User-facing independent public mobile QA of revised existing BCAA #9371.
 * Does not click merchant links or submit analytics/health-related data. */
const {chromium}=require("playwright");
const fs=require("fs");
const {navigatePublicGet}=require("../scripts/xfit_mobile_navigation.cjs");
const URL="https://xfit.cz/jak-spravne-pouzivat-bcaa-pro-lepsi-regeneraci-a-svalovy-rust/";
const SOURCES=[
 "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/",
 "https://pmc.ncbi.nlm.nih.gov/articles/PMC5477153/",
 "https://pmc.ncbi.nlm.nih.gov/articles/PMC12674588/",
 "https://xfit.cz/xfit-os-protein-guide/",
 "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
 "https://xfit.cz/xfit-os-jak-vybrat-rostlinny-protein/",
];
(async()=>{
 fs.mkdirSync("reports/browser-qa",{recursive:true});
 const browser=await chromium.launch({headless:true});
 const results=[];
 try{
  for(const width of [320,375,768]){
   const context=await browser.newContext({
     viewport:{width,height:812},deviceScaleFactor:1,
     isMobile:width<768,hasTouch:width<768,locale:"cs-CZ"
   });
   const page=await context.newPage();
   const errors=[];
   try{
    const {response}=await navigatePublicGet(page,URL,{timeout:60000});
    if(!response||response.status()!==200)errors.push("HTTP_NOT_200");
    const v=await page.evaluate(()=>{
      const root=document.querySelector(".td-post-content") ||
          document.querySelector(".entry-content") ||
          document.querySelector("article");
      const h1=document.querySelector("h1")?.textContent||"";
      const body=root?.innerText||"";
      const links=[...(root?.querySelectorAll("a[href]")||[])].map(x=>x.href);
      const canonicalLinks=[...document.querySelectorAll("link[rel~='canonical']")].map(x=>x.href);
      const h2=root?.querySelectorAll("h2").length||0;
      const firstP=root?.querySelector("p")?.textContent||"";
      const articleWidth=root?.getBoundingClientRect().width??0;
      return {rootFound:!!root,h1,body,links,canonicalLinks,
              h2,firstP,articleWidth,viewportWidth:innerWidth,
              nestedDoctype:(root?.innerHTML||"").toLowerCase().includes("<!doctype")};
    });
    if(!v.rootFound)errors.push("ARTICLE_ROOT_MISSING");
    if(!v.h1.toLocaleLowerCase("cs-CZ").includes("bcaa"))
      errors.push("BCAA_H1_NOT_PRESERVED");
    if(v.h2<7)errors.push("SEVEN_REVIEWED_SECTIONS_MISSING");
    if(!v.firstP.toLocaleLowerCase("cs-CZ").includes("rychlá odpověď"))
      errors.push("ABOVE_FIRST_SECTION_NO_BUY_VERDICT_MISSING");
    if(!v.body.includes("nekoupit nic"))
      errors.push("NO_PURCHASE_DECISION_MISSING");
    if(v.canonicalLinks.length!==1||v.canonicalLinks[0]!==URL)
      errors.push("CANONICAL_NOT_UNIQUE_SELF");
    if(v.nestedDoctype)errors.push("NESTED_DOCUMENT_STILL_RENDERED");
    for(const target of SOURCES){
      if(!v.links.includes(target))errors.push("REQUIRED_EDITORIAL_LINK_MISSING");
    }
    if(v.links.some(x=>x.includes("example.com")))
      errors.push("WRONG_LEGACY_DESTINATION_STILL_LINKED");
    if(v.articleWidth>v.viewportWidth+15)
      errors.push("ARTICLE_OVERFLOWS");
    await page.screenshot({path:"reports/browser-qa/bcaa-9371-"+width+".png",
       fullPage:false,animations:"disabled",timeout:15000});
   }catch(e){errors.push("CHROMIUM_"+e.constructor.name);}
   results.push({width,errors});
   await context.close();
  }
 }finally{await browser.close();}
 console.log(JSON.stringify({scope:"bcaa_9371_public_evidence_and_canonical",
   results,merchant_clicks:0,wp_writes:0}));
 if(results.some(x=>x.errors.length))process.exitCode=2;
})().catch(e=>{console.error("BCAA_9371_BROWSER_ERROR:"+e.constructor.name);process.exitCode=2;});
