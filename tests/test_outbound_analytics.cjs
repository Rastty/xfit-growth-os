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
  const listeners = {};
  const root = {
    location: {
      protocol: "https:", hostname: "xfit.cz", pathname: page,
      search: "", hash: "", href: "https://xfit.cz" + page,
    },
    document: {
      addEventListener: (type, handler) => { listeners[type] = handler; },
    },
    gtag: (...args) => calls.push(args),
  };
  if (bridge) root.xfitGetAnalyticsConsent = () => consent;
  vm.runInNewContext(SCRIPT, { window: root, URL });
  return {
    calls, root,
    click({href = URL_OK, id = "392", engine = "creatine",
           rel = "sponsored nofollow", trusted = true, card = true} = {}) {
      const link = {
        dataset: { xfitProductId: id, xfitEngine: engine, xfitPartner: "namaximum" },
        getAttribute: (name) => ({href, rel})[name] || null,
        closest: (selector) => selector === "article.xfit-product-card" && card ? {} : null,
      };
      listeners.click({
        isTrusted: trusted,
        target: { closest: (selector) =>
          selector === "a[data-xfit-product-id]" ? link : null },
      });
    },
  };
}

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
  h.click({engine:"whey", id:"483"});
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0][1], "affiliate_outbound_click");
  assert.equal(h.calls[0][2].product_id, 483);
});
