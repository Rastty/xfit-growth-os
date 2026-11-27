import unittest
from scripts.xfit_legacy_creatine_release import SCOPES
from scripts.xfit_legacy_mat_release import content, prepare
from scripts.wp_publish import PublishError, editorial_links
from scripts.xfit_coupon_cleanup import QUARANTINE_IDS
class LegacyCreatineTests(unittest.TestCase):
    def test_exact_distinct_sources_and_educational_routes(self):
        for cfg in SCOPES.values():
            self.assertNotIn(cfg.pid,QUARANTINE_IDS)
            body=content(cfg)
            self.assertEqual(editorial_links(body).count(cfg.target),1)
            self.assertIn("nih.gov",body)
            self.assertIn(cfg.cta,body)
            self.assertIn("nekup",body)
            self.assertNotIn("namaximum.cz",body)
            self.assertNotIn("5NM2022",body)
        self.assertIn("nasycovací",content(SCOPES["11753"]))
        self.assertIn("pufrované",content(SCOPES["11863"]))
        self.assertIn("100 Kč za 100 g",content(SCOPES["11882"]))
    def test_unreviewed_source_cannot_pass(self):
        for cfg in SCOPES.values():
            post={"id":cfg.pid,"slug":cfg.slug,"link":cfg.url,"status":"publish",
                  "title":{"raw":"Creatine"},"content":{"raw":"unreviewed"},"modified_gmt":cfg.modified}
            with self.assertRaises(PublishError):
                prepare(cfg,post)
