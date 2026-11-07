import unittest
from scripts.xfit_feed_ingest import parse_feed, safe_product_url, parse_price, validate_affiliate_link

class AffiliateFeedTests(unittest.TestCase):
    def test_valid_namaximum_affial_campaign(self):
        result = validate_affiliate_link(
            "https://www.namaximum.cz?utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap&a_aid=EXAMPLE&a_bid=EXAMPLE"
        )
        self.assertEqual(result, "affial_namaximum_tracking_format_valid__product_deeplinks_unverified")

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

    def test_namaximum_creapure_feed_sample(self):
        sample=b"""<SHOP><SHOPITEM><ITEM_ID>392</ITEM_ID>
        <PRODUCTNAME>Creatine Pure - Creapure Natural 1kg</PRODUCTNAME>
        <EAN>8586017480698</EAN><PRICE_VAT>999</PRICE_VAT>
        <URL>https://www.namaximum.cz/kategorie/kreatin/creatine-creapure?variant=392&amp;utm_source=heureka&amp;utm_medium=cpc</URL>
        <IMGURL>https://greenmedical.bwcdn.net/media/2020/06/2/1/creatine-pure-2014.jpg</IMGURL>
        </SHOPITEM></SHOP>"""
        offers, skipped = parse_feed(sample)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["merchant"], "NaMaximum.cz")
        self.assertEqual(offers[0]["id"], "392")
        self.assertEqual(offers[0]["ean"], "8586017480698")
        self.assertEqual(offers[0]["source_url"], "https://www.namaximum.cz/kategorie/kreatin/creatine-creapure?variant=392")
        self.assertIsNone(offers[0]["affiliate_url"])
        self.assertFalse(offers[0]["publish_ready"])

    def test_foreign_merchant_url_skipped(self):
        sample=b"<SHOP><SHOPITEM><PRODUCTNAME>Protein</PRODUCTNAME><PRICE_VAT>299</PRICE_VAT><URL>https://other-shop.example/p</URL></SHOPITEM></SHOP>"
        offers, skipped=parse_feed(sample)
        self.assertEqual(len(offers), 0)
        self.assertEqual(skipped["not_namaximum_product_link"], 1)

    def test_heureka_items(self):
        sample=b"""<?xml version="1.0" encoding="UTF-8"?>
        <SHOP><SHOPITEM><ITEM_ID>123</ITEM_ID><PRODUCTNAME>Protein A</PRODUCTNAME>
        <CATEGORYTEXT>Sport a fitness</CATEGORYTEXT><PRICE_VAT>299.90</PRICE_VAT>
        <URL>https://www.namaximum.cz/p/a?secretKey=hidden&amp;variant=1</URL>
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
    def test_reject_nonfinite_and_rounded_zero_prices_at_xml_boundary(self):
        for text in ("NaN", "nan", "Inf", "-Infinity", "1e309",
                     "0", "-2", "0.001", "broken", "9"*80):
            with self.subTest(price=text):
                self.assertIsNone(parse_price(text))
        for bad in (None, True, 350, [], {}):
            with self.subTest(type=type(bad).__name__):
                self.assertIsNone(parse_price(bad))
        self.assertEqual(parse_price("299,90"), 299.90)
        self.assertEqual(parse_price(" 1 000,50 "), 1000.50)

    def test_one_poisoned_xml_item_does_not_block_valid_merchandise(self):
        sample = b"""<SHOP>
        <SHOPITEM><ITEM_ID>101</ITEM_ID><PRODUCTNAME>Creatine Monohydrate 500g</PRODUCTNAME>
          <PRICE_VAT>NaN</PRICE_VAT><URL>https://www.namaximum.cz/p/a?variant=1</URL></SHOPITEM>
        <SHOPITEM><ITEM_ID>102</ITEM_ID><PRODUCTNAME>Whey WPC 1000g</PRODUCTNAME>
          <PRICE_VAT>Infinity</PRICE_VAT><URL>https://www.namaximum.cz/p/b?variant=2</URL></SHOPITEM>
        <SHOPITEM><ITEM_ID>103</ITEM_ID><PRODUCTNAME>Creatine Monohydrate 1000g</PRODUCTNAME>
          <PRICE_VAT>899.90</PRICE_VAT><URL>https://www.namaximum.cz/p/c?variant=3</URL></SHOPITEM>
        </SHOP>"""
        result, skipped = parse_feed(sample)
        self.assertEqual([p["id"] for p in result], ["103"])
        self.assertEqual(result[0]["price_czk"], 899.9)
        self.assertEqual(skipped["missing_title_or_price"], 2)

    def test_doctype_rejected(self):
        with self.assertRaises(ValueError):
            parse_feed(b'<!DOCTYPE shop [ <!ENTITY x "y"> ]><SHOP/>')
