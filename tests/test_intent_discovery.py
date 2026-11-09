"""Two source-backed old posts are not rewritten until exact live link evidence."""
import unittest

from scripts import xfit_intent_discovery as discovery


def post(slug, body, post_id=1723, url_host="xfit.cz"):
    return {
        "id": post_id,
        "slug": slug,
        "status": "publish",
        "link": "https://" + url_host + "/" + slug + "/",
        "content": {"raw": body},
    }


class LegacyRoutingDiscoveryTests(unittest.TestCase):
    def test_exact_url_in_plain_text_is_not_real_internal_link(self):
        slug, target, _ = discovery.PRIORITY_LEGACY[0]
        body = "<p>Long useful public article on creatine and training.</p>" * 24
        body += "<p>Example printed address: " + target + "</p>"
        calls = []
        def fake(base, path, payload=None):
            self.assertIsNone(payload)
            calls.append(path)
            self.assertIn("context=edit", path)
            if "slug=" + slug in path:
                return [post(slug, body)]
            return []
        result = discovery.inspect_priority(request=fake)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result[0]["state"], "SOURCE_VERIFIED")
        self.assertEqual(result[0]["target_already_linked"], False)
        self.assertEqual(result[0]["next_action"],
                         "EDITORIAL_REVIEW_BEFORE_ONE_POST")
        self.assertEqual(result[1]["state"], "UNKNOWN_NO_VERIFIED_SOURCE")
        self.assertEqual(result[1]["target_already_linked"], None)
        self.assertNotIn(body, str(result))
        self.assertTrue(all(not item.get("modified_wordpress", False) for item in result))

    def test_only_exact_anchor_counts_and_is_idempotent(self):
        slug,target,_ = discovery.PRIORITY_LEGACY[1]
        body = ("<p>Useful text.</p>" * 22 +
                '<a href="' + target + '">Podrobnosti o bezpečnosti</a>')
        def fake(base, path):
            if "slug=" + slug in path:
                return [post(slug, body, 2026)]
            return []
        result = discovery.inspect_priority(request=fake)
        self.assertTrue(result[1]["target_already_linked"])
        self.assertEqual(result[1]["next_action"], "ALREADY_LINKED")
        self.assertEqual(result[1]["wp_post_id"], 2026)

    def test_invalid_identity_is_unknown_and_never_eligible(self):
        slug,target,_ = discovery.PRIORITY_LEGACY[0]
        body = "<p>Evidence.</p>" * 40
        for changed in (
            {"link": "https://evil.example/" + slug + "/"},
            {"link": "http://xfit.cz/" + slug + "/"},
            {"slug": "wrong-slug"},
            {"status": "draft"},
            {"content": {"raw": ""}},
        ):
            with self.subTest(changed=changed):
                doc = post(slug,body)
                doc.update(changed)
                def fake(base,path):
                    return [doc] if "slug=" + slug in path else []
                result = discovery.inspect_priority(request=fake)
                self.assertEqual(result[0]["state"],
                                 "UNKNOWN_NO_VERIFIED_SOURCE")
                self.assertNotEqual(result[0]["next_action"],
                                    "EDITORIAL_REVIEW_BEFORE_ONE_POST")

    def test_api_failure_remains_unknown_without_echoing_exception(self):
        def broken(base,path):
            raise ValueError("SECRET or private content")
        result = discovery.inspect_priority(request=broken)
        self.assertEqual(len(result), 2)
        self.assertNotIn("SECRET", str(result))
        self.assertTrue(all(x["next_action"]=="RECHECK_SOURCE" for x in result))


if __name__=="__main__":
    unittest.main()
