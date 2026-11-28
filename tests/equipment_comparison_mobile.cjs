const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const URL = 'https://xfit.cz/xfit-os-vybaveni-na-domaci-cviceni-nabidky/';
async function main() {
  const phase = process.argv[2];
  assert.ok(['preview','live'].includes(phase));
  const doc = JSON.parse(fs.readFileSync('reports/private-equipment-comparison.json','utf8'));
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:375,height:812},deviceScaleFactor:1});
    await page.setContent('<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>'+doc.content+'</body></html>');
    const links = await page.locator('article.xfit-product-card a[rel~="sponsored"]').evaluateAll(els=>els.map(a=>a.href));
    assert.ok(links.length >= 2 && links.length <= 8);
    const budget = page.locator('#xfit-gear-budget-v1');
    assert.equal(await budget.count(),1);
    const norm = text => text.replace(/\s+/g,' ').replace(/[–—−]/g,'-').trim();
    const expectedBudget = (await budget.locator('h2,p').allTextContents()).map(norm).filter(Boolean);
    const expectedPrices = await budget.locator('strong').evaluateAll(els=>els.map(e=>e.textContent.replace(/\s+/g,' ').replace(/[–—−]/g,'-').trim()));
    const expectedOptional = [];
    for(const id of ['xfit-gear-ball','xfit-gear-massage']){
      if(await page.locator('#'+id).count()) expectedOptional.push(id);
    }
    if(phase === 'live'){
      await page.setExtraHTTPHeaders({'Cache-Control':'no-cache','Pragma':'no-cache'});
      await page.goto(URL,{waitUntil:'domcontentloaded',timeout:60000});
      await budget.waitFor({state:'visible',timeout:15000});
      assert.equal(new global.URL(page.url()).pathname, new global.URL(URL).pathname);
    }
    const cards = page.locator('article.xfit-product-card[id^="xfit-gear-offer-"]');
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
    assert.equal(await budget.count(),1);
    assert.deepEqual((await budget.locator('h2,p').allTextContents()).map(norm).filter(Boolean),expectedBudget,'budget text differs after rendering');
    assert.deepEqual(await budget.locator('strong').evaluateAll(els=>els.map(e=>e.textContent.replace(/\s+/g,' ').replace(/[–—−]/g,'-').trim())),expectedPrices,'budget prices differ');
    assert.equal(await budget.evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'budget overflow');
    for(const id of ['xfit-gear-mat','xfit-gear-band',...expectedOptional]){
      const a=budget.locator('a[href="#'+id+'"]');
      assert.equal(await a.count(),1);
      const box=await a.boundingBox();
      assert.ok(box && box.height>=44 && box.x>=-1 && box.x+box.width<=376,'budget jump link geometry');
      assert.equal(await page.locator('#'+id).count(),1,'budget target missing');
    }
    if(phase === 'live'){
      const guide = page.locator('#xfit-gear-buying-guide-v1');
      await guide.waitFor({state:'visible',timeout:15000});
      assert.equal(await guide.count(),1);
      assert.equal(await guide.isVisible(),true);
      assert.equal(await guide.locator('h4').count(),4);
      const gymLink=guide.locator('a[href="https://xfit.cz/domaci-posilovny-a-workout-hriste/"]');
      assert.equal(await gymLink.count(),1);
      assert.equal(await gymLink.isVisible(),true);
      assert.equal(await guide.evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'guide overflow');
    }
    fs.mkdirSync('reports/browser-qa',{recursive:true});
    await cards.first().scrollIntoViewIfNeeded();
    await page.screenshot({path:'reports/browser-qa/equipment-'+phase+'.png'});
    console.log(JSON.stringify({state:'EQUIPMENT_MOBILE_'+phase.toUpperCase()+'_VERIFIED',cards:links.length,budget_verified:true,optional_groups:expectedOptional,width:375,clicked_merchant_links:0}));
  } finally {await browser.close();}
}
main().catch(err=>{console.error('EQUIPMENT_MOBILE_QA_FAILED: '+(err?.name==='AssertionError' ? (err.message||'').split('\n')[0].slice(0,120) : err?.name||'unknown'));process.exitCode=2;});
