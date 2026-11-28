const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const URL='https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/';
const routes=['https://xfit.cz/xfit-os-sejkry-a-sportovni-lahve/','https://xfit.cz/xfit-os-arasidova-a-orechova-masla/','https://xfit.cz/xfit-os-fitness-obleceni-nabidky/'];
(async()=>{
  const phase=process.argv[2];assert.ok(['preview','live'].includes(phase));
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:375,height:812}});
    if(phase==='preview'){
      await page.setContent('<meta name="viewport" content="width=device-width, initial-scale=1">'+fs.readFileSync('reports/beginner-apparel-hub-preview.html','utf8'));
    }else{
      await page.goto(URL,{waitUntil:'domcontentloaded',timeout:45000});
      assert.equal(page.url(),URL);
    }
    const original=page.locator('section[data-xfit-choice-version="four-lanes-20261127"]');
    assert.equal(await original.count(),1);
    assert.equal(await original.locator('a').count(),6);
    assert.ok((await original.locator('a').first().textContent()).includes('bez nákupu'));
    const nav=page.locator('#xfit-dalsi-nabidky-20261127');
    assert.equal(await nav.count(),1);
    assert.deepEqual(await nav.locator('a').evaluateAll(xs=>xs.map(a=>a.getAttribute('href'))),routes);
    for(const a of await nav.locator('a').all()){
      const box=await a.boundingBox();
      assert.ok(box&&box.height>=44&&box.x>=-1&&box.x+box.width<=376);
    }
    assert.equal(await nav.evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
    fs.mkdirSync('reports/browser-qa',{recursive:true});
    await nav.scrollIntoViewIfNeeded();
    await page.screenshot({path:'reports/browser-qa/beginner-apparel-hub-'+phase+'.png'});
    console.log(JSON.stringify({state:'APPAREL_HUB_MOBILE_'+phase.toUpperCase()+'_VERIFIED',width:375,choices:9,merchant_clicks:0}));
  }finally{await browser.close();}
})().catch(()=>{console.error('APPAREL_HUB_MOBILE_QA_FAILED');process.exitCode=2;});
