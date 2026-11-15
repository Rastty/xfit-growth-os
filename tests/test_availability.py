import unittest

from scripts.xfit_availability import delivery_note, delivery_state
from scripts.xfit_feed_ingest import parse_feed
from scripts.xfit_select import select_offers
from scripts.xfit_creatine_guide import build_document as creatine_document
from scripts.xfit_whey_guide import build_document as whey_document


BASE = ("https://www.namaximum.cz/?utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap"
        "&a_aid=TESTA&a_bid=TESTB")
SAMPLE = ("https://www.namaximum.cz/p/example?variant=10&utm_medium=affiliate"
          "&utm_campaign=affial.com&utm_source=pap&a_aid=TESTA&a_bid=TESTB")


def product(ident, name, date=None, availability=""):
    item = {
        "id": str(ident), "title": name, "merchant": "NaMaximum.cz",
        "category": "Syrovátkové proteiny", "price_czk": 500 + ident,
        "ean": str(ident),
        "source_url": f"https://www.namaximum.cz/p/product-{ident}?variant={ident}",
    }
    if date is not None:
        item["delivery_date"] = date
    if availability:
        item["availability_raw"] = availability
    return item


class AvailabilityTests(unittest.TestCase):
    def test_heureka_days_are_dispatch_estimates_not_realtime_inventory(self):
        for raw, expected in (("0", "feed_stocked"), ("1", "up_to_week"),
                              ("7", "up_to_week"), ("8", "slow_dispatch"),
                              ("30", "slow_dispatch"), ("31", "slow_dispatch"),
                              ("2026-12-01", "preorder"), ("", "unknown"),
                              ("-1", "unknown"), ("not a number", "unknown")):
            with self.subTest(value=raw):
                self.assertEqual(delivery_state({"delivery_date": raw}), expected)
        self.assertEqual(delivery_state({"delivery_date": "0",
                                         "availability_raw": "Vyprodáno"}), "unavailable")

    def test_feed_preserves_field_provenance_independent_of_xml_tag_order(self):
        raw = b"""<SHOP><SHOPITEM>
            <ITEM_ID>10</ITEM_ID><PRODUCTNAME>Whey WPC 1000g</PRODUCTNAME>
            <PRICE_VAT>890</PRICE_VAT><AVAILABILITY>Vyprodano</AVAILABILITY>
            <DELIVERY_DATE>0</DELIVERY_DATE>
            <URL>https://www.namaximum.cz/p/whey?variant=10</URL>
            </SHOPITEM></SHOP>"""
        products, errors = parse_feed(raw)
        self.assertFalse(errors)
        self.assertEqual(products[0]["delivery_date"], "0")
        self.assertEqual(products[0]["availability_raw"], "Vyprodano")
        self.assertEqual(delivery_state(products[0]), "unavailable")

    def test_selector_excludes_explicitly_unavailable_slow_and_preorder(self):
        items = [
            product(10, "Whey WPC 1000g", "0"),
            product(11, "Whey WPC 750g", "3"),
            product(12, "Whey WPC 2000g", "8"),
            product(13, "Whey WPC 500g", "2026-12-01"),
            product(14, "Whey WPC 1500g", "0", "Není skladem"),
            product(15, "Whey WPC 1000g Natural", ""),
        ]
        selected = select_offers({"products": items}, "whey", limit=None)
        self.assertEqual({v["id"] for v in selected}, {"10", "11", "15"})
        self.assertEqual({v["availability_state"] for v in selected},
                         {"feed_stocked", "up_to_week", "unknown"})
        self.assertIn("v XML nepotvrzena", delivery_note(selected[-1])
                      if selected[-1]["availability_state"] == "unknown" else
                      delivery_note(next(x for x in selected
                                         if x["availability_state"] == "unknown")))

    def test_advisors_show_a_caveat_by_every_product_without_fake_stock_claim(self):
        for kind, build, names in (
            ("creatine", creatine_document,
             ("Creatine Monohydrate 1000g", "Creatine Monohydrate 500g")),
            ("whey", whey_document, ("Whey WPC 1000g", "Whey WPC 500g")),
        ):
            with self.subTest(kind=kind):
                items = [product(10, names[0], "0"),
                         product(11, names[1], "")]
                for item in items:
                    item["category"] = "Kreatin" if kind == "creatine" else "Syrovátkové proteiny"
                html = build({"merchant": "namaximum.cz", "merchant_match": True,
                              "products": items}, BASE, SAMPLE)["content"]
                self.assertEqual(html.count("data-xfit-availability="), 2)
                self.assertIn('data-xfit-availability="feed_stocked"', html)
                self.assertIn('data-xfit-availability="unknown"', html)
                self.assertIn("v XML nepotvrzena", html)
                self.assertIn("ověřte v obchodě", html)
                self.assertIn("7 dní", html)
                self.assertNotIn("garantovaně skladem", html)


if __name__ == "__main__":
    unittest.main()
