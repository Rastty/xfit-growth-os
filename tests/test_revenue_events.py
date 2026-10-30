import unittest

from scripts.xfit_revenue_events import build_event


class RevenueEventTests(unittest.TestCase):
    def setUp(self):
        self.fields = {
            "page": "xfit-os-kreatin-poradce",
            "selection_engine": "creatine",
        }

    def test_consent_is_required(self):
        self.assertIsNone(build_event("advisor_start", self.fields))
        self.assertIsNone(build_event("advisor_start", self.fields,
                                      analytics_consent=False))
        for consent in ("yes", 1, None):
            with self.subTest(consent=consent), self.assertRaises(ValueError):
                build_event("advisor_start", self.fields,
                            analytics_consent=consent)

    def test_advisor_actions_include_no_answers(self):
        for page, engine in (("xfit-os-kreatin-poradce", "creatine"),
                             ("xfit-os-syrovatkovy-protein-porovnani", "whey")):
            for name in ("advisor_start", "advisor_complete"):
                fields = {"page": page, "selection_engine": engine}
                self.assertEqual(build_event(name, fields, analytics_consent=True),
                                 {"name": name, "params": fields})

    def test_click_uses_only_catalog_identifiers(self):
        fields = dict(self.fields, partner="namaximum", product_id=392)
        result = build_event("affiliate_outbound_click", fields,
                             analytics_consent=True, verified_product_ids={392})
        self.assertEqual(result["params"], fields)
        fields["product_id"] = 999
        self.assertEqual(result["params"]["product_id"], 392)

    def test_click_requires_verified_catalog_membership(self):
        fields = dict(self.fields, partner="namaximum", product_id=392)
        for catalog in (None, set(), {393}, [392], {True, 392},
                        {"392"}, {0, 392}, {2**31, 392}):
            with self.subTest(catalog=catalog), self.assertRaises(ValueError):
                build_event("affiliate_outbound_click", fields,
                            analytics_consent=True, verified_product_ids=catalog)
        result = build_event("affiliate_outbound_click", fields,
                             analytics_consent=True,
                             verified_product_ids=frozenset({392, 393}))
        self.assertEqual(result["params"], fields)
        self.assertNotIn("verified_product_ids", result["params"])

    def test_denied_consent_does_not_require_catalog(self):
        fields = dict(self.fields, partner="namaximum", product_id=392)
        self.assertIsNone(build_event("affiliate_outbound_click", fields))

    def test_private_and_unknown_fields_fail_closed(self):
        for key in ("email", "health", "answers", "url", "a_aid", "user_id"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_event("advisor_complete", dict(self.fields, **{key: "private"}),
                            analytics_consent=True)

    def test_rejects_untrusted_values_and_missing_fields(self):
        click = dict(self.fields, partner="namaximum", product_id=392)
        invalid = [dict(click, page="https://example.org/?email=private"),
                   dict(click, selection_engine="whey"), {},
                   dict(click, partner="other")]
        for product_id in (True, 0, -1, 2**31, 1.5, "392", "https://example.org"):
            invalid.append(dict(self.fields, partner="namaximum", product_id=product_id))
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                build_event("affiliate_outbound_click", fields,
                            analytics_consent=True, verified_product_ids={392})
        for name in ("purchase", "commission", "health_answer", None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                build_event(name, self.fields, analytics_consent=True)
