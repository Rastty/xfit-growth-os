/* XFIT's bridge to WebToffee GDPR Cookie Consent 3.x.
 *
 * The plugin's documented getWccConsent() returns stored category grants.
 * This bridge NEVER infers consent from cookie strings, page content, banner
 * visibility, Google Consent Mode or plugin installation. On every click, the
 * outbound adapter calls xfitGetAnalyticsConsent() again to see current state.
 * Missing API, invalid state or errors are DENIED.
 */
(function (root) {
  "use strict";
  if (!root || typeof root.xfitGetAnalyticsConsent !== "undefined") {
    // Do not silently replace an existing site's consent bridge.
    return;
  }

  root.xfitGetAnalyticsConsent = function () {
    if (typeof root.getWccConsent !== "function") return false;
    try {
      const state = root.getWccConsent();
      return Boolean(
        state &&
        typeof state === "object" &&
        state.categories &&
        typeof state.categories === "object" &&
        state.categories.analytics === true
      );
    } catch (_error) {
      return false;
    }
  };
})(window);
