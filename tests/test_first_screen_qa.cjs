"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {summarizeFirstScreen} = require("../scripts/xfit_first_screen_qa.cjs");

test("reports substantial top ad geometry and bottom cookie banner without URLs", () => {
  const result = summarizeFirstScreen({
    viewport: {width: 375, height: 812},
    googleAdFrameRects: [
      {left: 0, top: 0, right: 375, bottom: 190},
      {left: 0, top: 1500, right: 300, bottom: 1800},
    ],
    cookieBannerRect: {left: 0, top: 720, right: 375, bottom: 812},
    h1TopPx: 830,
  });
  assert.equal(result.google_ad_frames_intersecting_viewport, 1);
  assert.equal(result.top_edge_google_ad_frame_count, 1);
  assert.equal(result.top_edge_google_ad_max_height_px, 190);
  assert.equal(result.top_edge_google_ad_viewport_height_pct, 23);
  assert.equal(result.bottom_cookie_banner_height_px, 92);
  assert.deepEqual(result.warnings, [
    "TALL_TOP_EDGE_GOOGLE_AD_FRAME",
    "TALL_BOTTOM_COOKIE_BANNER",
    "H1_BELOW_INITIAL_VIEWPORT",
  ]);
  assert.equal(JSON.stringify(result).includes("https://"), false);
});

test("never treats off-screen and zero-area frames as visible ads", () => {
  const result = summarizeFirstScreen({
    viewport: {width: 1363, height: 936},
    googleAdFrameRects: [
      {left: 0, top: 0, right: 0, bottom: 0},
      {left: 900, top: 1000, right: 1220, bottom: 1250},
      {left: 100, top: 100, right: 420, bottom: 350},
    ],
    cookieBannerRect: null,
    h1TopPx: 500,
  });
  assert.equal(result.google_ad_frames_intersecting_viewport, 1);
  assert.equal(result.top_edge_google_ad_frame_count, 0);
  assert.equal(result.bottom_cookie_banner_height_px, 0);
  assert.deepEqual(result.warnings, []);
  assert.equal(result.evidence_scope,
    "ONE_INITIAL_VIEWPORT_GEOMETRY_NOT_AD_IMPRESSIONS_OR_CONSENT");
});

test("rejects invalid viewport, clips partially visible frames", () => {
  assert.throws(() => summarizeFirstScreen({viewport: {width: 0, height: 812}}), TypeError);
  const result = summarizeFirstScreen({
    viewport: {width: 375, height: 812},
    googleAdFrameRects: [{left: -20, top: -50, right: 395, bottom: 80}],
    cookieBannerRect: {left: 0, top: 900, right: 375, bottom: 1000},
  });
  assert.equal(result.top_edge_google_ad_max_height_px, 80);
  assert.equal(result.h1_initial_top_px, null);
});
