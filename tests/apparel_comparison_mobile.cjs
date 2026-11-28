const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const URL = 'https://xfit.cz/xfit-os-fitness-obleceni-nabidky/';
async function main() {
  const phase = process.argv[2];
  assert.ok(['preview','live'].includes(phase));
  const doc = JSON.parse(fs.readFileSync('reports/private-apparel-comparison.json','utf8'));
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:375,height:812},deviceScaleFactor:1});
    await page.setContent('<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>'+doc.content+'</body></html>');
    const links = await page.locator('article.xfit-product-card a[rel~="sponsored"]').evaluateAll(els=>els.map(a=>a.href));
    assert.ok(links.length >= 3 && links.length <= 15);
    const sizeSelector = 'details[id^="xfit-size-picker-"] li[data-xfit-size] a[rel~="sponsored"]';
    const sizeLinks = await page.locator(sizeSelector).evaluateAll(els=>els.map(a=>a.href));
    assert.ok(sizeLinks.length>=3 && sizeLinks.length<=65);
    const expectedBra = await page.locator('#xfit-apparel-bra').count();
    const expectedTop = await page.locator('#xfit-apparel-top').count();
    if(phase === 'live'){
      await page.goto(URL,{waitUntil:'domcontentloaded',timeout:45000});
      assert.equal(new global.URL(page.url()).pathname, new global.URL(URL).pathname);
    }
    assert.equal(await page.locator('#xfit-apparel-bra').count(),expectedBra);
    assert.equal(await page.locator('#xfit-apparel-top').count(),expectedTop);
    if(expectedBra){assert.equal(await page.locator('a[href="https://xfit.cz/jak-na-vyber-podprsenky/"]').count(),1);}
    const cards = page.locator('article.xfit-product-card[id^="xfit-apparel-offer-"]');
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
    assert.deepEqual(await page.locator(sizeSelector).evaluateAll(els=>els.map(a=>a.href)),sizeLinks);
    const pickers=page.locator('details[id^="xfit-size-picker-"]');
    for (const picker of await pickers.all()) {
      const summary=picker.locator('summary');
      assert.ok(await summary.isVisible());
      await summary.click();
      assert.equal(await picker.evaluate(el=>el.open),true);
      for(const link of await picker.locator('li[data-xfit-size] a').all()){
        assert.ok(await link.isVisible());
        const box=await link.boundingBox();
        assert.ok(box && box.height>=44 && box.x>=-1 && box.x+box.width<=376);
      }
      assert.equal(await picker.evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
      await summary.click();
    }
    if(phase==='live'){
      const guide=page.locator('#xfit-apparel-fit-guide-v1');
      assert.equal(await guide.count(),1,'editorial guide missing');
      assert.ok(await guide.locator('h2').count()>=5,'editorial headings missing');
      assert.ok((await guide.innerText()).split(/\s+/).length>=650,'editorial guide truncated');
      assert.equal(await guide.evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'editorial guide overflow');
      console.log('APPAREL_EDITORIAL_MOBILE_LIVE_VERIFIED');
    }
    fs.mkdirSync('reports/browser-qa',{recursive:true});
    await cards.first().scrollIntoViewIfNeeded();
    await page.screenshot({path:'reports/browser-qa/apparel-'+phase+'.png'});
    console.log(JSON.stringify({state:'APPAREL_MOBILE_'+phase.toUpperCase()+'_VERIFIED',cards:links.length,size_choices:sizeLinks.length,bra_section:expectedBra,top_section:expectedTop,width:375,clicked_merchant_links:0}));
  } finally {await browser.close();}
}
main().catch(err=>{console.error('APPAREL_MOBILE_QA_FAILED: '+(err?.name==='AssertionError'?(err.message||'').split('\n')[0].slice(0,120):err?.name||'unknown'));process.exitCode=2;});
