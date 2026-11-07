"use strict";

// Browser navigation is a public GET, safe to retry on transient failures.
// Never retry consent actions, product clicks, POSTs or HTTP 404.
const RETRY_HTTP = new Set([429, 502, 503, 504]);
const RETRY_NETWORK = (
  /(?:net::ERR_(?:CONNECTION_RESET|CONNECTION_CLOSED|EMPTY_RESPONSE|NETWORK_CHANGED|TIMED_OUT|HTTP2_PROTOCOL_ERROR|ABORTED)|Navigation timeout|TimeoutError)/i
);

function transientNavigationError(error) {
  const name = typeof error?.name === "string" ? error.name : "";
  const message = typeof error?.message === "string" ? error.message : "";
  return name === "TimeoutError" || RETRY_NETWORK.test(message);
}

async function navigatePublicGet(page, url, options = {}) {
  const maxAttempts = options.maxAttempts ?? 3;
  const timeout = options.timeout ?? 60000;
  const pause = options.pause ?? (
    async ms => new Promise(resolve => setTimeout(resolve, ms))
  );
  if (!Number.isInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 3) {
    throw new TypeError("Attempts must be 1..3");
  }
  let retries = 0;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const response = await page.goto(url, {waitUntil:"domcontentloaded",timeout});
      const status = response?.status();
      if (RETRY_HTTP.has(status) && attempt < maxAttempts) {
        retries++;
        await pause(attempt * 1000);
        continue;
      }
      // Non-retryable 4xx/5xx are reported by the caller as failures.
      return {response, retries};
    } catch (error) {
      if (attempt === maxAttempts || !transientNavigationError(error)) {
        throw error;
      }
      retries++;
      await pause(attempt * 1000);
    }
  }
  throw new Error("Navigation retry exhausted");
}

module.exports = {navigatePublicGet, transientNavigationError};
