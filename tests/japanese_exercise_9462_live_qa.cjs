// Live read-only Chromium QA after a native onepost release; no outbound clicks.
const {chromium} = require('playwright');
const {navigatePublicGet} = require('../scripts/xfit_mobile_navigation.cjs');
const fs = require('fs');

const slug = '/japonske-cviceni-na-hubnuti-objasnujeme-zakladni-principy/';
const url = 'https://xfit.cz' + slug;
const targets = [
  url + '#desetiminutovy-plan',
  'https://xfit.cz/pilates-vs-kardio-co-je-lepsi-pro-hubnuti/',
  'https://xfit.cz/kolik-bilkovin-potrebujete-pro-budovani-svalu-pruvodce-spravnym-stravovanim/',
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
        if (response?.status()!==200 || new URL(page.url()).pathname!==slug)
          throw new Error('public_permalink_unverified');
        const result = await page.evaluate(destinations => {
          const panels = [...document.querySelectorAll('[data-xfit-radio-taiso="v1"]')];
          const panel = panels[0];
          const article = document.querySelector('article#post-9462 .td-post-content');
          const links = panel ? [...panel.querySelectorAll('a[href]')] : [];
          const own = links.filter(a=>destinations.includes(a.href));
          const canonical = [...document.querySelectorAll('link[rel="canonical"]')].map(x=>x.href);
          const body = article?.innerText || '';
          const heading = article?.querySelector('h2');
          return {count:panels.length,article:!!article,
            docWidth:document.documentElement.scrollWidth,
            actionLinks:own.map(x=>x.href),
            touchHeights:own.map(x=>x.getBoundingClientRect().height),
            touchWidths:own.map(x=>x.getBoundingClientRect().width),
            labels:own.map(x=>x.innerText.trim()),
            otherPanelLinks:links.length-own.length,
            firstSectionAfter:!!heading && !!panel && !!(panel.compareDocumentPosition(heading)
              & Node.DOCUMENT_POSITION_FOLLOWING),
            localPlanExists:!!article?.querySelector('#desetiminutovy-plan'),
            canonical,hasWHO:body.includes('Světová zdravotnická organizace'),
            hasJapan:body.includes('Japan Post Insurance'),hasCDC:body.includes('Americké CDC'),
            badMarkup:!!article && /<!DOCTYPE|www\.example\.com|5NM2022|ketomix/i.test(article.innerHTML),
          };
        }, targets);
        const issues=[];
        if (result.count!==1 || !result.article) issues.push('article_or_navigation_missing');
        if (result.docWidth>width+12) issues.push('horizontal_overflow');
        if (!result.firstSectionAfter) issues.push('decision_not_before_sections');
        if (result.canonical.length!==1 || result.canonical[0]!==url)
          issues.push('canonical_wrong_or_duplicate');
        if (!result.localPlanExists) issues.push('local_plan_not_reachable');
        if (!result.hasWHO || !result.hasJapan || !result.hasCDC) issues.push('sources_missing');
        if (result.badMarkup) issues.push('legacy_markup_or_promo_present');
        if (result.actionLinks.length!==3 || targets.some((x,i)=>result.actionLinks[i]!==x))
          issues.push('cta_destination_drift');
        if (result.touchHeights.some(x=>x<44) || result.touchWidths.some(x=>x<150))
          issues.push('small_touch_target');
        if (result.labels.some(x=>x.length<20)) issues.push('unclear_cta');
        if (width===375 && result.count===1) {
          await page.locator('[data-xfit-radio-taiso="v1"]').scrollIntoViewIfNeeded();
          await page.screenshot({path:'reports/browser-qa/japanese-exercise-9462-375.png',
            animations:'disabled',fullPage:false,timeout:10000});
        }
        console.log(JSON.stringify({article:9462,viewport:width,
          state:issues.length?'FAIL':'PASS',touchHeights:result.touchHeights.map(Math.round),
          canonicalCount:result.canonical.length,injectedAdLinks:result.otherPanelLinks,issues}));
        if (issues.length) failures++;
      } catch (error) {
        failures++;
        console.log(JSON.stringify({article:9462,viewport:width,state:'ERROR',
          error:error.message.slice(0,180)}));
      } finally {await context.close();}
    }
  } finally {await browser.close();}
  if (failures) process.exitCode=2;
})().catch(error=>{console.error(error.message);process.exitCode=2;});
