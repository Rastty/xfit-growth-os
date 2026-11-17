/* Real Chromium smoke for the self-contained XFIT prototype; no WP writes. */
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

(async () => {
  const url = pathToFileURL(path.resolve(__dirname, '../assets/tools/protein-price/index.html')).href;
  // CI installs the pinned Playwright Chromium. Only fall back to the system
  // binary for local diagnostics when that exact bundle is unavailable.
  const systemChromium = '/usr/bin/chromium';
  const bundledAvailable = fs.existsSync(chromium.executablePath());
  const browser = await chromium.launch({headless:true,
    ...(!bundledAvailable && fs.existsSync(systemChromium) ? {executablePath:systemChromium} : {})});
  try {
    for(const width of [320, 375, 768]) {
      const context = await browser.newContext({viewport:{width,height:812},locale:'cs-CZ',isMobile:true,hasTouch:true});
      const page = await context.newPage();
      const calls = [];
      page.on('request', req => { if(!req.url().startsWith('file:')) calls.push(req.url()); });
      await page.goto(url);
      assert.equal(await page.locator('h1').count(), 1);
      assert.equal(await page.locator('label[for]').count(), 8);
      assert.equal(await page.locator('form [name]').count(), 8);
      const layout = await page.evaluate(() => ({width:innerWidth,scroll:document.documentElement.scrollWidth,
        button:document.querySelector('button[type="submit"]').getBoundingClientRect().height}));
      assert.ok(layout.scroll <= layout.width+1, `horizontal overflow ${width}: ${JSON.stringify(layout)}`);
      assert.ok(layout.button >= 44, `inaccessible tap target at ${width}`);

      await page.locator('#xfit-a-price').fill('899');
      await page.locator('#xfit-a-mass').fill('900');
      await page.locator('#xfit-a-protein').fill('75');
      await page.getByRole('button',{name:'Spočítat cenu bílkovin'}).click();
      assert.match(await page.locator('[data-role="result"]').innerText(), /133,19 Kč/);
      assert.doesNotMatch(await page.locator('[data-role="result"]').innerText(), /Balení B:/);

      await page.locator('#xfit-b-price').fill('849');
      await page.locator('#xfit-b-mass').fill('750');
      await page.locator('#xfit-b-protein').fill('82');
      await page.getByRole('button',{name:'Spočítat cenu bílkovin'}).click();
      const result = await page.locator('[data-role="result"]').innerText();
      assert.match(result, /138,05 Kč/);
      assert.match(result, /nižší cenu[\s\S]*balení A/i);

      await page.locator('#xfit-b-protein').fill('');
      await page.getByRole('button',{name:'Spočítat cenu bílkovin'}).click();
      assert.match(await page.locator('[data-role="result"]').innerText(), /doplňte všechny tři/);
      assert.doesNotMatch(await page.locator('[data-role="result"]').innerText(), /133,19 Kč/);
      await page.getByRole('button',{name:'Vymazat údaje'}).click();
      assert.equal(await page.locator('[data-role="result"]').innerText(), '');
      assert.deepEqual(calls, [], 'calculator unexpectedly requested remote content');
      if(width === 375){
        fs.mkdirSync(path.resolve(__dirname,'../reports/browser-qa'),{recursive:true});
        await page.screenshot({path:path.resolve(__dirname,'../reports/browser-qa/protein-price-tool-mobile.png')});
      }
      await context.close();
      process.stdout.write(JSON.stringify({width,state:'PASS',remoteRequests:0})+'\n');
    }
  } finally {await browser.close();}
})().catch(e => {console.error(e); process.exitCode=1;});
