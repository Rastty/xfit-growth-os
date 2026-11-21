"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const SCRIPT = fs.readFileSync(
  path.join(__dirname, "..", "assets", "analytics", "xfit-outbound.js"), "utf8"
);
const URL_OK = "https://www.namaximum.cz/p/creatine?variant=392&utm_medium=affiliate" +
  "&utm_campaign=affial.com&utm_source=pap&a_aid=TESTA&a_bid=TESTB";

function harness({consent = true, bridge = true, page = "/xfit-os-kreatin-poradce/"} = {}) {
  const calls = [];
  const funnel = [];
  const listeners = {};
  const root = {
    location: {
      protocol: "https:", hostname: "xfit.cz", pathname: page,
      search: "", hash: "", href: "https://xfit.cz" + page,
    },
    document: {
      addEventListener: (type, handler) => { listeners[type] = handler; },
    },
    gtag: (...args) => {
      if (args[1] === "affiliate_outbound_click") calls.push(args);
      else funnel.push(args);
    },
  };
  if (bridge) root.xfitGetAnalyticsConsent = () => consent;
  root.getWccConsent = () => ({categories:{analytics:consent}});
  vm.runInNewContext(SCRIPT, { window: root, URL });
  return {
    calls, funnel, root,
    decide({type = "nav", href = "#xfit-need", trusted = true,
            googleAnnotation = false, confirmed = true} = {}) {
      const anchor = {
        classList: {contains: name => name === "google-anno" && googleAnnotation},
        getAttribute: name => name === "href" ? href :
          name === "data-xfit-funnel-complete" && type === "no_buy" && confirmed
            ? "no-buy" : null,
        hasAttribute: () => false,
        closest: selector =>
          selector === 'nav[aria-label="Rychlá navigace poradcem"]' && type === "nav" ||
          selector === '[data-xfit-quick-pick="no-buy"]' && type === "no_buy" ||
          selector === "section#xfit-rychly-vyber" && type === "no_buy" ? {} : null,
      };
      listeners.click({
        isTrusted: trusted,
        target: {closest: selector => selector === "a" ? anchor : null},
      });
    },
    click({href = URL_OK, id = "392", engine = "creatine",
           rel = "sponsored nofollow", trusted = true, card = true,
           hero = false} = {}) {
      const link = {
        dataset: { xfitProductId: id, xfitEngine: engine, xfitPartner: "namaximum",
                   xfitCta: hero ? "quick-pick" : undefined },
        getAttribute: (name) => ({href, rel})[name] || null,
        closest: (selector) =>
          (selector === "article.xfit-product-card" && card && !hero) ||
          (selector === "[data-xfit-quick-pick]" && hero) ||
          (selector === "section#xfit-rychly-vyber" && hero) ? {} : null,
      };
      listeners.click({
        isTrusted: trusted,
        target: { closest: (selector) =>
          selector === "a[data-xfit-product-id]" ? link : null },
      });
    },
  };
}

test("real choice start and no-buy completion are distinct, consented and deduped", () => {
  const h = harness();
  h.decide({type:"nav"});
  assert.deepEqual(JSON.parse(JSON.stringify(h.funnel)), [
    ["event", "advisor_start", {
      page:"xfit-os-kreatin-poradce", selection_engine:"creatine"
    }]
  ]);
  h.decide({type:"nav", href:"#xfit-offers"});
  assert.equal(h.funnel.length, 1, "navigation is not a completion");
  h.decide({type:"no_buy"});
  assert.equal(h.funnel.length, 2);
  assert.deepEqual(JSON.parse(JSON.stringify(h.funnel[1])), [
    "event", "advisor_complete", {
      page:"xfit-os-kreatin-poradce", selection_engine:"creatine"
    }
  ]);
  h.decide({type:"no_buy"});
  assert.equal(h.funnel.length, 2, "one completion per viewed page");
  assert.equal(h.calls.length, 0, "no-buy never becomes a merchant click");
  for (const event of h.funnel) {
    const fields = Object.keys(event[2]).sort();
    assert.deepEqual(fields, ["page", "selection_engine"]);
    const payload = JSON.stringify(event);
    for (const forbidden of ["result", "health", "email", "url", "query", "no_buy", "answer"]) {
      assert.equal(payload.includes(forbidden), false);
    }
  }
});

test("legacy informational no-buy anchor is start only until explicit source marker exists", () => {
  const h = harness();
  h.decide({type:"no_buy", confirmed:false});
  assert.deepEqual(h.funnel.map(x => x[1]), ["advisor_start"]);
  h.decide({type:"no_buy", confirmed:true});
  assert.deepEqual(h.funnel.map(x => x[1]), ["advisor_start", "advisor_complete"]);
  assert.equal(h.calls.length, 0);
});

test("first direct real merchant click starts and completes before outbound; repeat only click", () => {
  const h = harness();
  h.click();
  h.click();
  assert.equal(h.calls.length, 2);
  assert.deepEqual(h.funnel.map(x => x[1]), ["advisor_start", "advisor_complete"]);
  assert.equal(h.funnel[0][2].selection_engine, "creatine");
});

test("denied consent and fake or injected decisions create no funnel observations", () => {
  for (const opts of [{consent:false}, {bridge:false}, {page:"/not-an-advisor/"}]) {
    const h = harness(opts);
    h.decide({type:"nav"});
    h.decide({type:"no_buy"});
    h.click();
    assert.equal(h.funnel.length, 0);
  }
  const h = harness();
  h.decide({trusted:false});
  h.decide({type:"nav", href:"#unapproved"});
  h.decide({type:"no_buy", href:"#xfit-offers"});
  h.decide({type:"no_buy", googleAnnotation:true});
  assert.equal(h.funnel.length, 0);
  // The next actual permitted choice is counted exactly once.
  h.decide({type:"no_buy"});
  assert.deepEqual(h.funnel.map(x => x[1]), ["advisor_start", "advisor_complete"]);
});

test("consent withdrawal is checked for each action and never replays denied actions", () => {
  const h = harness();
  h.root.getWccConsent = () => ({categories:{analytics:false}});
  h.decide({type:"no_buy"});
  assert.equal(h.funnel.length, 0);
  h.root.getWccConsent = () => ({categories:{analytics:true}});
  h.decide({type:"nav"});
  assert.deepEqual(h.funnel.map(x => x[1]), ["advisor_start"]);
  h.root.getWccConsent = () => ({categories:{analytics:false}});
  h.decide({type:"no_buy"});
  assert.deepEqual(h.funnel.map(x => x[1]), ["advisor_start"]);
  h.root.getWccConsent = () => ({categories:{analytics:true}});
  h.decide({type:"no_buy"});
  assert.deepEqual(h.funnel.map(x => x[1]), ["advisor_start", "advisor_complete"]);
  h.root.getWccConsent = () => ({categories:{analytics:false}});
  h.click();
  assert.equal(h.calls.length, 0);
  assert.equal(h.funnel.length, 2);
});

test("valid real click after explicit consent emits only four whitelisted fields", () => {
  const h = harness();
  h.click();
  assert.equal(h.calls.length, 1);
  const [kind, name, params] = h.calls[0];
  assert.equal(kind, "event");
  assert.equal(name, "affiliate_outbound_click");
  assert.deepEqual(JSON.parse(JSON.stringify(params)), {
    page: "xfit-os-kreatin-poradce",
    selection_engine: "creatine",
    partner: "namaximum",
    product_id: 392,
  });
  const serialized = JSON.stringify(params);
  for (const forbidden of ["http", "a_aid", "a_bid", "email", "answer", "health"]) {
    assert.equal(serialized.includes(forbidden), false);
  }
});

test("hero one-click offer records the same consented product event as its card", () => {
  const h = harness();
  h.click({hero:true});
  h.click({hero:false});
  assert.equal(h.calls.length, 2);
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls[0])),
                   JSON.parse(JSON.stringify(h.calls[1])));
  assert.equal(h.calls[0][2].product_id, 392);

  const denied = harness({consent:false});
  denied.click({hero:true});
  assert.equal(denied.calls.length, 0);

  const spoof = harness();
  spoof.click({hero:true, id:"393"});
  spoof.click({hero:true, href:URL_OK.replace("utm_medium=affiliate", "utm_medium=cpc")});
  assert.equal(spoof.calls.length, 0);
});

test("no CMP bridge, denied consent, missing gtag => no event", () => {
  for (const opts of [{bridge:false}, {consent:false}]) {
    const h = harness(opts);
    h.click();
    assert.equal(h.calls.length, 0);
  }
  const h = harness();
  h.root.gtag = undefined;
  h.click();
  assert.equal(h.calls.length, 0);
});

test("preexisting permissive bridge cannot bypass denied or missing WebToffee consent", () => {
  const h = harness();
  h.root.xfitGetAnalyticsConsent = () => true;
  h.root.getWccConsent = () => ({categories:{analytics:false}});
  h.click();
  assert.equal(h.calls.length, 0);

  h.root.getWccConsent = undefined;
  h.click();
  assert.equal(h.calls.length, 0);

  h.root.getWccConsent = () => ({categories:{analytics:"true"}});
  h.click();
  assert.equal(h.calls.length, 0);

  h.root.getWccConsent = () => {throw new Error("Consent provider unavailable");};
  h.click();
  assert.equal(h.calls.length, 0);

  // Explicit true must be checked anew for each subsequent click.
  h.root.getWccConsent = () => ({categories:{analytics:true}});
  h.click();
  assert.equal(h.calls.length, 1);
  h.root.getWccConsent = () => ({categories:{analytics:false}});
  h.click();
  assert.equal(h.calls.length, 1);
});

test("only trusted active links from controlled card and page are counted", () => {
  for (const opts of [
    {id:"0"}, {id:"0392"}, {id:"392x"}, {id:"2147483648"},
    {engine:"whey"}, {rel:"nofollow"}, {trusted:false}, {card:false},
    {href:"https://evil.example/p?utm_medium=affiliate&a_aid=TESTA&a_bid=TESTB"},
    {href:"https://www.namaximum.cz/"}, {href:"javascript:alert(1)"},
    {href:"https://www.namaximum.cz/p/creatine?utm_medium=cpc&a_aid=TESTA&a_bid=TESTB"},
  ]) {
    const h = harness();
    h.click(opts);
    assert.equal(h.calls.length, 0, "unsafe click must not be measured");
  }
  const wrongPage = harness({page:"/privacy/"});
  wrongPage.click();
  assert.equal(wrongPage.calls.length, 0);
});

test("per-product events require one exact merchant variant matching catalog metadata", () => {
  const badUrls = [
    URL_OK.replace("variant=392", "variant=393"),
    URL_OK.replace("variant=392&", ""),
    URL_OK.replace("variant=392", "variant=0392"),
    URL_OK.replace("variant=392", "variant=392&variant=392"),
    URL_OK.replace("variant=392", "variant=392&variant=393"),
    URL_OK.replace("variant=392", "variant=392%2C393"),
    URL_OK.replace("variant=392", "variant=392abc"),
    URL_OK.replace("variant=392", "variant="),
  ];
  for (const href of badUrls) {
    const h = harness();
    h.click({href});
    assert.equal(h.calls.length, 0, "bad merchant product mapping must remain unmeasured");
  }
  // Tampering with *only* an HTML data attribute must not misattribute a
  // legitimate offer to a different catalog product.
  const h = harness();
  h.click({id:"393"});
  assert.equal(h.calls.length, 0);
});

test("consented variant-bound whey click uses only approved IDs and fields", () => {
  const h = harness({page:"/xfit-os-syrovatkovy-protein-porovnani/"});
  h.click({engine:"whey", id:"483", href:URL_OK.replace("variant=392", "variant=483")});
  assert.equal(h.calls.length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls[0][2])), {
    page:"xfit-os-syrovatkovy-protein-porovnani",
    selection_engine:"whey",
    partner:"namaximum",
    product_id:483
  });
  h.click({engine:"whey", id:"483", href:URL_OK});
  assert.equal(h.calls.length, 1);
});

test("landing-page query and anchor are not sent with click event", () => {
  const h = harness();
  h.root.location.search = "?utm_source=organic&utm_campaign=PRIVATE";
  h.root.location.hash = "#xfit-offers";
  h.click();
  assert.equal(h.calls.length, 1);
  const params = JSON.stringify(h.calls[0][2]);
  assert.equal(params.includes("utm_source"), false);
  assert.equal(params.includes("PRIVATE"), false);
  assert.equal(params.includes("#"), false);
  assert.equal(h.calls[0][2].page, "xfit-os-kreatin-poradce");
});

test("broken gtag transport cannot cancel a product click", () => {
  const h = harness();
  h.root.gtag = () => { throw new Error("analytics transport failed"); };
  assert.doesNotThrow(() => h.click());
});

test("whey events are attributed to the correct advisor, not a purchase", () => {
  const h = harness({page:"/xfit-os-syrovatkovy-protein-porovnani/"});
  h.click({engine:"whey", id:"483", href:URL_OK.replace("variant=392", "variant=483")});
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0][1], "affiliate_outbound_click");
  assert.equal(h.calls[0][2].product_id, 483);
});
