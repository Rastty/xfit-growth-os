const {chromium}=require('playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const phase=process.argv[2];assert.ok(['preview','live'].includes(phase));
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage({viewport:{width:375,height:812}});
  const url='https://xfit.cz/ctyri-zaludne-zdroje-cukru/',target='https://xfit.cz/xfit-os-arasidova-a-orechova-masla/';
  if(phase==='preview')await page.setContent('<meta name="viewport" content="width=device-width, initial-scale=1">'+fs.readFileSync('content/revisions/sugar-label-four-sources.html','utf8'));
  else {await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});assert.equal(page.url(),url);}
  const a=page.locator('a[data-xfit-sugar-offers="20261127"]');
  assert.equal(await a.count(),1);assert.equal(await a.getAttribute('href'),target);
  await a.scrollIntoViewIfNeeded();
  const b=await a.boundingBox();assert.ok(b&&b.x>=-1&&b.x+b.width<=376);
  if(phase==='live'){await page.goto(target,{waitUntil:'domcontentloaded',timeout:45000});assert.equal(page.url(),target);assert.ok(await page.locator('article.xfit-product-card').count()>=2);}
  console.log(JSON.stringify({state:'SUGAR_LABEL_MOBILE_'+phase.toUpperCase()+'_VERIFIED',width:375,target,merchant_clicks:0}));
 }finally{await browser.close();}
})().catch(()=>{console.error('SUGAR_LABEL_MOBILE_BLOCKED');process.exitCode=2;});
