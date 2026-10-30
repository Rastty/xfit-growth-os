const { chromium } = require("playwright");
const fs = require("fs");
const checks = [
  {name:"beginner",url:"https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",expected:"Doplňky stravy pro začátečníky",minH2:6,commercial:false},
  {name:"creatine",url:"https://xfit.cz/xfit-os-kreatin-poradce/",expected:"Jak vybrat kreatin",minH2:3,commercial:true},
  {name:"whey",url:"https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",expected:"Srovnání syrovátkových proteinů",minH2:3,commercial:true}
];
fs.mkdirSync("reports/browser-qa", {recursive:true});
(async()=>{
const browser=await chromium.launch({headless:true});
let bad=false;
for(const spec of checks){
 const context=await browser.newContext({viewport:{width:375,height:812},deviceScaleFactor:1,hasTouch:true,isMobile:true,locale:"cs-CZ"});
 const page=await context.newPage();
 const failures=[];
 try{
  const response=await page.goto(spec.url,{waitUntil:"domcontentloaded",timeout:60000});
  if(!response || response.status()>=400)failures.push("http_"+(response?.status()||"none"));
  await page.waitForTimeout(1200);
  const doc=await page.evaluate(()=>{
    const h1=[...document.querySelectorAll("h1")].map(n=>n.textContent.trim()).join(" | ");
    const h2=document.querySelectorAll("h2").length;
    const titles=[...document.querySelectorAll("h2")].map(n=>n.textContent.trim()).slice(0,15);
    const full=document.documentElement.scrollWidth;
    const inner=window.innerWidth;
    const details=document.querySelectorAll("details").length;
    const summaries=document.querySelectorAll("summary").length;
    const links=[...document.querySelectorAll('a[href*="namaximum.cz"]')];
    const missingSponsored=links.filter(n=>!n.relList.contains("sponsored")).length;
    const images=[...document.querySelectorAll("img")].filter(n=>n.getBoundingClientRect().width>30 && !n.alt);
    return {h1,h2,titles,viewport:inner,documentWidth:full,details,summaries,
        merchantLinks:links.length,missingSponsored,imagesMissingAlt:images.length,
        hasViewportMeta:!!document.querySelector('meta[name="viewport"]')};
  });
  if(!doc.h1.includes(spec.expected))failures.push("h1_missing_expected");
  if(doc.h2<spec.minH2)failures.push("insufficient_h2");
  if(!doc.hasViewportMeta)failures.push("mobile_viewport_missing");
  if(spec.commercial && !doc.merchantLinks)failures.push("merchant_links_missing");
  if(spec.commercial && doc.missingSponsored)failures.push("sponsored_rel_missing");
  if(spec.name==="beginner" && doc.details<3)failures.push("interactive_details_missing");
  if(doc.documentWidth>doc.viewport+12)failures.push("horizontal_overflow_"+(doc.documentWidth-doc.viewport));
  await page.screenshot({path:"reports/browser-qa/"+spec.name+"-mobile.png",fullPage:true});
  console.log(JSON.stringify({page:spec.name,state:failures.length?"FAIL":"PASS",doc,failures}));
 }catch(e){failures.push("browser_fetch_error_"+e.name);console.log(JSON.stringify({page:spec.name,state:"ERROR",failures}));}
 await context.close();
 bad ||= failures.length>0;
}
await browser.close();
if(bad)process.exitCode=2;

})().catch(e=>{console.error(e);process.exitCode=2;});
