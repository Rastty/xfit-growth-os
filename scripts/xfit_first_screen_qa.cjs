"use strict";

// Aggregate, read-only geometry for the *initial* viewport. Ad placement is
// dynamic: a missing frame in one run does not prove ads are disabled. Never
// log iframe URLs, publisher IDs, cookies, visitor data or affiliate links.
function clipRect(rect, width, height) {
  if (!rect || [rect.left, rect.top, rect.right, rect.bottom]
      .some(value => typeof value !== "number" || !Number.isFinite(value))) {
    return null;
  }
  const left = Math.max(0, rect.left);
  const top = Math.max(0, rect.top);
  const right = Math.min(width, rect.right);
  const bottom = Math.min(height, rect.bottom);
  if (right <= left || bottom <= top) return null;
  return {left, top, right, bottom, width: right - left, height: bottom - top};
}

function summarizeFirstScreen(observed) {
  const width = observed?.viewport?.width;
  const height = observed?.viewport?.height;
  if (!Number.isInteger(width) || !Number.isInteger(height) ||
      width < 240 || width > 5000 || height < 300 || height > 5000) {
    throw new TypeError("Unexpected viewport dimensions");
  }
  const frames = (Array.isArray(observed.googleAdFrameRects)
    ? observed.googleAdFrameRects.slice(0, 30) : [])
    .map(rect => clipRect(rect, width, height)).filter(Boolean);
  // Frame reaching the upper screen edge across at least half the viewport.
  // Geometry only: this does not establish an ad impression or click.
  const topEdge = frames.filter(rect => rect.top <= 4 &&
    rect.width >= width / 2 && rect.height >= 48);
  const maxTopHeight = Math.max(0, ...topEdge.map(rect => rect.height));
  const cookie = clipRect(observed.cookieBannerRect, width, height);
  const cookieHeight = cookie && cookie.bottom >= height - 4 &&
    cookie.width >= width / 2 ? cookie.height : 0;
  const h1Top = Number.isFinite(observed.h1TopPx)
    ? Math.round(observed.h1TopPx) : null;
  const percent = value => Math.round(value / height * 100);
  const warnings = [];
  if (maxTopHeight >= height * .15) warnings.push("TALL_TOP_EDGE_GOOGLE_AD_FRAME");
  if (cookieHeight >= height * .10) warnings.push("TALL_BOTTOM_COOKIE_BANNER");
  if (h1Top !== null && h1Top >= height) warnings.push("H1_BELOW_INITIAL_VIEWPORT");
  return {
    viewport_width_px: width,
    viewport_height_px: height,
    google_ad_frames_intersecting_viewport: frames.length,
    top_edge_google_ad_frame_count: topEdge.length,
    top_edge_google_ad_max_height_px: Math.round(maxTopHeight),
    top_edge_google_ad_viewport_height_pct: percent(maxTopHeight),
    bottom_cookie_banner_height_px: Math.round(cookieHeight),
    bottom_cookie_banner_viewport_height_pct: percent(cookieHeight),
    h1_initial_top_px: h1Top,
    warnings,
    evidence_scope: "ONE_INITIAL_VIEWPORT_GEOMETRY_NOT_AD_IMPRESSIONS_OR_CONSENT",
  };
}

module.exports = {summarizeFirstScreen};
