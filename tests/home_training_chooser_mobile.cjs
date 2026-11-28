const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const URL='https://xfit.cz/co-je-to-funkcni-trenink/';
const choices=['start','paze','hyzde','stehna','lytka','gear','gym','rest'];
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
  fs.mkdirSync('reports/browser-qa',{recursive:true});
  for(const width of [375,768,1280]){
   const page=await browser.newPage({viewport:{width,height:900}});
   await page.setExtraHTTPHeaders({'Cache-Control':'no-cache','Pragma':'no-cache'});
   await page.goto(URL,{waitUntil:'domcontentloaded',timeout:45000});
   const nav=page.locator('#xfit-home-training-chooser-v1');
   await nav.waitFor({state:'visible',timeout:15000});
   assert.equal(await nav.count(),1);
   assert.equal(await nav.evaluate(el=>el.scrollWidth>el.clientWidth+2),false,'chooser overflow');
   const links=nav.locator('a[data-xfit-choice]');
   assert.deepEqual(await links.evaluateAll(els=>els.map(a=>a.dataset.xfitChoice)),choices);
   for(let i=0;i<choices.length;i++){
    const link=links.nth(i);
    const box=await link.boundingBox();
    assert.ok(box && box.height>=44 && box.x>=-1 && box.x+box.width<=width+1,'invalid touch geometry '+choices[i]);
    await link.focus();
    assert.equal(await link.evaluate(a=>document.activeElement===a),true,'keyboard focus');
   }
   await nav.scrollIntoViewIfNeeded();
   await page.screenshot({path:'reports/browser-qa/home-training-'+width+'.png',animations:'disabled',timeout:15000});
   const start=nav.locator('[data-xfit-choice="start"]');
   await start.click();
   assert.equal(new global.URL(page.url()).hash,'#xfit-home-first-session');
   assert.equal(await page.locator('#xfit-home-first-session').count(),1);
   await page.close();
  }
  console.log(JSON.stringify({state:'HOME_TRAINING_CHOOSER_RESPONSIVE_VERIFIED',widths:[375,768,1280],choices:8,keyboard_focus:true,local_jump:true,merchant_clicks:0}));
 }finally{await browser.close()}
})().catch(err=>{console.error('HOME_TRAINING_CHOOSER_QA_FAILED: '+err.name+' '+String(err.message||'').slice(0,200));process.exitCode=2});
