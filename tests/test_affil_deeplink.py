import unittest
from urllib.parse import quote
from scripts.xfit_affil_deeplink import classify_product_link

BASE="https://www.namaximum.cz/?utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap&a_aid=TEST123&a_bid=TESTCAMPAIGN"
PRODUCT="https://www.namaximum.cz/kategorie/kreatin/creatine-creapure?variant=392&utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap&a_aid=TEST123&a_bid=TESTCAMPAIGN"

class AffialLinkTests(unittest.TestCase):
    def test_direct_product_example(self):
        s=classify_product_link(BASE,PRODUCT)
        self.assertEqual(s["scheme"],"merchant_direct_query")
        self.assertFalse(s["publish_ready"])

    def test_redirect_desturl(self):
        url="https://login.affial.com/scripts/somepath?a_aid=TEST123&a_bid=TESTCAMPAIGN&desturl="+quote("https://www.namaximum.cz/kategorie/kreatin/creatine-creapure?variant=392",safe="")
        s=classify_product_link(BASE,url)
        self.assertEqual(s["scheme"],"affial_redirect_desturl")

    def test_id_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            classify_product_link(BASE,PRODUCT.replace("TEST123","WRONG"))

    def test_other_merchant_rejected(self):
        with self.assertRaises(ValueError):
            classify_product_link(BASE,PRODUCT.replace("www.namaximum.cz","evil.example"))

    def test_homepage_rejected(self):
        with self.assertRaises(ValueError):
            classify_product_link(BASE,BASE)
