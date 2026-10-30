import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError
from scripts.wp_publish import wp_request, PublishError

class WordPressRetryTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict("os.environ", {"WP_USERNAME":"test-user","WP_APP_PASSWORD":"test-password"})
        self.env.start()
    def tearDown(self):
        self.env.stop()
    def test_get_retries_safe_transient_handshake_failure(self):
        good=io.BytesIO(b'{"id":6440}')
        with patch("scripts.wp_publish.time.sleep") as delay, patch(
            "scripts.wp_publish.urllib.request.urlopen",
            side_effect=[URLError("ssl handshake timed out"), good]
        ) as fetch:
            result=wp_request("https://xfit.cz","posts/6440")
        self.assertEqual(result["id"],6440)
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(delay.call_count,1)
    def test_post_does_not_retry_after_timeout(self):
        with patch("scripts.wp_publish.time.sleep") as delay, patch(
            "scripts.wp_publish.urllib.request.urlopen",
            side_effect=URLError("ssl handshake timed out")
        ) as fetch:
            with self.assertRaises(PublishError):
                wp_request("https://xfit.cz","posts/6440",payload={"title":"test"})
        self.assertEqual(fetch.call_count,1)
        delay.assert_not_called()
    def test_get_gives_up_after_three_errors(self):
        with patch("scripts.wp_publish.time.sleep") as delay, patch(
            "scripts.wp_publish.urllib.request.urlopen",
            side_effect=URLError("ssl handshake timed out")
        ) as fetch:
            with self.assertRaises(PublishError):
                wp_request("https://xfit.cz","posts/6440")
        self.assertEqual(fetch.call_count,3)
        self.assertEqual(delay.call_count,2)
if __name__=="__main__":unittest.main()
