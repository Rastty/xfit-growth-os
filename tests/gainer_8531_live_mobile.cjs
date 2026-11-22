/* Existing mass-gainer buyer page 8531, public Chrome only, no checkout clicks. */
const {chromium}=require("playwright");
const fs=require("fs");
const {navigatePublicGet}=require("../scripts/xfit_mobile_navigation.cjs");
const URL="https://xfit.cz/jake-jsou-klicove-faktory-pri-vyberu-nejlepsiho-gainery-pro-fitness-a-rust-svalove-hmoty/";
const LINKS=[
 "https://www.ausport.gov.au/ais/nutrition/supplements/group_a/sports-foods2/isolated-protein-supplement2/how-and-when-do-i-use-it",
 "https://acsm.org/healthy-weight-gain-athletes/",
 "https://pubmed.ncbi.nlm.nih.gov/38537251/",
 "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/",
 "https://xfit.cz/xfit-os-protein-guide/",
 "https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/",
 "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/"
];
(async()=>{
 fs.mkdirSync("reports/browser-qa",{recursive:true});
 const browser=await chromium.launch({headless:true});
 const results=[];
 try{
  for(const width of [320,375,768]){
   const context=await browser.newContext({viewport:{width,height:812},
     deviceScaleFactor:1,isMobile:width<768,hasTouch:width<768,locale:"cs-CZ"});
   const page=await context.newPage();
   const errors=[];
   try{
    const {response}=await navigatePublicGet(page,URL,{timeout:60000});
    if(!response||response.status()!==200)errors.push("HTTP_NOT_200");
    const d=await page.evaluate(()=>{
      const root=document.querySelector(".td-post-content") ||
                 document.querySelector(".entry-content") ||
                 document.querySelector("article");
      const body=root?.innerText||"";
      const firstP=root?.querySelector("p")?.textContent||"";
      return {
        found:!!root,body,firstP,
        h1:document.querySelector("h1")?.textContent?.trim()||"",
        h2:root?.querySelectorAll("h2").length||0,
        links:[...(root?.querySelectorAll("a[href]")||[])].map(x=>x.href),
        canonicals:[...document.querySelectorAll("link[rel~='canonical']")].map(x=>x.href),
        articleWidth:root?.getBoundingClientRect().width??0,
        viewportWidth:innerWidth,
        nestedDoctype:(root?.innerHTML||"").toLowerCase().includes("<!doctype")
      };
    });
    if(!d.found)errors.push("ARTICLE_NOT_FOUND");
    if(!d.h1.toLocaleLowerCase("cs-CZ").includes("gainer"))
       errors.push("ORIGINAL_TITLE_NOT_PRESERVED");
    if(!d.firstP.toLocaleLowerCase("cs-CZ").includes("rychlá odpověď"))
       errors.push("FIRST_SCREEN_VERDICT_MISSING");
    if(!d.body.includes("gainer nemusíte kupovat"))
       errors.push("NO_BUY_OPTION_NOT_VISIBLE");
    if(!d.body.includes("93,75")||!d.body.includes("modelový příklad"))
       errors.push("PRICE_CALCULATION_MISSING_CONTEXT");
    if(d.h2<7)errors.push("REVIEWED_SECTIONS_MISSING");
    if(d.canonicals.length!==1||d.canonicals[0]!==URL)
       errors.push("CANONICAL_NOT_UNIQUE_SELF");
    if(d.nestedDoctype)errors.push("NESTED_HTML_DOCUMENT_REMAINS");
    if(d.articleWidth>d.viewportWidth+15)errors.push("ARTICLE_OVERFLOWS");
    for(const link of LINKS){
      if(!d.links.includes(link))errors.push("SOURCE_OR_BUYER_GUIDE_LINK_MISSING");
    }
    await page.screenshot({path:"reports/browser-qa/gainer-8531-"+width+".png",
         fullPage:false,animations:"disabled",timeout:15000});
   }catch(e){errors.push("BROWSER_"+e.constructor.name);}
   results.push({width,errors});
   await context.close();
  }
 }finally{await browser.close();}
 console.log(JSON.stringify({scope:"gainer_8531_public_buyer_guide",
   results,merchant_clicks:0,wp_writes:0}));
 if(results.some(x=>x.errors.length))process.exitCode=2;
})().catch(e=>{console.error("GAINER_8531_BROWSER_ERROR:"+e.constructor.name);process.exitCode=2;});
