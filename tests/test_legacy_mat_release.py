import unittest
from unittest.mock import patch
from scripts.xfit_legacy_mat_release import SCOPES, TARGET, content, prepare, sha, stable_metadata
from scripts.wp_publish import PublishError, editorial_links
from scripts.xfit_editorial_gate import check_document

class LegacyMatRevisionTests(unittest.TestCase):
    def test_both_distinct_helpful_revisions_and_exact_routes(self):
        one,two=[content(c) for c in SCOPES.values()]
        self.assertIn("půjčovné 35 Kč",one)
        self.assertNotIn("půjčovné 35 Kč",two)
        self.assertIn("tuhost",two)
        for body in (one,two):
            self.assertEqual(editorial_links(body).count(TARGET),1)
            self.assertTrue(check_document({"content":body},commercial=False)["passed"])
            self.assertNotIn("5NM2022",body)
            self.assertNotIn("namaximum.cz",body)

    def test_exact_pinned_source_or_noop_only(self):
        from dataclasses import replace
        for cfg in SCOPES.values():
            old="reviewed exact source"
            testcfg=replace(cfg,old_sha=sha(old))
            post={"id":cfg.pid,"slug":cfg.slug,"link":cfg.url,"status":"publish",
                  "title":{"raw":"Mat"},"content":{"raw":old},"modified_gmt":cfg.modified}
            self.assertEqual(prepare(testcfg,post),(old,content(cfg)))
            self.assertEqual(prepare(testcfg,{**post,"content":{"raw":content(cfg)}})[0],content(cfg))
            for bad in ({**post,"modified_gmt":"other"},{**post,"id":10860},
                        {**post,"content":{"raw":old+" changed"}}):
                with self.assertRaises(PublishError):
                    prepare(testcfg,bad)

    def test_auto_generated_excerpt_is_not_a_stored_metadata_change(self):
        before={"id":3377,"slug":"mat","status":"publish","link":"https://xfit.cz/mat/",
                "categories":[1],"tags":[3],"sticky":False,"featured_media":12,
                "title":{"raw":"Mat","rendered":"Mat"},
                "excerpt":{"raw":"","rendered":"Original generated text"}}
        after={**before,"excerpt":{"raw":"","rendered":"New generated text"}}
        self.assertEqual(stable_metadata(before),stable_metadata(after))
        for changed in ({**after,"excerpt":{"raw":"Explicit new excerpt","rendered":"new"}},
                        {**after,"categories":[2]},{**after,"featured_media":99},
                        {**after,"title":{"raw":"New title","rendered":"New title"}}):
            self.assertNotEqual(stable_metadata(before),stable_metadata(changed))
        with self.assertRaises(PublishError):
            stable_metadata({k:v for k,v in before.items() if k!="excerpt"})

if __name__=="__main__":
    unittest.main()
