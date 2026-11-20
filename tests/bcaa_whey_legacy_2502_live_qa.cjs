// Live public read-only browser QA. No outbound merchant clicks or consent actions.
const {chromium} = require('playwright');
const {navigatePublicGet} = require('../scripts/xfit_mobile_navigation.cjs');
const fs = require('fs');

const slug = '/bcaa-vs-whey-protein-jake-jsou-rozdily-a-ktere-doplneni-je-pro-vas-nejlepsi/';
const url = 'https://xfit.cz' + slug;
const expected = [
  'https://xfit.cz/xfit-os-protein-guide/',
  'https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/',
  'https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/',
];

(async () => {
  fs.mkdirSync('reports/browser-qa', {recursive:true});
  const browser = await chromium.launch({headless:true});
  let failed = false;
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
          const panels = [...document.querySelectorAll('[data-xfit-bcaa-choice="v1"]')];
          const panel = panels[0];
          if (panels.length!==1 || !panel) return {count:panels.length};
          const links = [...panel.querySelectorAll('a[href]')];
          const own = links.filter(x=>destinations.includes(x.href));
          const injected = links.filter(x=>!destinations.includes(x.href));
          const article = panel.closest('.td-post-content') || panel.parentElement;
          const heading = article?.querySelector('h2');
          const body = article?.innerText || '';
          return {count:panels.length,docWidth:document.documentElement.scrollWidth,
            actionLinks:own.map(a=>a.href),labels:own.map(a=>a.textContent.trim()),
            heights:own.map(a=>a.getBoundingClientRect().height),
            widths:own.map(a=>a.getBoundingClientRect().width),
            beforeHeading:!!heading && !!(panel.compareDocumentPosition(heading)
              & Node.DOCUMENT_POSITION_FOLLOWING),
            hasSources:body.includes('NIH Office of Dietary Supplements')
              && body.includes('International Society of Sports Nutrition'),
            noCoupon:!body.includes('5NM2022'),
            noOldEnglish:!body.includes('What are BCAAs and whey protein?'),
            injectedLinkCount:injected.length,
          };
        }, expected);
        const issues=[];
        if(result.count!==1)issues.push('panel_missing_or_duplicate');
        if(result.docWidth>width+12)issues.push('horizontal_overflow');
        if(!result.beforeHeading)issues.push('not_before_first_section');
        if(!result.hasSources)issues.push('missing_sources');
        if(!result.noCoupon)issues.push('expired_coupon_visible');
        if(!result.noOldEnglish)issues.push('duplicate_english_visible');
        if(result.actionLinks?.length!==3 || expected.some((x,i)=>result.actionLinks[i]!==x))
          issues.push('decision_link_drift');
        if(result.heights?.some(x=>x<44) || result.widths?.some(x=>x<150))
          issues.push('small_touch_target');
        if(result.labels?.some(x=>x.length<16))issues.push('unclear_decision');
        if(width===375){
          await page.locator('[data-xfit-bcaa-choice="v1"]').scrollIntoViewIfNeeded();
          await page.screenshot({path:'reports/browser-qa/bcaa-whey-2502-375.png',
            animations:'disabled',fullPage:false,timeout:10000});
        }
        console.log(JSON.stringify({page:'bcaa-whey-2502',viewport:width,
          state:issues.length?'FAIL':'PASS',touchHeights:result.heights?.map(Math.round),
          injectedLinkCount:result.injectedLinkCount||0,issues}));
        if(issues.length)failed=true;
      } catch(error){failed=true; console.log(JSON.stringify({page:'bcaa-whey-2502',
        viewport:width,state:'ERROR',type:error.name,message:error.message.slice(0,180)}));}
      finally{await context.close();}
    }
  } finally {await browser.close();}
  if(failed)process.exitCode=2;
})().catch(e=>{console.error(e.message);process.exitCode=2;});
