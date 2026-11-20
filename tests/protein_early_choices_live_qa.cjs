// Independent real-Chromium mobile confirmation of the onepost protein handoff.
// Never click a merchant link or send analytics/consent events.
const {chromium} = require("playwright");
const {navigatePublicGet} = require("../scripts/xfit_mobile_navigation.cjs");
const fs = require("fs");

const url = "https://xfit.cz/xfit-os-protein-guide/";
const destinations = [
  "https://xfit.cz/kolik-bilkovin-potrebujete-pro-budovani-svalu-pruvodce-spravnym-stravovanim/",
  "https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/",
  "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
];

(async () => {
  const browser = await chromium.launch({headless:true});
  let failed = false;
  try {
    fs.mkdirSync("reports/browser-qa", {recursive:true});
    for (const width of [320, 375, 768]) {
      const context = await browser.newContext({
        viewport:{width,height:812},isMobile:true,hasTouch:true,locale:"cs-CZ",
      });
      try {
        const page = await context.newPage();
        const {response} = await navigatePublicGet(page,url,{timeout:60000});
        if (!response || response.status()!==200 || new URL(page.url()).pathname!==
            "/xfit-os-protein-guide/") throw new Error("public_permalink_unverified");
        const actual = await page.evaluate(() => {
          const navs = [...document.querySelectorAll('[data-xfit-choice="protein-guide-v1"]')];
          const n=navs[0];
          if (navs.length!==1 || !n) return {count:navs.length};
          const anchors=[...n.querySelectorAll("a[href]")];
          const article=n.closest(".td-post-content") || n.parentElement;
          const firstArticleHeading=article?.querySelector("h2");
          return {count:1,viewport:innerWidth,docWidth:document.documentElement.scrollWidth,
            headingBefore:!!firstArticleHeading && !!(n.compareDocumentPosition(
              firstArticleHeading) & Node.DOCUMENT_POSITION_FOLLOWING),
            noMerchant:!n.querySelector('a[href*="namaximum.cz"]'),
            labels:anchors.map(a=>a.textContent.trim()),
            links:anchors.map(a=>a.href),
            sizes:anchors.map(a=>({height:a.getBoundingClientRect().height,
              width:a.getBoundingClientRect().width})),
          };
        });
        const issues=[];
        if (actual.count!==1) issues.push("panel_missing_or_duplicate");
        if (actual.docWidth>width+12) issues.push("horizontal_overflow");
        if (!actual.headingBefore) issues.push("panel_after_first_section");
        if (!actual.noMerchant) issues.push("direct_merchant_in_educational_panel");
        if (actual.links?.length!==3 || destinations.some((x,i)=>actual.links?.[i]!==x))
          issues.push("routes_changed");
        if (actual.sizes?.some(x=>x.height<44 || x.width<150)) issues.push("small_touch_target");
        if (actual.labels?.some(x=>!x || x.length<15)) issues.push("unclear_action");
        if (width===375) {
          await page.locator('[data-xfit-choice="protein-guide-v1"]').scrollIntoViewIfNeeded();
          await page.screenshot({path:"reports/browser-qa/protein-early-choices-375.png",
            animations:"disabled",fullPage:false,timeout:10000});
        }
        console.log(JSON.stringify({page:"protein-guide",viewport:width,
          state:issues.length?"FAIL":"PASS",count:actual.count,
          touchHeights:actual.sizes?.map(x=>Math.round(x.height)),issues}));
        if (issues.length) failed = true;
      } catch (error) {
        failed = true;
        console.log(JSON.stringify({page:"protein-guide",viewport:width,
          state:"ERROR",kind:error.name}));
      } finally {await context.close();}
    }
  } finally {await browser.close();}
  if (failed) process.exitCode=2;
})().catch(err=>{console.error(err.name);process.exitCode=2;});
