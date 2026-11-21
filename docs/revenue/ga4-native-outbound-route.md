# XFIT — existing Google Analytics outbound click path (2026-11-21)

## Goal
Get **real, consent-compliant** traffic-to-merchant evidence from the two existing
XFIT product advisers **without installing a redundant tracking plugin** if
the site's existing Google Analytics 4 tag already collects outbound clicks.

This is a conditional measurement path, not a claim that data already exists.
Do not fire test merchant clicks to manufacture signals. Do not publish affiliate
campaign IDs, per-visitor details or health/quiz choices in public reports.

## Existing evidence, separate scopes
1. [XFIT affiliate health #44884514226](https://github.com/Rastty/xfit-growth-os/actions/runs/44884514226):
   both product advisers publicly render 6 source-matching product cards + 2
   source-matching quick-pick CTAs; outgoing destinations and affiliate tracking
   are correctly attached. This confirms **HTML/link parity only**, not that
   anyone clicked or that a merchant paid.
2. [Previous read-only CMP/analytics #44765199965](https://github.com/Rastty/xfit-growth-os/actions/runs/44765199965):
   WebToffee v3 present, a generic Google tag HTML signature present,
   XFIT custom event bridge and listener absent; XFIT plugin was not installed.
   Generic Google tag fingerprint alone may be an Ads tag or GA4 tag and says
   nothing about actual consent or event receipt.
3. [This run's precise static-tag report](https://github.com/Rastty/xfit-growth-os/actions/workflows/xfit-ga4-native-outbound-getonly.yml)
   separates static G- GA4 loader/config, AW Ads loader/config and GTM container.
   It counts genuine HTML external merchant anchors but does **not** call them,
   execute page JavaScript, read cookies, collect IDs or send events.

## Native GA4 route, only if proved active by GA4 account

GA4 supports enhanced measurement's automatically collected web **`click`**
event for outbound links to a different domain. When the **correct XFIT data
stream** has the **outbound clicks** option enabled and actual analytics consent
is granted, the existing NaMaximum affiliate `<a href>` anchors can generate
click events without the unpublished XFIT plugin.

In GA4 for the XFIT stream, inspect:
- **Admin → Data streams → XFIT web stream → Enhanced measurement**:
  verify outbound clicks, not simply that a Google tag is visible in HTML.
- **Reports / Explore**: filter **Event name = `click`**, outbound=true,
  and **Link domain** = `namaximum.cz` or `www.namaximum.cz`. Break down by
  **Page path + query string** or a safe normalized `page_path` to distinguish
  `/xfit-os-kreatin-poradce/` vs
  `/xfit-os-syrovatkovy-protein-porovnani/`.
- Prefer **Link domain** over storing or reporting full `link_url`, because
  affiliate links include campaign identifiers. Avoid full visitor URLs,
  click identifiers, emails, or free-text answers.
- Treat `click` as **outbound visit intent only**, never an order or paid
  commission. GA4 reports need a trustworthy date range and comparison window.
  Empty report may mean no traffic, no consent, configuration issue or delay;
  it does not prove zero sales.
- Reconcile **approved versus paid commission** from Affial directly in the
  affiliate platform, not by multiplying `click` events by an assumed rate.

## When custom plugin is still needed

The prepackaged plugin v0.1.4 handles consent-gated
`advisor_start`/`advisor_complete`/`affiliate_outbound_click` with validated
product metadata. It is **not installed** by GitHub packaging. If native GA4
`click` works, installing the plugin is optional for a richer decision funnel,
not mandatory just to count outbound links. If both native GA4 `click` and
custom `affiliate_outbound_click` are active, **do not sum them**: one user
action may produce both. Keep one canonical metric for outbound intent.
The XFIT custom adapter is gated by WebToffee's actual analytics grant at event
time; no personal or health data should be forwarded.

## Guardrails
- A static `G-` loader/config in HTML is not proof of an actual GA4 property,
  consent or collection; a GTM container might dynamically load GA4.
- A static `AW-` Ads loader must **not** be mistaken for GA4.
- No GA4 or Affial access was granted to this read-only code; real event counts
  and commissions remain **UNKNOWN** until captured from the actual account.
- Do not re-install a plugin, edit the WordPress theme or change a consent
  banner solely because this report says `UNKNOWN`.
- Do not create a fake measurement event to make a test green.

References: [Google — Enhanced measurement events](https://support.google.com/analytics/answer/9216061)
and [Google — event parameters including `link_domain` and `link_url`](https://support.google.com/analytics/table/13594742).
