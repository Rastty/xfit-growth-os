import unittest
from html.parser import HTMLParser

from scripts.xfit_click_metadata import card_click_attributes
from scripts.wp_publish import PublishError
from tests.test_creatine_guide import BASE as CBASE, SAMPLE as CSAMPLE, CreatineGuideTests
from tests.test_whey_guide import BASE as WBASE, SAMPLE as WSAMPLE, WheyTests
from scripts.xfit_creatine_guide import build_document as creatine_document
from scripts.xfit_whey_guide import build_document as whey_document


class OutboundAttributes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ctas = []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and "sponsored" in dict(attrs).get("rel", "").split():
            self.ctas.append(dict(attrs))


class ClickMetadataTests(unittest.TestCase):
    def test_feed_id_is_whitelisted_and_never_contains_tracking_url(self):
        self.assertEqual(
            card_click_attributes("392", "creatine"),
            ' data-xfit-engine="creatine" data-xfit-partner="namaximum"'
            ' data-xfit-product-id="392"',
        )
        for invalid in (None, "", "000392", "392&foo", "392.0", True, False,
                        0, -1, 2147483648, 3.2, "https://example.com/1"):
            with self.subTest(value=repr(invalid)), self.assertRaises(PublishError):
                card_click_attributes(invalid, "whey")
        with self.assertRaises(PublishError):
            card_click_attributes(392, "unknown")

    def test_both_trusted_catalog_builders_produce_attributed_ctas(self):
        creators = [
            (CreatineGuideTests().setUp, creatine_document, CBASE, CSAMPLE,
             "creatine"),
            (WheyTests().setUp, whey_document, WBASE, WSAMPLE, "whey"),
        ]
        for setup, builder, base, sample, engine in creators:
            instance = setup.__self__
            setup()
            page = builder(instance.catalog, base, sample)
            parsed = OutboundAttributes()
            parsed.feed(page["content"])
            self.assertGreaterEqual(len(parsed.ctas), 2)
            for cta in parsed.ctas:
                self.assertEqual(cta["data-xfit-engine"], engine)
                self.assertEqual(cta["data-xfit-partner"], "namaximum")
                self.assertTrue(cta["data-xfit-product-id"].isdigit())
                self.assertNotIn("a_aid", " ".join(
                    str(v) for k, v in cta.items() if k.startswith("data-xfit")
                ))
                self.assertIn("sponsored", cta["rel"].split())


if __name__ == "__main__":
    unittest.main()
