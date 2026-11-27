const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ids={"11753":"kreatin-pro-zacatecniky-jaky-druh-kreatinu-si-vybrat-pro-cviceni","11863":"porovnani-nejucinnejsich-druhu-kreatinu-pro-sportovce","11882":"nejlepsi-kreatin-pro-fitness-jak-vybrat-ten-spravny-pro-vas"};
const target='https://xfit.cz/xfit-os-kreatin-poradce/';
let stage='setup';
(async()=>{
 const id=process.argv[2],phase=process.argv[3];assert.ok(ids[id]&&['preview','live'].includes(phase));
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage({viewport:{width:375,height:812}});
  const url='https://xfit.cz/'+ids[id]+'/';
  stage='load_source';
  if(phase==='preview'){
   const doc=JSON.parse(fs.readFileSync('content/revisions/legacy-creatine-'+id+'.json','utf8'));
   await page.setContent('<meta name="viewport" content="width=device-width, initial-scale=1">'+doc.content);
  }else{await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});assert.equal(page.url(),url);}
  stage='exact_source_anchor';
  const link=page.locator('a[data-xfit-creatine-offers="'+id+'"]');
  assert.equal(await link.count(),1);assert.equal(await link.getAttribute('href'),target);
  stage='scroll_source_anchor';
  await link.scrollIntoViewIfNeeded({timeout:15000});
  stage='source_anchor_geometry';
  const box=await link.boundingBox();assert.ok(box&&box.height>=44&&box.x>=-1&&box.x+box.width<=376);
  fs.mkdirSync('reports/browser-qa',{recursive:true});await page.screenshot({path:'reports/browser-qa/creatine-'+id+'-'+phase+'.png'});
  if(phase==='live'){
   stage='load_destination';
   await page.goto(target,{waitUntil:'domcontentloaded',timeout:45000});
   assert.equal(page.url(),target);
   stage='destination_cards';
   await page.locator('article.xfit-product-card').first().waitFor({state:'visible',timeout:15000});
   assert.ok(await page.locator('article.xfit-product-card').count()>=2);
  }
  console.log(JSON.stringify({state:'LEGACY_CREATINE_MOBILE_'+phase.toUpperCase()+'_VERIFIED',post_id:Number(id),width:375,target,merchant_clicks:0}));
 }finally{await browser.close();}
})().catch(()=>{console.error(JSON.stringify({state:'LEGACY_CREATINE_MOBILE_QA_FAILED',stage}));process.exitCode=2;});
