"""The postwrite diagnostic must remain read-only and bounded."""
import unittest
from unittest.mock import patch

from scripts import xfit_7363_readonly_diagnostic as d


class ReadonlyDiagnosticTests(unittest.TestCase):
    def test_fingerprint_identifies_exact_anchor_not_plain_text(self):
        source = "<p>" + d.CFG.target + "</p>" * 5
        post = {"id": d.CFG.post_id, "slug": d.CFG.slug,
                "status": "publish", "content": {"raw": source},
                "modified_gmt": "2026-11-15T14:00:00"}
        self.assertFalse(d.fingerprint(post)["target_anchor_present"])
        post["content"]["raw"] = '<a href="' + d.CFG.target + '">Srovnání</a>'
        self.assertTrue(d.fingerprint(post)["target_anchor_present"])

    def test_main_uses_get_only_even_if_source_has_not_changed(self):
        post = {"id": d.CFG.post_id, "slug": d.CFG.slug,
                "status": "publish", "content": {"raw": "<p>Existing text</p>"},
                "modified_gmt": "2026-11-15T14:00:00"}
        with patch.object(d, "normalized_base", return_value="https://xfit.cz"), \
             patch.object(d, "wp_request", side_effect=[post, post, []]) as getter, \
             patch.object(d, "public_verified", return_value=False):
            d.main()
        self.assertEqual(getter.call_count, 3)
        for call in getter.call_args_list:
            self.assertNotIn("payload", call.kwargs)


if __name__ == "__main__":
    unittest.main()
