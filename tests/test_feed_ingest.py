import unittest
from scripts.xfit_feed_ingest import parse_feed, safe_product_url, parse_price, validate_affiliate_link

class AffiliateFeedTests(unittest.TestCase):
    def test_valid_namaximum_affial_campaign(self):
        result = validate_affiliate_link(
            "https://www.namaximum.cz?utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap&a_aid=EXAMPLE&a_bid=EXAMPLE"
        )
        self.assertEqual(result, "affial_namaximum_link_format_valid__greenmedical_feed_is_DIFFERENT_MERCHANT")

    def test_reject_namaximum_without_tracking_ids(self):
        self.assertEqual(
            validate_affiliate_link("https://www.namaximum.cz/?utm_campaign=affial.com"),
            "namaximum_link_missing_expected_affial_parameters"
        )

    def test_old_ehub_link_is_not_affial_link(self):
        self.assertEqual(
            validate_affiliate_link("https://ehub.cz/system/scripts/click.php?a_aid=EXAMPLE&a_bid=EXAMPLE"),
            "ehub_link_is_not_the_confirmed_affial_namaximum_campaign"
        )

    def test_heureka_items(self):
        sample=b"""<?xml version="1.0" encoding="UTF-8"?>
        <SHOP><SHOPITEM><ITEM_ID>123</ITEM_ID><PRODUCTNAME>Protein A</PRODUCTNAME>
        <CATEGORYTEXT>Sport a fitness</CATEGORYTEXT><PRICE_VAT>299.90</PRICE_VAT>
        <URL>https://shop.example.com/p/a?secretKey=hidden&amp;variant=1</URL>
        </SHOPITEM></SHOP>"""
        items, skipped=parse_feed(sample)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["price_czk"],299.9)
        self.assertNotIn("secretKey",items[0]["source_url"])
        self.assertFalse(items[0]["publish_ready"])
    def test_restricted_products_filtered(self):
        xml=b"<SHOP><SHOPITEM><PRODUCTNAME>CBD oil</PRODUCTNAME><PRICE_VAT>299</PRICE_VAT></SHOPITEM></SHOP>"
        items, skipped=parse_feed(xml)
        self.assertEqual(len(items),0)
        self.assertEqual(skipped["restricted_or_sensitive_product"],1)
    def test_prices_and_malformed(self):
        self.assertIsNone(parse_price("0"))
        self.assertIsNone(parse_price("unknown"))
        with self.assertRaises(ValueError):
            parse_feed(b"<SHOP>")
    def test_doctype_rejected(self):
        with self.assertRaises(ValueError):
            parse_feed(b'<!DOCTYPE shop [ <!ENTITY x "y"> ]><SHOP/>')
