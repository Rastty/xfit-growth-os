"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const BRIDGE = fs.readFileSync(
  path.join(__dirname, "..", "assets", "analytics", "xfit-webtoffee-bridge.js"), "utf8");
const OUTBOUND = fs.readFileSync(
  path.join(__dirname, "..", "assets", "analytics", "xfit-outbound.js"), "utf8");
const OFFER = "https://www.namaximum.cz/p/creatine?variant=392" +
  "&utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap" +
  "&a_aid=SIMULATED_AID&a_bid=SIMULATED_BID";

function mount(initialState, {existingBridge} = {}) {
  let state = initialState;
  const events = [];
  const callbacks = {};
  const root = {
    document: {addEventListener: (kind, fn) => { callbacks[kind] = fn; }},
    location: {
      protocol:"https:", hostname:"xfit.cz", pathname:"/xfit-os-kreatin-poradce/",
      href:"https://xfit.cz/xfit-os-kreatin-poradce/"
    },
    getWccConsent: () => state,
    gtag: (...args) => events.push(args),
  };
  if (existingBridge) root.xfitGetAnalyticsConsent = existingBridge;
  vm.runInNewContext(BRIDGE, {window:root});
  vm.runInNewContext(OUTBOUND, {window:root, URL});
  return {
    root, events, setConsent: newState => { state = newState; },
    click({trusted = true, id = "392", href = OFFER} = {}) {
      const link = {
        dataset: {xfitProductId:id, xfitEngine:"creatine", xfitPartner:"namaximum"},
        getAttribute: name => ({rel:"sponsored nofollow", href})[name] || null,
        closest: selector => selector === "article.xfit-product-card" ? {} : null,
      };
      callbacks.click({
        isTrusted:trusted,
        target: {
          closest: selector => selector === "a[data-xfit-product-id]" ? link : null,
        }
      });
    },
  };
}

test("actual WebToffee bridge and outbound adapter follow denial, grant and revoke", () => {
  const h = mount({categories:{analytics:false}});
  h.click();
  assert.equal(h.events.length, 0);
  h.setConsent({categories:{analytics:true}});
  h.click();
  assert.equal(h.events.length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(h.events[0])), [
    "event", "affiliate_outbound_click", {
      page:"xfit-os-kreatin-poradce", selection_engine:"creatine",
      partner:"namaximum", product_id:392,
    }
  ]);
  h.setConsent({categories:{analytics:false}});
  h.click();
  assert.equal(h.events.length, 1);
  h.setConsent({categories:{analytics:true}});
  h.click({id:"393"});
  assert.equal(h.events.length, 1, "a wrong merchant variant must not be attributed");
  h.click({trusted:false});
  assert.equal(h.events.length, 1, "synthetic click must not be attributed");
  for (const secret of ["SIMULATED_AID", "SIMULATED_BID", "https://", "health", "email"]) {
    assert.equal(JSON.stringify(h.events).includes(secret), false);
  }
});

test("permissive preexisting bridge does not bypass actual WebToffee denial", () => {
  const h = mount({categories:{analytics:false}}, {existingBridge:() => true});
  h.click();
  assert.equal(h.events.length, 0);
  h.setConsent({categories:{analytics:true}});
  h.click();
  assert.equal(h.events.length, 1);
  h.setConsent({categories:{analytics:"true"}});
  h.click();
  assert.equal(h.events.length, 1);
  h.root.getWccConsent = undefined;
  h.click();
  assert.equal(h.events.length, 1);
});

test("missing WebToffee API or throwing provider can never create a click event", () => {
  const h = mount(null);
  h.click();
  assert.equal(h.events.length, 0);
  h.root.getWccConsent = () => { throw new Error("Private state inaccessible"); };
  h.click();
  assert.equal(h.events.length, 0);
  h.root.getWccConsent = () => ({categories:{analytics:true}});
  h.click();
  assert.equal(h.events.length, 1);
});
