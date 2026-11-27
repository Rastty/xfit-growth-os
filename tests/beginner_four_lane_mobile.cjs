const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const URL='https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/';
const routes=['#zacatecnik-rozhodnuti','https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/','https://xfit.cz/xfit-os-rostlinne-proteiny-porovnani/','https://xfit.cz/xfit-os-kreatin-poradce/','https://xfit.cz/xfit-os-vybaveni-na-domaci-cviceni-nabidky/','https://xfit.cz/xfit-os-kreatin-nebo-protein/'];
(async()=>{
  const phase=process.argv[2];assert.ok(['preview','live'].includes(phase));
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:375,height:812}});
    if(phase==='preview'){
      await page.setContent('<meta name="viewport" content="width=device-width, initial-scale=1">'+fs.readFileSync('reports/beginner-four-lane-preview.html','utf8'));
    }else{
      await page.goto(URL,{waitUntil:'domcontentloaded',timeout:45000});
      assert.equal(page.url(),URL);
    }
    const nav=page.locator('section[data-xfit-choice-version="four-lanes-20261127"]');
    assert.equal(await nav.count(),1);
    const links=nav.locator('a');
    assert.deepEqual(await links.evaluateAll(xs=>xs.map(a=>a.getAttribute('href'))),routes);
    for(let i=0;i<5;i++){
      const box=await links.nth(i).boundingBox();
      assert.ok(box&&box.height>=44&&box.x>=-1&&box.x+box.width<=376);
    }
    assert.ok((await nav.locator('a').first().textContent()).includes('bez nákupu'));
    assert.equal(await nav.evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
    fs.mkdirSync('reports/browser-qa',{recursive:true});
    await nav.scrollIntoViewIfNeeded();
    await page.screenshot({path:'reports/browser-qa/beginner-four-lane-'+phase+'.png'});
    console.log(JSON.stringify({state:'FOUR_LANE_MOBILE_'+phase.toUpperCase()+'_VERIFIED',width:375,choices:6,merchant_clicks:0}));
  }finally{await browser.close();}
})().catch(()=>{console.error('FOUR_LANE_MOBILE_QA_FAILED');process.exitCode=2;});
