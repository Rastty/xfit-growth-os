"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {navigatePublicGet, transientNavigationError} = require("../scripts/xfit_mobile_navigation.cjs");

const resp = code => ({status: () => code});
const url = "https://xfit.cz/xfit-os-kreatin-nebo-protein/";

test("a transient WEDOS 503 is retried as GET, then public 200 accepted", async () => {
  const calls = [];
  let n = 0;
  const page = {goto: async (dest, opts) => {
    calls.push([dest, opts]);
    return ++n === 1 ? resp(503) : resp(200);
  }};
  const waits = [];
  const result = await navigatePublicGet(page, url, {
    pause: async ms => waits.push(ms)
  });
  assert.equal(result.response.status(), 200);
  assert.equal(result.retries, 1);
  assert.deepEqual(waits, [1000]);
  assert.equal(calls.length, 2);
  assert.equal(calls[0][0], url);
  assert.equal(calls[0][1].waitUntil, "domcontentloaded");
});

test("a timeout/connection reset is retried with a bounded limit", async () => {
  let count = 0;
  const page = {goto: async () => {
    count++;
    if (count < 3) throw new Error("page.goto: net::ERR_CONNECTION_RESET");
    return resp(200);
  }};
  const waits = [];
  const result = await navigatePublicGet(page, url, {
    pause: async ms => waits.push(ms)
  });
  assert.equal(result.response.status(), 200);
  assert.equal(result.retries, 2);
  assert.deepEqual(waits, [1000, 2000]);
  assert.equal(count, 3);
});

test("broken page is never hidden: 404 and persistent 500 fail on first status", async () => {
  for (const status of [404, 500, 403]) {
    let attempts = 0;
    const page = {goto: async () => {attempts++; return resp(status);}};
    const result = await navigatePublicGet(page, url, {
      pause: async () => {throw new Error("Must not retry permanent HTTP status");}
    });
    assert.equal(result.response.status(), status);
    assert.equal(result.retries, 0);
    assert.equal(attempts, 1);
  }
});

test("persistent 503 returns failed HTTP status after 3 tries", async () => {
  let tries = 0;
  const page = {goto: async () => {tries++; return resp(503);}};
  const result = await navigatePublicGet(page, url, {pause: async () => {}});
  assert.equal(result.response.status(), 503);
  assert.equal(result.retries, 2);
  assert.equal(tries, 3);
});

test("permanent SSL failure and unexpected code errors do not retry", async () => {
  for (const message of ["net::ERR_CERT_AUTHORITY_INVALID", "JavaScript crashed"]) {
    let attempts = 0;
    const page = {goto: async () => {attempts++; throw new Error(message);}};
    await assert.rejects(
      navigatePublicGet(page, url, {
        pause: async () => {throw new Error("Unexpected retry");}
      }),
      err => err.message === message
    );
    assert.equal(attempts, 1);
  }
});

test("negative, unlimited or fractional retry counts are rejected", async () => {
  const page = {goto: async () => resp(200)};
  for (const number of [-1,0,4,1.5]) {
    await assert.rejects(
      navigatePublicGet(page, url, {maxAttempts:number}),
      TypeError
    );
  }
  assert.equal(transientNavigationError({name:"TimeoutError"}), true);
  assert.equal(transientNavigationError({message:"net::ERR_CERT_AUTHORITY_INVALID"}), false);
});
