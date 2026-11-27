import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from scripts.xfit_drinkware_comparison import build_document
from scripts.xfit_drinkware_refresh import splice, segments, START, END
from scripts.wp_publish import MARKER, PublishError
from test_drinkware_comparison import BASE, SAMPLE, catalog, row


def source(price=249):
    data = catalog(row(1, "Shaker A", price, path="a"),
                   row(2, "Šejkr B", 399, path="b"), row(3, "Láhev C", 75, path="c"))
    data["fetched_at_utc"] = datetime.now(timezone.utc).isoformat()
    return build_document(data, BASE, SAMPLE)["content"]


class DrinkwareRefreshTests(unittest.TestCase):
    def test_only_owned_dynamic_sections_change_and_editorial_html_survives(self):
        old = MARKER + "\n" + source()
        old = old.replace(END, END + '\n<p>Redakční doplněk beze změny.</p>')
        new = source(259)
        changed = splice(old, new)
        self.assertIn("259,00 Kč", changed)
        self.assertNotIn("249,00 Kč", changed)
        self.assertIn("<p>Redakční doplněk beze změny.</p>", changed)
        (od1, od2), (ob1, ob2) = segments(old)
        (nd1, nd2), (nb1, nb2) = segments(changed)
        self.assertEqual(old[:od1], changed[:nd1])
        self.assertEqual(old[od2:ob1], changed[nd2:nb1])
        self.assertEqual(old[ob2:], changed[nb2:])

    def test_same_catalog_same_day_is_noop(self):
        body = source()
        old = MARKER + "\n" + body
        self.assertEqual(splice(old, body), old)

    def test_missing_duplicate_boundaries_or_unowned_source_fail(self):
        old = MARKER + "\n" + source()
        new = source(259)
        for invalid in (old.replace(MARKER, ""), old.replace(START, ""),
                        old.replace(END, END + END),
                        old.replace('class="xfit-feed-retrieval"', 'class="other"'),
                        old.replace('class="xfit-product-card"', 'class="other"')):
            with self.subTest(sample=invalid[:80]), self.assertRaises(PublishError):
                splice(invalid, new)

if __name__ == "__main__":
    unittest.main()
