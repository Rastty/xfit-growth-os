const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const URL = 'https://xfit.cz/xfit-os-orechova-masla-porovnani/';
async function main() {
  const phase = process.argv[2];
  assert.ok(['preview','live'].includes(phase));
  const doc = JSON.parse(fs.readFileSync('reports/private-nut-butter-comparison.json','utf8'));
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:375,height:812},deviceScaleFactor:1});
    await page.setContent('<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>'+doc.content+'</body></html>');
    const links = await page.locator('article.xfit-product-card a[rel~="sponsored"]').evaluateAll(els=>els.map(a=>a.href));
    assert.ok(links.length >= 2 && links.length <= 6);
    if(phase === 'live'){
      await page.goto(URL,{waitUntil:'domcontentloaded',timeout:45000});
      assert.equal(new global.URL(page.url()).pathname, new global.URL(URL).pathname);
    }
    const cards = page.locator('article.xfit-product-card[id^="xfit-nut-offer-"]');
    assert.equal(await cards.count(),links.length);
    const actual = await cards.locator('a[rel~="sponsored"]').evaluateAll(els=>els.map(a=>a.href));
    assert.equal(JSON.stringify(actual),JSON.stringify(links),'CTA destinations differ');
    for(let i=0;i<links.length;i++){
      const c=cards.nth(i);
      const a=c.locator('a[rel~="sponsored"]');
      const box=await a.boundingBox();
      assert.ok(box && box.height>=44 && box.x>=-1 && box.x+box.width<=376,'CTA geometry');
      const overflow=await c.evaluate(el=>el.scrollWidth>el.clientWidth+2);
      assert.equal(overflow,false,'Card horizontal overflow');
    }
    fs.mkdirSync('reports/browser-qa',{recursive:true});
    await cards.first().scrollIntoViewIfNeeded();
    await page.screenshot({path:'reports/browser-qa/nut-butter-'+phase+'.png'});
    console.log(JSON.stringify({state:'NUT_BUTTER_MOBILE_'+phase.toUpperCase()+'_VERIFIED',cards:links.length,width:375,clicked_merchant_links:0}));
  } finally {await browser.close();}
}
main().catch(()=>{console.error('NUT_BUTTER_MOBILE_QA_FAILED');process.exitCode=2;});
