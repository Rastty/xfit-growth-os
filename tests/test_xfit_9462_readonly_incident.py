"""No-write incident evidence, including a changed revision and cache drift."""
import contextlib
from io import StringIO
import json
import unittest
from unittest.mock import patch

from scripts import xfit_9462_readonly_incident as d
from tests.test_japanese_exercise_9462 import post


class IncidentTests(unittest.TestCase):
    def test_fingerprint_matches_exact_reviewed_legacy(self):
        value = d.fingerprint(post())
        self.assertTrue(value["old_reviewed_source"])
        self.assertFalse(value["new_marker"])

    def test_changed_content_is_distinguished_from_old(self):
        value = d.fingerprint(post(d.article.revision()))
        self.assertTrue(value["new_revision_matches"])
        self.assertTrue(value["new_marker"])
        self.assertFalse(value["old_reviewed_source"])

    def test_probe_never_sends_payload_or_post(self):
        output = StringIO()
        with patch.object(d, "normalized_base", return_value="https://xfit.cz"), \
                patch.object(d, "wp_request", side_effect=[post(), post(), []]) as wp, \
                patch.object(d, "public_fingerprint", return_value={"new_marker_rest": False}), \
                contextlib.redirect_stdout(output):
            d.run()
        saved = json.loads(output.getvalue())
        self.assertEqual(saved["remote_post_attempts"], 0)
        self.assertTrue(saved["same_auth_source"])
        self.assertEqual(wp.call_count, 3)
        self.assertTrue(all("payload" not in c.kwargs for c in wp.call_args_list))
        self.assertIn("xfit_probe=", wp.call_args_list[1].args[1])


if __name__ == "__main__":
    unittest.main()
