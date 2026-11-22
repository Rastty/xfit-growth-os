/* Source-bound browser check for the exact Black Mamba legacy article only.
 * Do not follow merchant links, cookies, tracking or external resources by hand. */
const {chromium} = require("playwright");
const fs=require("fs");
const {navigatePublicGet}=require("../scripts/xfit_mobile_navigation.cjs");

const URL="https://xfit.cz/black-mamba-co-to-je/";
const NEED=[
  "Rychlá odpověď:",
  "Co je Black Mamba a proč nestačí název produktu",
  "Stimulanty, kofein a synefrin:",
  "Zdroje a redakční metodika",
  "nekoupit nic",
];
const LINK=[
  "https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",
  "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
  "https://ods.od.nih.gov/factsheets/WeightLoss-HealthProfessional/",
];
(async()=>{
 fs.mkdirSync("reports/browser-qa",{recursive:true});
 const browser=await chromium.launch({headless:true});
 const result=[];
 try {
   for(const width of [320,375,768]){
     const ctx=await browser.newContext({
       viewport:{width,height:812},deviceScaleFactor:1,
       isMobile:width<768,hasTouch:width<768,locale:"cs-CZ",
     });
     const page=await ctx.newPage();
     const errors=[];
     try {
       const {response}=await navigatePublicGet(page,URL,{timeout:60000});
       if(!response || response.status()!==200){errors.push("HTTP_NOT_200");}
       else {
         const d=await page.evaluate(()=>{
           const root=document.querySelector(".td-post-content") ||
             document.querySelector(".entry-content") ||
             document.querySelector("article");
           const text=root?.innerText || "";
           const links=[...(root?.querySelectorAll("a[href]")||[])].map(x=>x.href);
           const w=root?.getBoundingClientRect().width||0;
           return {
             found:!!root,body:text,
             title:document.querySelector("h1")?.textContent?.trim()||"",
             h2:root?.querySelectorAll("h2").length||0,
             links,
             articleWidth:w,
             viewportWidth:innerWidth,
           };
         });
         if(!d.found)errors.push("ARTICLE_NOT_FOUND");
         if(!d.title.toLowerCase().includes("black mamba"))errors.push("H1_MISMATCH");
         if(d.h2<6)errors.push("MISSING_SIX_EXPLANATION_SECTIONS");
         for(const marker of NEED){
           if(!d.body.toLocaleLowerCase("cs-CZ").includes(
                 marker.toLocaleLowerCase("cs-CZ"))) errors.push("MISSING_REVIEWED_CONTENT");
         }
         for(const link of LINK){
           if(!d.links.includes(link))errors.push("MISSING_EVIDENCE_OR_NO_BUY_LINK");
         }
         if(d.links.some(x=>x.includes("us-supplements.to")))
           errors.push("UNVERIFIED_MERCHANT_STILL_LINKED");
         if(d.articleWidth>d.viewportWidth+15)
           errors.push("EDITORIAL_HORIZONTAL_OVERFLOW");
       }
       await page.screenshot({path:"reports/browser-qa/black-mamba-"+
         width+".png",fullPage:false,animations:"disabled",timeout:15000});
     } catch(e){errors.push("BROWSER_QA_"+e.constructor.name);}
     result.push({width,errors});
     await ctx.close();
   }
 } finally {await browser.close();}
 console.log(JSON.stringify({scope:"black_mamba_single_live_public",
   results:result,merchant_clicks:0,wp_writes:0}));
 if(result.some(r=>r.errors.length)) process.exitCode=2;
})().catch(e=>{console.error("BLACK_MAMBA_MOBILE_QA_ERROR:"+e.constructor.name);process.exitCode=2;});
