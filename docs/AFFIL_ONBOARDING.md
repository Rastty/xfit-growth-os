# Xfit — affiliate onboarding (Affial + NaMaximum)

## Confirmed tracking structure
The owner corrected an older erroneous eHUB link. The **current partner link is on `www.namaximum.cz`** and has the parameters `utm_medium=affiliate`, `utm_campaign=affial.com`, `utm_source=pap`, `a_aid`, `a_bid`. The exact referral IDs and URL are intentionally **not committed**.

The public [Affial NaMaximum campaign](https://www.affial.com/namaximum/) offers **7.5% commission, 30-day cookie** and states that **PPC advertising is prohibited**. Confirm that this specific publisher account is approved for the campaign and verify the current terms in the dashboard before publishing.

### Store values in GitHub Secrets
Settings → Secrets and variables → Actions → **Secrets**

- `XFIT_AFFIL_DEFAULT_LINK`: paste the **corrected NaMaximum affiliate homepage URL** from the user directly into the encrypted secret. Replace any prior eHUB value; do not paste URLs with tracking IDs into issues, commits or conversations.
- `XFIT_GREENMEDICAL_FEED_URL`: the **separate GreenMedical/Venalio Heureka XML URL** with a rotated secret key (if this *other* advertiser should be integrated). **Do not use this feed for NaMaximum links.**
- If available later, a NaMaximum XML feed URL should use its own separate secret, e.g. `XFIT_NAMAXIMUM_FEED_URL`, and will require a dedicated parser/validator. Do not assign the GreenMedical URL to it.

The Affial portal documentation states: **Propagace → XML feedy** (if the advertiser supplies one), and **Propagace → Banners & Links → Dynamický odkaz** for product-level affiliate links:
- https://help.affial.com/article/13-jak-zacit-s-propagaci
- https://help.affial.com/article/28-vytvoreni-odkazu

### Important mismatch
- **Affiliate merchant:** NaMaximum.cz
- **Previously supplied feed merchant:** GreenMedical (hosted by Venalio)
- These are **not the same store**. Never use GreenMedical product prices, images or SKUs to imply that NaMaximum sells the same offers or that its affiliate homepage URL is a product link.
- The format of the correct referral link can be validated locally. Conversion tracking and actual affiliation are **not verified** until live referral/campaign reporting is checked.

### Optional read-only GreenMedical feed validation
If GreenMedical is independently approved and intended, set `XFIT_GREENMEDICAL_FEED_URL` and `XFIT_AFFIL_DEFAULT_LINK` (correct NaMaximum URL) as secrets. Under **Variables**, set `XFIT_AFFIL_FEED_ENABLED=true`. Then run **XFIT Affiliate Feed Validation**, which only normalizes and privately archives the GreenMedical offers; it does not publish them or combine them with NaMaximum links. Securely rotate the previously shared Venalio secretKey if possible. The workflow cannot yet import a NaMaximum feed.

### Publish checklist
1. Confirm approval of the NaMaximum Affial campaign and the real product feed.
2. Normalize product images, merchant URLs, GTIN/SKU, prices including VAT, and availability.
3. Generate and verify actual product-level Affial deep links for **the same merchant**.
4. Disclose affiliate links and track outbound clicks; never present misleading or unsupported supplement claims.
5. Verify conversion tracking in Affial dashboard before scaling.

Do not claim a live affiliate integration until its feeds and referral links are verified and publicly deployed.
