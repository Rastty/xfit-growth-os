import unittest
from scripts.xfit_public_freshness import TARGETS, owns_public_url, visible_has, probe
from scripts.wp_publish import PublishError


def post(slug, post_id, marker):
    return {"id":post_id, "slug":slug, "status":"publish",
            "content":{"raw":"<!-- xfit-growth-os:v1 -->\n<h2>"+marker+"</h2>"},
            "link":"https://xfit.cz/"+slug+"/"}


class PublicFreshnessTests(unittest.TestCase):
    def test_known_canonical_urls_only(self):
        self.assertTrue(owns_public_url("https://xfit.cz/xfit-os-kreatin-poradce/", "xfit-os-kreatin-poradce"))
        self.assertFalse(owns_public_url("https://external.example/xfit-os-kreatin-poradce/", "xfit-os-kreatin-poradce"))
        self.assertFalse(owns_public_url("https://xfit.cz/xfit-os-kreatin-poradce/?token=private", "xfit-os-kreatin-poradce"))

    def test_public_view_checks_edited_body_not_unchanged_title(self):
        target = TARGETS[2]
        original = post(*target)
        success = probe(target, read_post=lambda _:original,
                        read_public=lambda url:("<html><h1>Jak vybrat kreatin</h1><h2>Dvě cesty k výběru podle ceny</h2></html>",{"Age":"0"}))
        self.assertEqual(success["status"],"PUBLIC_FRESH")
        stale = probe(target, read_post=lambda _:original,
                      read_public=lambda url:("<html><h1>Jak vybrat kreatin</h1><p>Starý obsah</p></html>",{"Age":"720"}))
        self.assertEqual(stale["status"],"PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertTrue(stale["wp_source_has_target"])
        self.assertFalse(stale["public_has_target"])

    def test_source_missing_is_not_mistaken_for_cache_staleness(self):
        slug, ident, marker = TARGETS[3]
        source = post(slug, ident, "Stará sekce")
        result = probe(TARGETS[3], read_post=lambda _:source,
                       read_public=lambda _:("<h2>Dvě cesty k výběru podle ceny</h2>",{}))
        self.assertEqual(result["status"],"SOURCE_NOT_UPDATED")
        self.assertFalse(result["wp_source_has_target"])

    def test_public_transport_error_fails_safely_without_retrying_posts(self):
        target = TARGETS[2]
        result = probe(target, read_post=lambda _:post(*target),
                       read_public=lambda _: (_ for _ in ()).throw(OSError("network")))
        self.assertEqual(result["status"],"PUBLIC_READ_ERROR")
        self.assertNotIn("network",str(result))

    def test_visible_text_decodes_entities_and_whitespace(self):
        self.assertTrue(visible_has("<h2>Dvě&nbsp;cesty k výběru podle ceny</h2>",
                                    "Dvě cesty k výběru podle ceny"))

if __name__ == "__main__":
    unittest.main()
