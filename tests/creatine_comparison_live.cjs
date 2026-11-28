const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const URL='https://xfit.cz/xfit-os-kreatin-poradce/';
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
  for(const width of [375,1280]){
   const page=await browser.newPage({viewport:{width,height:900}});
   await page.setExtraHTTPHeaders({'Cache-Control':'no-cache','Pragma':'no-cache'});
   await page.goto(URL,{waitUntil:'domcontentloaded',timeout:60000});
   const comparison=page.locator('#xfit-creatine-compare');
   await comparison.waitFor({state:'visible',timeout:15000});
   const cards=page.locator('article.xfit-product-card');
   const choices=comparison.locator('a[data-xfit-creatine-compare]');
   const count=await cards.count();
   assert.ok(count>=2&&count<=6);
   assert.equal(await choices.count(),count);
   assert.equal(await comparison.evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
   for(let i=0;i<count;i++){
    const c=cards.nth(i),a=choices.nth(i);
    assert.equal(await a.getAttribute('href'),'#'+await c.getAttribute('id'));
    const title=(await c.locator('h3').innerText()).trim();
    assert.ok((await a.innerText()).includes(title));
    assert.equal(await c.evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
    for(const link of [a,c.locator('a[rel~="sponsored"]')]){
     const b=await link.boundingBox();
     assert.ok(b&&b.height>=44&&b.x>=-1&&b.x+b.width<=width+1,'invalid geometry');
    }
   }
   await choices.first().click();
   assert.equal(new global.URL(page.url()).hash,'#xfit-offer-1');
   console.log(JSON.stringify({state:'CREATINE_COMPARISON_LIVE_VERIFIED',width,cards:count,merchant_clicks:0}));
   await page.close();
  }
 }finally{await browser.close()}
})().catch(err=>{console.error('CREATINE_COMPARISON_QA_FAILED: '+err.name+' '+String(err.message||'').slice(0,200));process.exitCode=2});
