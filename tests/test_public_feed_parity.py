"""Offline regression: source/current XML/public product identity & price joins."""
import json
import unittest
from unittest.mock import patch

from scripts.xfit_public_feed_parity import (
    _cents, inspect, ParityError,
)

BASE = ("https://www.namaximum.cz/bezpecny-produkt/"
        "?utm_campaign=affial.com&utm_source=pap&utm_medium=affiliate"
        "&a_aid=private-demo-a& a_bid=private-demo-b").replace("& a_bid", "&a_bid")


def page(engine, *, price_override=None, href_override=None):
    start = '<p>Affiliate spolupráce: z některých odkazů získáváme provizi.</p>'
    cards = []
    base = 100 if engine == "creatine" else 200
    for i in range(1, 7):
        item_id = str(base + i)
        amount = 100 + i
        if price_override is not None and i == 1:
            amount = price_override
        extra = "&data1=xfit&data2=creatine" if engine == "creatine" else ""
        href = ("https://www.namaximum.cz/product/"
                "?utm_campaign=affial.com&utm_source=pap&utm_medium=affiliate"
                "&a_aid=private-demo-a&a_bid=private-demo-b"
                "&variant=" + item_id + extra)
        if href_override is not None and i == 1:
            href = href_override
        cards.append(
            '<article class="xfit-product-card"><h3>Produkt pro test</h3>'
            '<p>Cena: ' + str(amount) + ',00 Kč · Balení: 500 g</p>'
            '<p>Cena za 100 g prášku: 20,00 Kč</p>'
            '<a data-xfit-engine="' + engine + '"'
            ' data-xfit-partner="namaximum"'
            ' data-xfit-product-id="' + item_id + '"'
            ' rel="sponsored nofollow" href="' + href + '">Zobrazit</a></article>'
        )
    return start + "".join(cards)


def current_feed():
    return [
        {"id":str(j), "price_czk":float(100+j%100),
         "delivery_date":"0", "availability_raw":""}
        for j in list(range(101, 107)) + list(range(201, 207))
    ]


def pages():
    return {
        "xfit-os-kreatin-poradce": (page("creatine"), page("creatine")),
        "xfit-os-syrovatkovy-protein-porovnani": (page("whey"), page("whey")),
    }


class CurrentFeedPublicParityTests(unittest.TestCase):
    def test_twelve_source_public_prices_and_feed_identifiers_match(self):
        result = inspect(current_feed(), pages(), BASE)
        self.assertEqual(result["state"], "SOURCE_FEED_NUMERIC_PARITY_OBSERVED")
        self.assertEqual(sum(x["public_cards"] for x in result["pages"]), 12)
        self.assertEqual(sum(x["numeric_price_matches_feed"] for x in result["pages"]),12)
        self.assertEqual(sum(x["feed_availability_field_present"] for x in result["pages"]),12)
        self.assertFalse(result["merchant_checkout_price_verified"])
        self.assertFalse(result["merchant_checkout_stock_verified"])
        self.assertEqual(result["affiliate_click_requests"],0)
        self.assertEqual(result["wordpress_writes"],0)

    def test_feed_missing_one_item_is_review_not_claim_of_out_of_stock(self):
        feed = [item for item in current_feed() if item["id"] != "101"]
        result = inspect(feed, pages(), BASE)
        self.assertEqual(result["state"], "REVIEW_CURRENT_FEED_VS_PUBLIC_OFFERS")
        self.assertTrue(result["manual_review_required"])
        self.assertEqual(result["pages"][0]["feed_item_not_observed"],1)
        self.assertEqual(result["pages"][0]["numeric_price_matches_feed"],5)
        self.assertFalse(result["merchant_checkout_stock_verified"])

    def test_changed_feed_price_only_flags_source_numeric_difference(self):
        feed = current_feed()
        feed[0]["price_czk"] = 499.00
        result = inspect(feed, pages(), BASE)
        self.assertEqual(result["pages"][0]["numeric_price_differs_from_feed"],1)
        self.assertEqual(result["pages"][1]["numeric_price_matches_feed"],6)
        self.assertFalse(result["merchant_checkout_price_verified"])
        serialized = json.dumps(result,ensure_ascii=False)
        for sensitive in ("private-demo-a", "private-demo-b",
                          '"101"', '"499.00"', "namaximum.cz/product"):
            self.assertNotIn(sensitive,serialized)

    def test_duplicate_feed_id_is_ambiguous_not_a_match(self):
        feed = current_feed()
        feed.append(dict(feed[0]))
        result = inspect(feed, pages(), BASE)
        self.assertEqual(result["pages"][0]["ambiguous_feed_id"],1)
        self.assertEqual(result["state"],"REVIEW_CURRENT_FEED_VS_PUBLIC_OFFERS")

    def test_source_public_price_drift_refused_before_feed_join(self):
        altered = pages()
        source, _ = altered["xfit-os-kreatin-poradce"]
        altered["xfit-os-kreatin-poradce"] = (source, page("creatine",price_override=999))
        with self.assertRaisesRegex(ParityError,"WP_PUBLIC_OFFER_ID_OR_PRICE_DRIFT"):
            inspect(current_feed(), altered, BASE)

    def test_unsafe_affiliate_url_or_variant_not_considered_a_valid_offer(self):
        altered = pages()
        forged = page("creatine",href_override=
                      "https://evil.example/product/?variant=101")
        altered["xfit-os-kreatin-poradce"] = (forged,forged)
        with self.assertRaisesRegex(ParityError,"INVALID_AFFILIATE_CARD_CONTEXT"):
            inspect(current_feed(), altered, BASE)

    def test_unparseable_public_price_requires_review_not_fabricated_equal(self):
        altered = pages()
        source = page("creatine", price_override="Zavolejte")
        altered["xfit-os-kreatin-poradce"] = (source,source)
        result = inspect(current_feed(), altered, BASE)
        self.assertEqual(result["pages"][0]["displayed_price_not_parseable"],1)
        self.assertTrue(result["manual_review_required"])

    def test_price_parser_rejects_fractional_cents_locale_and_infinity(self):
        for value in ("NaN","Infinity","1,234.50","1e3","0","-20","1.009",
                      "", None, [], 0, 0.0):
            with self.subTest(value=str(value)):
                self.assertIsNone(_cents(value))
        self.assertEqual(_cents("1 245,50"),124550)
        self.assertEqual(_cents(1245.5),124550)

    def test_missing_feed_or_scope_rejected_without_any_network(self):
        with self.assertRaisesRegex(ParityError,"LATEST_FEED_INCOMPLETE"):
            inspect([],pages(),BASE)
        with self.assertRaisesRegex(ParityError,"SOURCE_OR_PUBLIC_PAGE_MISSING"):
            inspect(current_feed(),{},BASE)
        with patch("scripts.xfit_public_feed_parity.fetch_feed",
                   side_effect=AssertionError("pure function must not fetch")):
            self.assertEqual(inspect(current_feed(),pages(),BASE)["wordpress_writes"],0)


if __name__=="__main__":
    unittest.main()
