"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const SCRIPT = fs.readFileSync(path.join(
  __dirname, "..", "assets", "analytics", "xfit-webtoffee-bridge.js"
), "utf8");

function mount(options = {}) {
  const state = {current: options.initial};
  const root = {};
  if (options.api === true) {
    root.getWccConsent = () => {
      if (state.current === "throws") throw new Error("ignored private failure");
      return state.current;
    };
  }
  vm.runInNewContext(SCRIPT, {window: root});
  return {state, root, consent: () => root.xfitGetAnalyticsConsent()};
}

test("no WebToffee API denies analytics even if Google tag is present", () => {
  const setup = mount({initial: {categories:{analytics:true}}});
  setup.root.gtag = () => {};
  assert.equal(setup.consent(), false);
});

test("explicit stored WebToffee analytics category true grants, and only boolean true", () => {
  for (const state of [null, undefined, {}, {categories:null},
                       {categories:{}}, {categories:{analytics:false}},
                       {categories:{analytics:1}}, {categories:{analytics:"true"}}]) {
    const setup = mount({api:true, initial:state});
    assert.equal(setup.consent(), false, "unknown state must not grant consent");
  }
  const setup = mount({api:true, initial:{categories:{analytics:true}}});
  assert.equal(setup.consent(), true);
});

test("changes and revocation take effect at each click without stale consent cache", () => {
  const setup = mount({api:true, initial:{categories:{analytics:false}}});
  assert.equal(setup.consent(), false);
  setup.state.current = {categories:{analytics:true}};
  assert.equal(setup.consent(), true);
  setup.state.current = {categories:{analytics:false}};
  assert.equal(setup.consent(), false);
  setup.state.current = "throws";
  assert.equal(setup.consent(), false);
});

test("WebToffee API loading after bridge still works at click time", () => {
  const setup = mount();
  assert.equal(setup.consent(), false);
  setup.root.getWccConsent = () => ({categories:{analytics:true}});
  assert.equal(setup.consent(), true);
});
