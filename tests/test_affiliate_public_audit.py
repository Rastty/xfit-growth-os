"""Public-versus-WP affiliate truth, without browsing merchant click URLs."""
import unittest

from scripts import xfit_affiliate_public_audit as probe

BASE = ("https://www.namaximum.cz/?utm_medium=affiliate"
        "&utm_campaign=affial.com&utm_source=pap&a_aid=SENSITIVE_AID&a_bid=SENSITIVE_BID")
GOOD_QUERY = ("?variant=392&utm_source=pap&utm_medium=affiliate"
              "&a_aid=SENSITIVE_AID&a_bid=SENSITIVE_BID&utm_campaign=affial.com")
SLUG = "xfit-os-kreatin-poradce"


def card(item_id, variant):
    return (
        '<article class="xfit-product-card" id="xfit-offer-' + item_id + '">'
        '<h3>Kreatin monohydrát</h3>'
        '<a data-xfit-engine="creatine" data-xfit-partner="namaximum"'
        ' data-xfit-product-id="' + item_id + '" rel="sponsored nofollow"'
        ' href="https://www.namaximum.cz/kreatin/produkt'
        + GOOD_QUERY.replace("392", variant) + '">Zobrazit nabídku</a>'
        '</article>'
    )


def body():
    return (
        '<html><h1>Výběr kreatinu</h1><p>Affiliate: Xfit může dostat provizi.</p>'
        + card("392", "392") + card("393", "393") + '</html>'
    )


def wp(content=None):
    return {
        "id": 25455, "slug": SLUG, "status": "publish",
        "link": "https://xfit.cz/" + SLUG + "/",
        "content": {"rendered": body() if content is None else content},
    }


class AffiliateParityTests(unittest.TestCase):
    def test_two_real_matching_cards_are_safely_reported(self):
        result = probe.audit_page(
            SLUG, BASE, wp_reader=lambda slug: wp(),
            public_reader=lambda slug: body())
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["source_card_count"], 2)
        self.assertTrue(result["offer_destinations_match"])
        for secret in ("SENSITIVE_AID", "SENSITIVE_BID", "392", "393"):
            self.assertNotIn(secret, str(result))

    def test_catalog_variant_match_is_explicit_evidence_not_revenue(self):
        result = probe.audit_page(
            SLUG, BASE, wp_reader=lambda slug: wp(),
            public_reader=lambda slug: body())
        self.assertEqual(result["catalog_variant_linkage"], "EXACT_VARIANT_IDS_MATCH")
        self.assertEqual(result["source_variant_linkage_counts"]["matched"], 2)
        self.assertEqual(result["public_variant_linkage_counts"]["matched"], 2)
        self.assertEqual(result["public_variant_linkage_counts"]["mismatched"], 0)
        self.assertNotIn("SENSITIVE_", str(result))
        for sensitive_id in ("392", "393"):
            self.assertNotIn(sensitive_id, str(result))

    def test_same_wrong_variant_in_wp_and_public_does_not_get_false_verification(self):
        # WP/public URL parity is necessary but insufficient if *both* carry
        # the same wrong catalog-id-to-merchant-variant mapping.
        mismatched = body().replace(card("393", "393"), card("393", "392"))
        result = probe.audit_page(
            SLUG, BASE, wp_reader=lambda slug: wp(mismatched),
            public_reader=lambda slug: mismatched)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["offer_destinations_match"])
        self.assertEqual(result["catalog_variant_linkage"], "MISMATCH_REQUIRES_REVIEW")
        self.assertEqual(result["public_variant_linkage_counts"]["mismatched"], 1)
        self.assertNotIn("393", str(result))
        self.assertNotIn("392", str(result))

    def test_missing_or_ambiguous_variant_keeps_evidence_unknown(self):
        for altered in (
            body().replace("?variant=392&", "?", 1),
            body().replace("?variant=392&", "?variant=392&variant=393&", 1),
        ):
            with self.subTest(altered=altered.count("variant=")):
                result = probe.audit_page(
                    SLUG, BASE, wp_reader=lambda slug: wp(altered),
                    public_reader=lambda slug: altered)
                self.assertEqual(result["errors"], [])
                self.assertEqual(result["catalog_variant_linkage"],
                                 "UNPROVEN_VARIANT_LINKAGE")
                self.assertEqual(result["public_variant_linkage_counts"]["matched"], 1)
                self.assertEqual(
                    sum(result["public_variant_linkage_counts"].values()), 2)

    def test_variant_identity_helper_never_trusts_bad_catalog_id(self):
        url = "https://www.namaximum.cz/p/product?variant=392"
        self.assertEqual(probe.variant_identity_status(url, "392"), "MATCH")
        self.assertEqual(probe.variant_identity_status(url, "393"), "MISMATCH")
        self.assertEqual(probe.variant_identity_status(url, "0392"),
                         "UNVERIFIABLE_CATALOG_ID")
        self.assertEqual(probe.variant_identity_status(url, ""),
                         "UNVERIFIABLE_CATALOG_ID")
        self.assertEqual(probe.variant_identity_status(
            "https://www.namaximum.cz/p/product", "392"), "NO_VARIANT")

    def test_public_campaign_tampering_not_hidden_by_valid_wp_source(self):
        altered = body().replace("a_bid=SENSITIVE_BID", "a_bid=DIFFERENT", 1)
        result = probe.audit_page(
            SLUG, BASE, wp_reader=lambda slug: wp(),
            public_reader=lambda slug: altered)
        self.assertIn("wp_public_offer_or_tracking_mismatch", result["errors"])
        self.assertIn("public_invalid_merchant_campaign_destination", result["errors"])
        self.assertFalse(result["offer_destinations_match"])

    def test_missing_card_and_missing_metadata_detected(self):
        result = probe.audit_page(
            SLUG, BASE, wp_reader=lambda slug: wp(),
            public_reader=lambda slug: body().replace(card("393", "393"), ""))
        self.assertIn("public_unexpected_card_count", result["errors"])
        self.assertEqual(result["public_card_count"], 1)
        self.assertFalse(result["offer_destinations_match"])

    def test_duplicate_id_and_wrong_engine_are_not_trusted(self):
        duplicate = body().replace('data-xfit-product-id="393"',
                                   'data-xfit-product-id="392"')
        result = probe.card_evidence(duplicate, SLUG, BASE)
        self.assertIn("duplicate_catalog_cta", result["errors"])
        wrong = body().replace('data-xfit-engine="creatine"',
                               'data-xfit-engine="whey"', 1)
        self.assertIn("invalid_catalog_cta_metadata",
                      probe.card_evidence(wrong, SLUG, BASE)["errors"])

    def test_open_redirect_query_root_and_unsafe_campaign_block(self):
        self.assertTrue(probe.canonical_article(
            "https://www.xfit.cz/" + SLUG + "/", SLUG))
        for url in (
            "https://xfit.cz/",
            "https://xfit.cz/" + SLUG + "/?cachebust=1",
            "http://xfit.cz/" + SLUG + "/",
            "https://bad.example/" + SLUG + "/",
            "https://xfit.cz/another-article/",
            "https://xfit.cz:443/" + SLUG + "/",
        ):
            with self.subTest(url=url):
                self.assertFalse(probe.canonical_article(url, SLUG))
        aid, bid = "SENSITIVE_AID", "SENSITIVE_BID"
        valid = "https://www.namaximum.cz/kreatin/produkt" + GOOD_QUERY
        self.assertTrue(probe.safe_affiliate_url(valid, aid, bid))
        for bad in (
            valid.replace("www.namaximum.cz", "fake-namaximum.cz"),
            valid.replace("https:", "http:"),
            valid.replace("/kreatin/produkt", "/"),
            valid.replace("SENSITIVE_BID", "wrong"),
            valid + "#misleading",
            valid.replace("namaximum.cz/", "namaximum.cz:8080/"),
        ):
            with self.subTest(bad=bad.split("?")[0]):
                self.assertFalse(probe.safe_affiliate_url(bad, aid, bid))

    def test_wrong_wp_article_cannot_be_public_verified(self):
        for invalid in (
            {**wp(), "id": 25456},
            {**wp(), "status": "draft"},
            {**wp(), "link": "https://xfit.cz/wrong/"}
        ):
            with self.subTest(id=invalid["id"]):
                with self.assertRaises(ValueError):
                    probe.audit_page(
                        SLUG, BASE, wp_reader=lambda slug: invalid,
                        public_reader=lambda slug: body())

    def test_disclosure_and_empty_cards_fail_closed(self):
        no_disclosure = body().replace(
            "Affiliate: Xfit může dostat provizi.", "Nezávislý výběr.")
        result = probe.card_evidence(no_disclosure, SLUG, BASE)
        self.assertIn("missing_affiliate_disclosure", result["errors"])
        empty = '<html><h1>Prázdné</h1><p>affiliate</p></html>'
        self.assertIn("unexpected_card_count",
                      probe.card_evidence(empty, SLUG, BASE)["errors"])

    def test_no_side_effects_and_no_assumed_orders_or_commissions(self):
        self.assertNotIn("http", str(probe.PAGES))
        self.assertEqual(probe.MAX_CARDS, 12)
        self.assertFalse(probe.safe_affiliate_url(
            "https://www.namaximum.cz/?a_aid=SENSITIVE_AID", "SENSITIVE_AID", "SENSITIVE_BID"))


if __name__ == "__main__":
    unittest.main()
