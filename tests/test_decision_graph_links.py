"""Live-url-backed internal routing contract for XFIT decision funnels.

These tests do not claim search rank or conversion gains. They ensure that
high-intent evergreen pages hand readers to the appropriate next decision
instead of only presenting a sale CTA, and that canonical links stay stable.
"""
import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class InternalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))


def body(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return doc["content"]


def links(html):
    parser = InternalLinks()
    parser.feed(html)
    return parser.links


class XfitDecisionGraphTests(unittest.TestCase):
    BEGINNER = "content/ready/xfit-os-doplnky-pro-zacatecniky.json"
    CHOOSER = "content/ready/xfit-os-kreatin-nebo-protein.json"
    PROTEIN = "content/ready/xfit-os-protein-guide.json"

    def test_beginner_page_hands_off_to_neutral_chooser(self):
        source = body(self.BEGINNER)
        self.assertIn("možnost nekupovat nic", source)
        self.assertIn("https://xfit.cz/xfit-os-kreatin-nebo-protein/", links(source))
        self.assertLess(source.index("rozhodovacího průvodce kreatin versus protein"),
                        source.index('id="zacatecnik-rozhodnuti"'))

    def test_chooser_has_fair_price_method_before_product_list(self):
        source = body(self.CHOOSER)
        urls = links(source)
        self.assertIn("https://xfit.cz/xfit-os-cena-proteinu-podle-etikety/", urls)
        self.assertIn("https://xfit.cz/xfit-os-kreatin-poradce/", urls)
        self.assertIn("https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/", urls)
        self.assertIn("https://xfit.cz/xfit-os-doplnky-pro-zacatecniky/", urls)
        self.assertIn("cena za 100 g čistých bílkovin", source)
        self.assertIn("protein kupovat nemusíte", source)

    def test_core_internal_links_use_canonical_https(self):
        for source_path in (self.BEGINNER, self.CHOOSER, self.PROTEIN):
            with self.subTest(source=source_path):
                for url in links(body(source_path)):
                    if url.startswith("#"):
                        continue
                    parsed = urlsplit(url)
                    self.assertEqual(parsed.scheme, "https")
                    self.assertTrue(parsed.hostname)
                    if parsed.hostname in ("xfit.cz", "www.xfit.cz"):
                        self.assertEqual(parsed.hostname, "xfit.cz")
                        self.assertFalse(parsed.query)
                        self.assertFalse(parsed.fragment)
                        self.assertTrue(parsed.path.endswith("/"))


if __name__ == "__main__":
    unittest.main()
