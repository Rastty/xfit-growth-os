/* XFIT consent-gated advisor funnel and outbound analytics (opt-in integration only).
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
    // A verified advisor remains the same page when reached with marketing
    // parameters or an anchor. Never transmit those parameters to analytics.
    if (!engine) return null;

    const link = event.target.closest("a[data-xfit-product-id]");
    if (!link || typeof link.closest !== "function") return null;
    // A first-screen purchase CTA must be the same independently verified
    // offer as its lower product card; both live inside controlled contexts.
    const onCard = !!link.closest("article.xfit-product-card");
    const onQuickPick = link.dataset &&
      link.dataset.xfitCta === "quick-pick" &&
      !!link.closest("[data-xfit-quick-pick]") &&
      !!link.closest("section#xfit-rychly-vyber");
    if (!onCard && !onQuickPick) return null;
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

    // Live read-only affiliate audit verified 6/6 exact catalog/variant
    // matches in each advisor (run 42865679992). Bind analytics identity
    // to the *actual* merchant offer, not an independently editable data-
    // attribute. Missing, duplicate or mismatched variants remain UNKNOWN:
    // never dispatch an incorrect product-level GA4 event.
    const variants = qs.getAll("variant");
    if (variants.length !== 1 || variants[0] !== data.xfitProductId) return null;

    return {
      page: location.pathname.slice(1, -1),
      selection_engine: engine,
      partner: "namaximum",
      product_id: product
    };
  }

  // A deliberately small, observable decision boundary; no pageview is an
  // advisor start, and no quiz answer, selected option, or visitor identity is
  // put into GA4. A no-buy choice is an equally valid completion.
  const NAV_TARGETS = Object.freeze([
    "#xfit-need", "#xfit-vyber-podle-rozpoctu", "#xfit-offers"
  ]);
  let started = false;
  let completed = false;

  function readDecisionClick(event) {
    if (!event || event.isTrusted !== true || !event.target ||
        typeof event.target.closest !== "function") return null;
    const anchor = event.target.closest("a");
    if (!anchor || typeof anchor.closest !== "function") return null;
    if (anchor.classList && anchor.classList.contains("google-anno")) return null;
    if (typeof anchor.getAttribute !== "function" ||
        typeof anchor.hasAttribute !== "function" ||
        anchor.hasAttribute("onclick") ||
        anchor.getAttribute("target") !== null) return null;
    const href = anchor.getAttribute("href");
    if (!NAV_TARGETS.includes(href)) return null;
    if (anchor.closest('nav[aria-label="Rychlá navigace poradcem"]')) {
      return "start";
    }
    if (href === "#xfit-need" &&
        anchor.closest('[data-xfit-quick-pick="no-buy"]') &&
        anchor.closest("section#xfit-rychly-vyber")) {
      // The old "zjistit, zda..." CTA merely begins reading. Only an
      // explicitly marked "today I choose not to buy" CTA is a completion.
      // This remains safe while the WordPress HTML has not been refreshed.
      return anchor.getAttribute("data-xfit-funnel-complete") === "no-buy"
        ? "no_buy" : "start";
    }
    return null;
  }

  function emit(eventName, params) {
    try {
      root.gtag("event", eventName, params);
      return true;
    } catch (_error) {
      // Analytics failure never blocks navigation or user choice.
      return false;
    }
  }

  function onClick(event) {
    // Must be supplied by a verified CMP integration. Missing/unknown consent
    // is denial; never infer consent from a cookie, button or banner.
    if (typeof root.xfitGetAnalyticsConsent !== "function" ||
        typeof root.getWccConsent !== "function" ||
        typeof root.gtag !== "function") return;
    let granted = false;
    try {
      // The public bridge symbol can already exist on the site. It is not
      // sufficient by itself: verify the documented WebToffee 3.x stored
      // analytics category directly at click time, including after revoke.
      const state = root.getWccConsent();
      granted = root.xfitGetAnalyticsConsent() === true &&
        state && typeof state === "object" &&
        state.categories && typeof state.categories === "object" &&
        state.categories.analytics === true;
    } catch (_error) { return; }
    if (!granted) return;
    // Always re-check current page identity at event time; consent may be
    // granted or withdrawn between actions without refreshing the page.
    const location = root.location;
    const engine = location && location.protocol === "https:" &&
      ["xfit.cz", "www.xfit.cz"].includes(location.hostname) &&
      ENGINES[location.pathname];
    if (!engine) return;
    const data = readApprovedClick(event);
    const decision = readDecisionClick(event);
    if (!data && !decision) return;
    const context = {
      page: location.pathname.slice(1, -1),
      selection_engine: engine
    };
    if (!started) started = emit("advisor_start", context);
    if (started && !completed && (data || decision === "no_buy")) {
      completed = emit("advisor_complete", context);
    }
    // Never dedupe genuine affiliate clicks: each trusted merchant action
    // is an observed click, not a buyer or completed order. The adapter
    // never attempts navigation interception or a network retry.
    if (data) emit("affiliate_outbound_click", data);
  }

  if (root.document && typeof root.document.addEventListener === "function") {
    root.document.addEventListener("click", onClick, true);
  }
})(window);
