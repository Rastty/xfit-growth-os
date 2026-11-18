/* Real local Chromium QA for both feed-backed above-the-fold decisions.
 * Synthetic catalog only; never opens merchant links or touches WordPress.
 */
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const fixture = String.raw`
import json
from datetime import datetime, timezone
from tests.test_quick_pick import BASE, SAMPLE
from tests.test_price_tradeoff import catalog_item
from scripts.xfit_creatine_guide import build_document as creatine
from scripts.xfit_whey_guide import build_document as whey
data = {}
for kind, builder, category, titles in (
    ('creatine', creatine, 'Kreatin', ('Creatine Monohydrate 1kg', 'Creatine Monohydrate 500g', 'Creatine Monohydrate 750g')),
    ('whey', whey, 'Syrovátkové proteiny', ('Whey WPC 1kg', 'Whey WPC 500g', 'Whey WPI 750g')),
):
    catalog = {'merchant':'namaximum.cz', 'merchant_match':True,
               'fetched_at_utc':datetime.now(timezone.utc).isoformat(),
               'products':[catalog_item(i, title, price, category) for i, title, price in
                           zip((901, 902, 903), titles, (700, 450, 900))]}
    data[kind] = builder(catalog, BASE, SAMPLE)['content']
print(json.dumps(data, ensure_ascii=False))
`;

(async () => {
  const documents = JSON.parse(execFileSync('python', ['-c', fixture], {encoding: 'utf8'}));
  const bundleAvailable = fs.existsSync(chromium.executablePath());
  const systemChromium = '/usr/bin/chromium';
  const browser = await chromium.launch({headless: true,
    ...(!bundleAvailable && fs.existsSync(systemChromium)
      ? {executablePath: systemChromium} : {})});
  try {
    for (const kind of ['creatine', 'whey']) {
      for (const width of [320, 375, 768]) {
        const context = await browser.newContext({viewport: {width, height: 812},
          isMobile: true, hasTouch: true, locale: 'cs-CZ'});
        const page = await context.newPage();
        // Images are not part of this first-screen contract; keep it offline.
        await page.route('**/*', route => route.abort());
        await page.setContent(`<!doctype html><html lang="cs"><head>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>body{margin:0;font:16px/1.45 Arial,sans-serif;color:#1e3035}
          main{padding:12px;max-width:760px;margin:auto}a{color:#116a70}</style>
          </head><body><main>${documents[kind]}</main></body></html>`);
        const metrics = await page.evaluate(() => {
          const main = document.querySelector('main').getBoundingClientRect();
          const cta = document.querySelector('#xfit-rychly-vyber [data-xfit-cta="quick-pick"]')
            .getBoundingClientRect();
          const nav = document.querySelector('nav').getBoundingClientRect();
          return {scrollWidth: document.documentElement.scrollWidth,
            viewportWidth: window.innerWidth, ctaTop: cta.top - main.top,
            navTop: nav.top - main.top, ctaHeight: cta.height};
        });
        assert.ok(metrics.scrollWidth <= metrics.viewportWidth + 1,
          `${kind} ${width}px horizontal overflow: ${JSON.stringify(metrics)}`);
        assert.ok(metrics.ctaTop < metrics.navTop,
          `${kind} ${width}px merchant choice hidden below navigation`);
        // Bound the first actionable offer to an early content region even
        // at narrow 320 px; production theme/header is tested separately.
        assert.ok(metrics.ctaTop < 1850,
          `${kind} ${width}px first product too far below content start: ${JSON.stringify(metrics)}`);
        assert.ok(metrics.ctaHeight >= 44, `${kind} ${width}px undersized merchant CTA`);
        assert.equal(await page.locator('#xfit-rychly-vyber [data-xfit-cta="quick-pick"]').count(), 2);
        // Exactly one extra editorial link is allowed on whey; an additional
        // merchant, tracking or unreviewed outbound link must fail preview QA.
        assert.equal(await page.locator('#xfit-rychly-vyber a').count(), kind === 'whey' ? 6 : 5);
        if (kind === 'whey') {
          const educationFirst = await page.evaluate(() => {
            const education = document.querySelector(
              '#xfit-rychly-vyber a[href="https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/"]');
            const merchant = document.querySelector('#xfit-rychly-vyber [data-xfit-cta="quick-pick"]');
            return !!education && !!merchant && !!(education.compareDocumentPosition(merchant) & Node.DOCUMENT_POSITION_FOLLOWING);
          });
          assert.ok(educationFirst, 'whey label-price education must precede first merchant choice');
        }
        if (width === 375) {
          const dir = path.resolve(__dirname, '../reports/browser-qa');
          fs.mkdirSync(dir, {recursive:true});
          await page.screenshot({path:path.join(dir, `adviser-${kind}-early-choices.png`), fullPage:false});
        }
        console.log(JSON.stringify({kind,width,state:'PASS',ctaOffsetPx:Math.round(metrics.ctaTop)}));
        await context.close();
      }
    }
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
