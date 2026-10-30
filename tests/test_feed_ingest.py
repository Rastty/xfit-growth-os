import unittest
from scripts.xfit_feed_ingest import parse_feed, safe_product_url, parse_price

class AffiliateFeedTests(unittest.TestCase):
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
