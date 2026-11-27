const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ids={'3377':'vybaveni-do-fitka-jak-vybrat-vhodnou-podlozku-na-pilates-cviceni','7487':'jak-vybrat-spravnou-podlozku-pro-cviceni-pilates'};
const target='https://xfit.cz/xfit-os-vybaveni-na-domaci-cviceni-nabidky/#xfit-gear-mat';
(async()=>{
 const id=process.argv[2],phase=process.argv[3];assert.ok(ids[id]&&['preview','live'].includes(phase));
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage({viewport:{width:375,height:812}});
  const url='https://xfit.cz/'+ids[id]+'/';
  if(phase==='preview'){
   const doc=JSON.parse(fs.readFileSync(id==='3377'?'content/revisions/pilates-mat-home-studio-3377.json':'content/revisions/pilates-mat-choice-7487.json','utf8'));
   await page.setContent('<meta name="viewport" content="width=device-width, initial-scale=1">'+doc.content);
  }else{await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});assert.equal(page.url(),url);}
  const link=page.locator('a[data-xfit-mat-offers="'+id+'"]');
  assert.equal(await link.count(),1);assert.equal(await link.getAttribute('href'),target);
  await link.scrollIntoViewIfNeeded();
  const box=await link.boundingBox();assert.ok(box&&box.height>=44&&box.x>=-1&&box.x+box.width<=376);
  fs.mkdirSync('reports/browser-qa',{recursive:true});await page.screenshot({path:'reports/browser-qa/mat-'+id+'-'+phase+'.png'});
  if(phase==='live'){
   await page.goto(target,{waitUntil:'domcontentloaded',timeout:45000});
   assert.equal(new URL(page.url()).hash,'#xfit-gear-mat');
   assert.equal(await page.locator('#xfit-gear-mat').count(),1);
  }
  console.log(JSON.stringify({state:'LEGACY_MAT_MOBILE_'+phase.toUpperCase()+'_VERIFIED',post_id:Number(id),width:375,target,merchant_clicks:0}));
 }finally{await browser.close();}
})().catch(()=>{console.error('LEGACY_MAT_MOBILE_QA_FAILED');process.exitCode=2;});
