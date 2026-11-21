import unittest
from scripts.xfit_affiliate_health import check_markdown_html
BASE="https://www.namaximum.cz/?utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap&a_aid=TESTID&a_bid=TESTCAMPAIGN"
Q="?variant=392&utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap&a_aid=TESTID&a_bid=TESTCAMPAIGN"
def link(q=Q,rel="sponsored nofollow"):
    return '<a href="https://www.namaximum.cz/p/creapure'+q+'" rel="'+rel+'">Produkt</a>'
class HealthTests(unittest.TestCase):
    def test_good_links(self):
        result=check_markdown_html(link()+link(),BASE)
        self.assertEqual(result["errors"],[])
        self.assertEqual(result["merchant_link_count"],2)
    def test_url_tracking_is_not_a_reader_visible_disclosure(self):
        result=check_markdown_html(link()+link(),BASE)
        self.assertFalse(result["has_disclosure"])
        # The URLs contain utm_medium=affiliate, but that is not page copy.
        self.assertEqual(result["errors"],[])

    def test_actual_visible_notice_before_offer(self):
        body='<p>Partnerské odkazy: Xfit.cz může získat provizi.</p>'+link()+link()
        self.assertTrue(check_markdown_html(body,BASE)["has_disclosure"])

    def test_notice_after_first_offer_does_not_count(self):
        body=link()+'<p>Partnerské odkazy: Xfit.cz může získat provizi.</p>'+link()
        self.assertFalse(check_markdown_html(body,BASE)["has_disclosure"])

    def test_disclosure_in_hidden_or_script_content_does_not_count(self):
        text='Partnerské odkazy: Xfit.cz může získat provizi.'
        hidden=(
            '<script>'+text+'</script>',
            '<template><p>'+text+'</p></template>',
            '<div hidden><p>'+text+'</p></div>',
            '<div aria-hidden="true"><p>'+text+'</p></div>',
            '<div style="display: none"><p>'+text+'</p></div>',
        )
        for fragment in hidden:
            with self.subTest(fragment=fragment[:30]):
                self.assertFalse(check_markdown_html(fragment+link()+link(),BASE)["has_disclosure"])

    def test_wrong_campaign(self):
        result=check_markdown_html(link(Q.replace("TESTID","OTHER"))+link(),BASE)
        self.assertIn("wrong_campaign_ids",result["errors"])
    def test_missing_rel(self):
        result=check_markdown_html(link(rel="nofollow")+link(),BASE)
        self.assertIn("missing_sponsored_rel",result["errors"])
    def test_heureka_not_commissioned(self):
        result=check_markdown_html(link("?variant=392&utm_source=heureka")+link(),BASE)
        self.assertIn("wrong_campaign_utm",result["errors"])
    def test_zero_links(self):
        self.assertIn("insufficient_affiliate_product_links",check_markdown_html("<p>test</p>",BASE)["errors"])
