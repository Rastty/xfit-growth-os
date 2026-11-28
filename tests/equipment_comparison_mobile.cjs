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
    assert.ok(links.length >= 2 && links.length <= 14);
    const budget = page.locator('#xfit-gear-budget-v1');
    assert.equal(await budget.count(),1);
    const norm = text => text.replace(/\s+/g,' ').replace(/[–—−]/g,'-').trim();
    const expectedBudget = (await budget.locator('h2,p').allTextContents()).map(norm).filter(Boolean);
    const expectedPrices = await budget.locator('strong').evaluateAll(els=>els.map(e=>e.textContent.replace(/\s+/g,' ').replace(/[–—−]/g,'-').trim()));
    const expectedOptional = [];
    for(const id of ['xfit-gear-ball','xfit-gear-massage','xfit-gear-glove','xfit-gear-belt','xfit-gear-strap']){
      if(await page.locator('#'+id).count()) expectedOptional.push(id);
    }
    const nav=page.locator('#xfit-equipment-nav-v2');
    const expectedChoiceTexts=await nav.locator('[data-xfit-gear-choice]').allTextContents();
    const expectedNav=['#xfit-gear-mat','#xfit-gear-band',...expectedOptional.map(id=>'#'+id),'#xfit-gear-budget-v1'];
    if(phase === 'live'){
      await page.setExtraHTTPHeaders({'Cache-Control':'no-cache','Pragma':'no-cache'});
      await page.goto(URL,{waitUntil:'domcontentloaded',timeout:60000});
      await budget.waitFor({state:'visible',timeout:15000});
      assert.equal(new global.URL(page.url()).pathname, new global.URL(URL).pathname);
    }
    assert.equal(await nav.count(),1);
    assert.deepEqual((await nav.locator('[data-xfit-gear-choice]').allTextContents()).map(norm),expectedChoiceTexts.map(norm),'feed-bound category text');
    assert.equal(await nav.locator('[data-xfit-nav-price]').count(),expectedNav.length-1);
    const grids=page.locator('[data-xfit-offer-grid]');
    assert.equal(await grids.count(),expectedNav.length-1);
    for(let i=0;i<await grids.count();i++){
      assert.equal(await grids.nth(i).evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'product grid overflow');
    }
    assert.deepEqual(await nav.locator('a').evaluateAll(els=>els.map(a=>a.getAttribute('href'))),expectedNav,'category navigation targets');
    assert.equal(await nav.evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'category navigation overflow');
    for(let i=0;i<expectedNav.length;i++){
      const box=await nav.locator('a').nth(i).boundingBox();
      assert.ok(box && box.height>=44 && box.x>=-1 && box.x+box.width<=376,'category navigation geometry');
      assert.equal(await page.locator(expectedNav[i]).count(),1,'category destination exists');
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
      const training=page.locator('#xfit-gear-training-return-v1');
      await training.waitFor({state:'visible',timeout:15000});
      assert.equal(await training.count(),1);
      const trainingLink=training.locator('a[href="https://xfit.cz/co-je-to-funkcni-trenink/"]');
      assert.equal(await trainingLink.count(),1);
      const trainingBox=await trainingLink.boundingBox();
      assert.ok(trainingBox && trainingBox.height>=44 && trainingBox.x>=-1 && trainingBox.x+trainingBox.width<=376,'training choice geometry');
      assert.equal(await training.evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'training choice overflow');
      const guide = page.locator('#xfit-gear-buying-guide-v1');
      await guide.waitFor({state:'visible',timeout:15000});
      assert.equal(await guide.count(),1);
      assert.equal(await guide.isVisible(),true);
      assert.equal(await guide.locator('h4').count(),4);
      const gymLink=guide.locator('a[href="https://xfit.cz/domaci-posilovny-a-workout-hriste/"]');
      assert.equal(await gymLink.count(),1);
      assert.equal(await gymLink.isVisible(),true);
      assert.equal(await guide.evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'guide overflow');
      const strength=page.locator('#xfit-strength-accessory-guide-v1');
      await strength.waitFor({state:'visible',timeout:15000});
      assert.equal(await strength.count(),1);
      assert.equal(await strength.locator('h4').count(),4);
      assert.equal(await strength.evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'strength guide overflow');
      const back=strength.locator('a[href="#xfit-gear-budget-v1"]');
      assert.equal(await back.count(),1);
      assert.ok(await back.isVisible());
      for(const id of expectedOptional.filter(id=>/glove|belt|strap/.test(id))){
        assert.equal(await page.locator('#'+id+' + p a[href="#xfit-strength-accessory-guide-v1"]').count(),1);
      }
    }
    fs.mkdirSync('reports/browser-qa',{recursive:true});
    await cards.first().scrollIntoViewIfNeeded();
    await page.screenshot({path:'reports/browser-qa/equipment-'+phase+'.png',timeout:15000,animations:'disabled'});
    console.log(JSON.stringify({state:'EQUIPMENT_MOBILE_'+phase.toUpperCase()+'_VERIFIED',cards:links.length,budget_verified:true,navigation_verified:true,optional_groups:expectedOptional,width:375,clicked_merchant_links:0}));
  } finally {await browser.close();}
}
main().catch(err=>{console.error('EQUIPMENT_MOBILE_QA_FAILED: '+(err?.name==='AssertionError' ? (err.message||'').split('\n')[0].slice(0,120) : err?.name||'unknown'));process.exitCode=2;});
