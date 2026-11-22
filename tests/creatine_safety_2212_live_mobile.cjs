/* Real mobile Chromium smoke test of the exact already-published legacy rescue.
 * No merchant clicks, pixels, secrets, custom analytics or WordPress writes. */
const {chromium} = require("playwright");
const fs = require("fs");
const {navigatePublicGet} = require("../scripts/xfit_mobile_navigation.cjs");

const URL = "https://xfit.cz/bezpecnostni-aspekty-kreatinu-monohydratu-a-jak-minimalizovat-rizika/";
const TARGETS = [
  "https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/",
  "https://xfit.cz/kreatin-a-jeho-vliv-na-ledviny-a-jatra/",
  "https://xfit.cz/xfit-os-kreatin-poradce/",
];
const CHECKS = [
  "Rychlá odpověď:",
  "Ledviny a kreatinin:",
  "Dehydratace, křeče a změna hmotnosti",
  "Zdroje, metodika a omezení",
];
(async () => {
  fs.mkdirSync("reports/browser-qa",{recursive:true});
  const browser = await chromium.launch({headless:true});
  const result = [];
  try {
    for (const width of [320, 375, 768]) {
      const ctx = await browser.newContext({
        viewport: {width, height: 812},
        deviceScaleFactor: 1, isMobile: width < 768, hasTouch: width < 768,
        locale: "cs-CZ",
      });
      const page = await ctx.newPage();
      const errors = [];
      try {
        const {response} = await navigatePublicGet(page, URL, {timeout:60000});
        if (!response || response.status() !== 200) {
          errors.push("HTTP_NOT_200");
        } else {
          const data = await page.evaluate(() => {
            const article = document.querySelector(".td-post-content") ||
              document.querySelector(".entry-content") ||
              document.querySelector("article");
            const text = article?.innerText || "";
            const hrefs = [...(article?.querySelectorAll("a[href]") || [])]
              .map(a=>a.href).filter(x=>x.startsWith("https://xfit.cz/"));
            const headers = [...(article?.querySelectorAll("h2") || [])];
            const rect = article?.getBoundingClientRect();
            return {
              title: document.querySelector("h1")?.textContent?.trim() || "",
              found: !!article,
              body: text,
              hrefs,
              h2: headers.length,
              articleWidth: rect ? Math.round(rect.width) : null,
              viewportWidth: innerWidth,
            };
          });
          if (!data.found) errors.push("ARTICLE_NOT_FOUND");
          if (!data.title.includes("Bezpečnostní aspekty kreatinu monohydrátu")) {
            errors.push("TITLE_MISMATCH");
          }
          for (const word of CHECKS) {
            if (!data.body.includes(word)) errors.push("MISSING_EDITORIAL_MARKER");
          }
          if (data.body.toLowerCase().includes("5nm2022")) {
            errors.push("OLD_COUPON_STILL_VISIBLE_IN_ARTICLE");
          }
          if (data.h2 < 7) errors.push("SECTION_STRUCTURE_MISSING");
          if (data.articleWidth !== null &&
              data.articleWidth > data.viewportWidth + 20) {
            errors.push("ARTICLE_HORIZONTAL_OVERFLOW");
          }
          for (const target of TARGETS) {
            if (!data.hrefs.includes(target)) errors.push("MISSING_FIRST_PARTY_ROUTE");
          }
        }
        await page.screenshot({
          path:"reports/browser-qa/creatine-safety-2212-"+width+".png",
          fullPage:false, animations:"disabled", timeout:15000,
        });
      } catch (error) {
        errors.push("BROWSER_QA_"+error.constructor.name);
      }
      result.push({width,errors});
      await ctx.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({scope:"creatine_safety_2212_public_mobile",results:result,
    wp_writes:0,external_merchant_clicks:0}));
  if(result.some(x=>x.errors.length)) process.exitCode = 2;
})().catch(error => {
  console.error("CREATINE_SAFETY_MOBILE_QA_ERROR:"+error.constructor.name);
  process.exitCode=2;
});
