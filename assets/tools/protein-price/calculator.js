/* XFIT protein-price comparison — deterministic, offline and privacy-preserving.
 * No cookies, storage, analytics, network requests or third-party dependencies.
 * Include as a deferred external script only after a reviewed hosting deployment.
 */
(function (root) {
  "use strict";

  function parseHundredths(value, maximum, allowZero) {
    if (typeof value !== "string") return null;
    const raw = value.trim();
    if (!/^(?:\d{1,7})(?:[,.]\d{1,2})?$/.test(raw)) return null;
    const chunks = raw.replace(",", ".").split(".");
    const result = BigInt(chunks[0]) * 100n + BigInt((chunks[1] || "").padEnd(2, "0"));
    if ((!allowZero && result === 0n) || result > BigInt(maximum) * 100n) return null;
    return result;
  }

  function parsePack(raw) {
    if (!raw || typeof raw !== "object") return null;
    const price = parseHundredths(raw.price, 1000000, false);
    const protein = parseHundredths(raw.protein, 100, false);
    const massText = typeof raw.mass === "string" ? raw.mass.trim() : "";
    const mass = /^\d{1,5}$/.test(massText) ? Number(massText) : 0;
    const delivery = raw.delivery === "" ? null : parseHundredths(raw.delivery, 100000, true);
    if (price === null || protein === null || !Number.isSafeInteger(mass) ||
        mass < 1 || mass > 10000 || (raw.delivery !== "" && delivery === null)) return null;
    const total = price + (delivery || 0n);
    const divisor = BigInt(mass) * protein;
    return {
      totalCents: total,
      proteinHundredths: BigInt(mass) * protein / 100n,
      // Round to the nearest 0.01 CZK, half up. Integer arithmetic prevents
      // binary floating-point errors on exact tie values.
      per100Cents: (total * 1000000n + divisor / 2n) / divisor,
      per25Cents: (total * 250000n + divisor / 2n) / divisor,
      deliveryIncluded: delivery !== null
    };
  }

  function compare(a, b) {
    const first = parsePack(a);
    if (!first) return { error: "Zkontrolujte cenu, hmotnost a údaj o bílkovinách u balení A." };
    const secondEmpty = [b.price, b.mass, b.protein, b.delivery].every(x => x === "");
    const second = secondEmpty ? null : parsePack(b);
    if (!secondEmpty && !second) {
      return { error: "U balení B doplňte všechny tři povinné údaje nebo jej nechte prázdné." };
    }
    const shippingComparison = !second ? "single" :
      first.deliveryIncluded === second.deliveryIncluded ?
        (first.deliveryIncluded ? "included" : "excluded") : "incomplete";
    return { first, second, shippingComparison };
  }

  function asCzk(cents) {
    const whole = cents / 100n;
    const fraction = String(cents % 100n).padStart(2, "0");
    return whole.toString().replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0") + "," + fraction + " Kč";
  }

  function asGrams(hundredths) {
    return (hundredths / 100n).toString() + "," + String(hundredths % 100n).padStart(2, "0") + " g";
  }

  function priceVerdict(result) {
    if (!result || !result.first || !result.second) return "";
    if (result.shippingComparison === "incomplete") {
      return "Nelze férově určit levnější balení: doprava je zadaná jen u jednoho. " +
        "Vyplňte dopravu u obou balení (i 0 Kč pro dopravu zdarma), " +
        "nebo ji z obou polí vymažte. Uvedené jednotkové ceny teď nejsou přímo srovnatelné.";
    }
    // Compare exact fractions, not independently rounded display prices.
    const a = result.first;
    const b = result.second;
    const diff = a.totalCents * b.proteinHundredths - b.totalCents * a.proteinHundredths;
    return (result.shippingComparison === "excluded" ?
      "Porovnání nezahrnuje dopravu. " : "Doprava je zahrnuta u obou balení. ") +
      (diff === 0n
        ? "Při stejném přepočtu vycházejí obě balení cenově nastejno."
        : "Nižší cenu za stejné množství deklarovaných bílkovin má balení " +
          (diff < 0n ? "A" : "B") + ". Neznamená to automaticky lepší složení.");
  }

  function text(element, value) {
    element.textContent = value;
  }

  function init(section) {
    if (!section || section.dataset.xfitReady === "1") return;
    const form = section.querySelector("form");
    const output = section.querySelector('[data-role="result"]');
    if (!form || !output) return;
    section.dataset.xfitReady = "1";
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      const fields = form.elements;
      const pack = name => ({
        price: fields[name + "-price"].value.trim(),
        mass: fields[name + "-mass"].value.trim(),
        protein: fields[name + "-protein"].value.trim(),
        delivery: fields[name + "-delivery"].value.trim()
      });
      const result = compare(pack("a"), pack("b"));
      output.replaceChildren();
      if (result.error) {
        output.setAttribute("data-state", "error");
        const warning = document.createElement("p");
        text(warning, result.error);
        output.append(warning);
        return;
      }
      output.setAttribute("data-state", "ok");
      const lead = document.createElement("p");
      text(lead, "Přepočet podle vámi zadaných údajů z etikety:");
      output.append(lead);
      for (const [label, item] of [["A", result.first], ["B", result.second]]) {
        if (!item) continue;
        const p = document.createElement("p");
        text(p, "Balení " + label + ": " + asCzk(item.per100Cents) +
          " / 100 g bílkovin; " + asCzk(item.per25Cents) +
          " / 25 g bílkovin; " + asGrams(item.proteinHundredths) +
          " bílkovin v balení.");
        output.append(p);
      }
      if (result.second) {
        const winner = document.createElement("p");
        text(winner, priceVerdict(result));
        output.append(winner);
      }
      const caveat = document.createElement("p");
      text(caveat, "Doprava je započtena jen tam, kde jste vyplnili její cenu. " +
        "Porovnáváte jedno balení z každé nabídky, nikoli laboratorně ověřenou kvalitu. " +
        "Pokud vám stačí bílkoviny z jídla, proteinový prášek kupovat nemusíte.");
      output.append(caveat);
    });
    form.addEventListener("reset", function () {
      output.replaceChildren();
      output.removeAttribute("data-state");
    });
  }

  const api = { parseHundredths, parsePack, compare, asCzk, asGrams, priceVerdict, init };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") {
    const mount = () => document.querySelectorAll('[data-xfit-tool="protein-price"]').forEach(init);
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
    else mount();
  }
})(typeof window === "undefined" ? null : window);
