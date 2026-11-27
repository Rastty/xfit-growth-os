const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const configs={
 'protein-guide':{id:25451,slug:'xfit-os-protein-guide',mark:'protein-guide-v2',targets:['https://xfit.cz/kolik-bilkovin-potrebujete-pro-budovani-svalu-pruvodce-spravnym-stravovanim/','https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/','https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/','https://xfit.cz/xfit-os-rostlinne-proteiny-porovnani/']},
 'protein-price':{id:25541,slug:'xfit-os-cena-proteinu-podle-etikety',mark:'protein-price-offers-v1',targets:['https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/','https://xfit.cz/xfit-os-rostlinne-proteiny-porovnani/']}
};
(async()=>{
 const cfg=configs[process.argv[2]],phase=process.argv[3];
 assert.ok(cfg&&['preview','live'].includes(phase));
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage({viewport:{width:375,height:812}});
  const url='https://xfit.cz/'+cfg.slug+'/';
  if(phase==='preview')await page.setContent('<meta name="viewport" content="width=device-width, initial-scale=1">'+fs.readFileSync('reports/protein-route-preview.html','utf8'));
  else{await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});assert.equal(page.url(),url);}
  const nav=page.locator('nav[data-xfit-choice="'+cfg.mark+'"]');assert.equal(await nav.count(),1);
  const links=nav.locator('a');assert.deepEqual(await links.evaluateAll(xs=>xs.map(a=>a.getAttribute('href'))),cfg.targets);
  for(let i=0;i<cfg.targets.length;i++){const box=await links.nth(i).boundingBox();assert.ok(box&&box.height>=44&&box.x>=-1&&box.x+box.width<=376);}
  assert.equal(await nav.evaluate(el=>el.scrollWidth>el.clientWidth+2),false);
  fs.mkdirSync('reports/browser-qa',{recursive:true});await nav.scrollIntoViewIfNeeded();
  await page.screenshot({path:'reports/browser-qa/protein-route-'+cfg.id+'-'+phase+'.png'});
  console.log(JSON.stringify({state:'PROTEIN_ROUTES_MOBILE_'+phase.toUpperCase()+'_VERIFIED',post_id:cfg.id,width:375,choices:cfg.targets.length,merchant_clicks:0}));
 }finally{await browser.close();}
})().catch(()=>{console.error('PROTEIN_ROUTES_MOBILE_QA_FAILED');process.exitCode=2;});
