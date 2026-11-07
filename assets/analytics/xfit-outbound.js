/* XFIT outbound CTA analytics adapter (opt-in integration only).
 * Deploy as an externally enqueued first-party script after the site's real
 * consent manager and GA4 are verified. This file does NOT self-create consent.
 * No cookies, session IDs, URL params or health/quiz answers are collected here.
 */
(function (root) {
  "use strict";

  const ENGINES = Object.freeze({
    "/xfit-os-kreatin-poradce/": "creatine",
    "/xfit-os-syrovatkovy-protein-porovnani/": "whey"
  });

  function readApprovedClick(event) {
    if (!event || event.isTrusted !== true || !event.target ||
        typeof event.target.closest !== "function") return null;
    const location = root.location;
    if (!location || location.protocol !== "https:" ||
        !["xfit.cz", "www.xfit.cz"].includes(location.hostname)) return null;
    const engine = ENGINES[location.pathname];
    if (!engine || location.search || location.hash) return null;

    const link = event.target.closest("a[data-xfit-product-id]");
    if (!link || typeof link.closest !== "function" ||
        !link.closest("article.xfit-product-card")) return null;
    const data = link.dataset || {};
    if (data.xfitEngine !== engine || data.xfitPartner !== "namaximum" ||
        typeof data.xfitProductId !== "string" ||
        !/^[1-9][0-9]{0,9}$/.test(data.xfitProductId)) return null;

    const product = Number(data.xfitProductId);
    if (!Number.isSafeInteger(product) || product > 2147483647) return null;
    const rel = (link.getAttribute("rel") || "").toLowerCase().split(/\s+/);
    if (!rel.includes("sponsored")) return null;

    let destination;
    try {
      destination = new URL(link.getAttribute("href"), location.href);
    } catch (_error) { return null; }
    if (destination.protocol !== "https:" ||
        !["namaximum.cz", "www.namaximum.cz"].includes(destination.hostname) ||
        destination.username || destination.password || destination.port ||
        destination.pathname === "/") return null;

    const qs = destination.searchParams;
    if (qs.get("utm_medium") !== "affiliate" ||
        qs.get("utm_campaign") !== "affial.com" ||
        qs.get("utm_source") !== "pap" ||
        !qs.get("a_aid") || !qs.get("a_bid")) return null;

    return {
      page: location.pathname.slice(1, -1),
      selection_engine: engine,
      partner: "namaximum",
      product_id: product
    };
  }

  function onClick(event) {
    // Must be supplied by a verified CMP integration. Missing/unknown consent
    // is denial; never infer consent from a cookie, button or banner.
    if (typeof root.xfitGetAnalyticsConsent !== "function" ||
        typeof root.gtag !== "function") return;
    let granted = false;
    try { granted = root.xfitGetAnalyticsConsent() === true; }
    catch (_error) { return; }
    if (!granted) return;
    const data = readApprovedClick(event);
    if (!data) return;
    // No transport retry, navigation interception, health data or affiliate
    // destination URL. This event is NOT a purchase or earned commission.
    root.gtag("event", "affiliate_outbound_click", data);
  }

  if (root.document && typeof root.document.addEventListener === "function") {
    root.document.addEventListener("click", onClick, true);
  }
})(window);
