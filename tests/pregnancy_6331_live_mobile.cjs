/* Exact original WP #6331 public page; no shopping or sensitive interactions. */
const {chromium}=require("playwright");
const fs=require("fs");
const {navigatePublicGet}=require("../scripts/xfit_mobile_navigation.cjs");
const URL="https://xfit.cz/spalovace-tuku-v-tehotenstvi-a-pri-kojeni-co-je-bezpecne-a-ucinne/";
const SOURCE_LINKS=[
 "https://www.nice.org.uk/guidance/NG247/chapter/recommendations",
 "https://www.rcog.org.uk/for-the-public/browse-our-patient-information/healthy-eating-and-vitamin-supplements-in-pregnancy/",
 "https://www.nhs.uk/baby/breastfeeding-and-bottle-feeding/breastfeeding-and-lifestyle/medicines/",
 "https://www.nhs.uk/baby/breastfeeding-and-bottle-feeding/breastfeeding-and-lifestyle/diet/",
 "https://ods.od.nih.gov/factsheets/WeightLoss-HealthProfessional/"
];
(async()=>{
 fs.mkdirSync("reports/browser-qa",{recursive:true});
 const browser=await chromium.launch({headless:true});
 const results=[];
 try{
  for(const width of [320,375,768]){
   const context=await browser.newContext({
     viewport:{width,height:812},deviceScaleFactor:1,
     isMobile:width<768,hasTouch:width<768,locale:"cs-CZ"});
   const page=await context.newPage(), errors=[];
   try{
    const {response}=await navigatePublicGet(page,URL,{timeout:60000});
    if(!response||response.status()!==200)errors.push("HTTP_NOT_200");
    const d=await page.evaluate(()=>{
      const root=document.querySelector(".td-post-content") ||
                 document.querySelector(".entry-content") ||
                 document.querySelector("article");
      const body=root?.innerText||"";
      const first=root?.querySelector("p")?.textContent||"";
      const links=[...(root?.querySelectorAll("a[href]")||[])].map(x=>x.href);
      return {found:!!root,body,first,
        h1:document.querySelector("h1")?.textContent?.trim()||"",
        h2:root?.querySelectorAll("h2").length||0,links,
        canonical:[...document.querySelectorAll("link[rel~='canonical']")].map(x=>x.href),
        width:root?.getBoundingClientRect().width??0,viewportWidth:innerWidth};
    });
    if(!d.found)errors.push("ARTICLE_ROOT_MISSING");
    if(!d.h1.toLocaleLowerCase("cs-CZ").includes("těhotenství") ||
       !d.h1.toLocaleLowerCase("cs-CZ").includes("kojení"))
       errors.push("PREGNANCY_TITLE_MISMATCH");
    if(!d.first.toLocaleLowerCase("cs-CZ").includes("krátká odpověď"))
       errors.push("FIRST_SCREEN_SAFETY_ANSWER_MISSING");
    if(!d.body.toLocaleLowerCase("cs-CZ").includes("nekupujte žádný spalovač"))
       errors.push("NO_BUY_RECOMMENDATION_MISSING");
    if(!d.body.includes("NICE")||!d.body.includes("NHS"))
       errors.push("OFFICIAL_RECOMMENDATIONS_MISSING");
    if(d.body.includes("5NM2022"))
       errors.push("EXPIRED_PROMO_STILL_VISIBLE");
    if(d.h2<6)errors.push("SIX_EDITORIAL_SECTIONS_MISSING");
    if(d.canonical.length!==1||d.canonical[0]!==URL)
       errors.push("CANONICAL_NOT_UNIQUE_SELF");
    if(d.width>d.viewportWidth+15)errors.push("ARTICLE_OVERFLOWS");
    for(const link of SOURCE_LINKS){
      if(!d.links.includes(link))errors.push("OFFICIAL_SOURCE_LINK_MISSING");
    }
    if(d.links.some(x=>/namaximum\.cz|us-supplements\.to|chytapust/i.test(x)))
       errors.push("PREGNANCY_MERCHANT_LINK_PRESENT");
    await page.screenshot({path:"reports/browser-qa/pregnancy-6331-"+width+".png",
      fullPage:false,animations:"disabled",timeout:15000});
   }catch(e){errors.push("CHROMIUM_"+e.constructor.name);}
   results.push({width,errors});
   await context.close();
  }
 }finally{await browser.close();}
 console.log(JSON.stringify({scope:"pregnancy_6331_public_no_buy",results,
   merchant_clicks:0,wp_writes:0}));
 if(results.some(x=>x.errors.length))process.exitCode=2;
})().catch(e=>{console.error("PREGNANCY_6331_QA_ERROR:"+e.constructor.name);process.exitCode=2;});
