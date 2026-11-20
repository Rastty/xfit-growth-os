// Read-only public Chromium QA after native onepost publisher. No affiliate clicks.
const {chromium} = require('playwright');
const {navigatePublicGet} = require('../scripts/xfit_mobile_navigation.cjs');
const fs = require('fs');

const slug = '/kreatin-jako-podpora-energetickeho-metabolismu-pri-intenzivnim-treninku-v-ramci-fitness-diety/';
const url = 'https://xfit.cz' + slug;
const targets = [
  'https://xfit.cz/xfit-os-kreatin-nebo-protein/',
  'https://xfit.cz/xfit-os-kreatin-poradce/',
  'https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/',
];

(async () => {
  fs.mkdirSync('reports/browser-qa', {recursive:true});
  const browser = await chromium.launch({headless:true});
  let failures = 0;
  try {
    for (const width of [320,375,768]) {
      const context = await browser.newContext({viewport:{width,height:812},
        isMobile:true,hasTouch:true,locale:'cs-CZ'});
      try {
        const page = await context.newPage();
        const {response} = await navigatePublicGet(page,url,{timeout:60000});
        if (response?.status() !== 200 || new URL(page.url()).pathname !== slug)
          throw new Error('public_permalink_not_verified');
        const result = await page.evaluate(expected => {
          const panels = [...document.querySelectorAll('[data-xfit-creatine-10953="v1"]')];
          const panel = panels[0];
          const article = document.querySelector('article#post-10953 .td-post-content');
          const own = panel ? [...panel.querySelectorAll('a[href]')].filter(a => expected.includes(a.href)) : [];
          const firstHeading = article?.querySelector('h2');
          const allCan = [...document.querySelectorAll('link[rel="canonical"]')].map(x => x.href);
          const text = article?.innerText || '';
          return {count:panels.length,article:!!article,docWidth:document.documentElement.scrollWidth,
            links:own.map(a=>a.href),heights:own.map(a=>a.getBoundingClientRect().height),
            widths:own.map(a=>a.getBoundingClientRect().width),
            labels:own.map(a=>a.innerText.trim()),
            otherPanelLinks:panel ? panel.querySelectorAll('a[href]').length-own.length : -1,
            beforeHeading:!!firstHeading && !!panel && !!(panel.compareDocumentPosition(firstHeading)
              & Node.DOCUMENT_POSITION_FOLLOWING),
            canonical:allCan,hasNIH:text.includes('NIH Office of Dietary Supplements'),
            hasISSN:text.includes('International Society of Sports Nutrition'),
            badSource:!!article && (/<!DOCTYPE|www\.example\.com|script\.js|styles\.css|5NM2022/i.test(article.innerHTML)),
          };
        },targets);
        const issues=[];
        if (result.count !== 1 || !result.article) issues.push('decision_or_article_missing');
        if (result.docWidth > width + 12) issues.push('horizontal_overflow');
        if (!result.beforeHeading) issues.push('decision_below_first_section');
        if (result.canonical.length !== 1 || result.canonical[0] !== url) issues.push('canonical_wrong_or_duplicate');
        if (!result.hasNIH || !result.hasISSN) issues.push('sources_missing');
        if (result.badSource) issues.push('legacy_broken_markup_or_coupon');
        if (result.links.length !== 3 || targets.some((target,i)=>result.links[i]!==target))
          issues.push('decision_target_drift');
        if (result.heights?.some(height=>height<44) || result.widths?.some(w=>w<150))
          issues.push('small_touch_target');
        if (result.labels?.some(label=>label.length<24)) issues.push('unclear_decision');
        if (width===375 && result.count === 1) {
          await page.locator('[data-xfit-creatine-10953="v1"]').scrollIntoViewIfNeeded();
          await page.screenshot({path:'reports/browser-qa/creatine-10953-375.png',
            animations:'disabled',fullPage:false,timeout:10000});
        }
        console.log(JSON.stringify({article:10953,viewport:width,
          state:issues.length?'FAIL':'PASS',touchHeights:result.heights?.map(Math.round),
          injectedAdLinks:result.otherPanelLinks,canonicalCount:result.canonical.length,issues}));
        if (issues.length) failures++;
      } catch (error) {
        failures++;
        console.log(JSON.stringify({article:10953,viewport:width,state:'ERROR',
          error:error.message.slice(0,180)}));
      } finally {await context.close();}
    }
  } finally {await browser.close();}
  if (failures) process.exitCode=2;
})().catch(error=>{console.error(error.message);process.exitCode=2;});
