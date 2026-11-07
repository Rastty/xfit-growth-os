"""Expiry-proof source dates for real product comparisons; no fake freshness."""
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from scripts.xfit_catalog_retrieval import (
    verified_catalog_fetch_time, catalog_retrieval_notice
)
from scripts.wp_publish import PublishError
from scripts.xfit_creatine_guide import build_document as creatine
from scripts.xfit_whey_guide import build_document as whey

UTC = timezone.utc
EXAMPLE_NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
BASE = ("https://www.namaximum.cz/?utm_medium=affiliate"
        "&utm_campaign=affial.com&utm_source=pap&a_aid=TEST&a_bid=TEST")
SAMPLE = ("https://www.namaximum.cz/kategorie/kreatin/creatine-creapure"
          "?variant=392&utm_medium=affiliate&utm_campaign=affial.com"
          "&utm_source=pap&a_aid=TEST&a_bid=TEST")


def item(ident, title, category, price):
    return {
        "id": str(ident), "title": title, "price_czk": price, "category": category,
        "source_url": f"https://www.namaximum.cz/p/example?variant={ident}",
        "merchant": "NaMaximum.cz", "ean":str(ident),
    }


class CatalogRetrievalTests(TestCase):
    def test_real_time_is_utc_and_local_date_is_correct(self):
        stamp = "2026-11-07T11:55:00+00:00"
        observed = verified_catalog_fetch_time(
            {"fetched_at_utc":stamp}, now=EXAMPLE_NOW, required=True
        )
        self.assertEqual(observed.isoformat(), stamp)
        html = catalog_retrieval_notice(
            {"fetched_at_utc":stamp}, now=EXAMPLE_NOW
        )
        self.assertIn("7. 11. 2026", html)
        self.assertIn("XML katalog NaMaximum.cz", html)
        self.assertIn("nikoli okamžik změny ceny", html)
        self.assertIn("Aktuální cenu, složení a dostupnost ověřte", html)
        self.assertNotIn("a_aid", html)
        self.assertNotIn("11:55", html)

    def test_cross_midnight_prague_uses_local_day_not_utc_day(self):
        t = datetime(2026, 11, 7, 23, 40, tzinfo=UTC)
        value = catalog_retrieval_notice(
            {"fetched_at_utc":"2026-11-07T23:35:00Z"}, now=t
        )
        self.assertIn("8. 11. 2026", value)

    def test_missing_time_is_only_allowed_for_synthetic_builders(self):
        self.assertEqual(catalog_retrieval_notice({}), "")
        with self.assertRaises(PublishError):
            verified_catalog_fetch_time({}, now=EXAMPLE_NOW, required=True)

    def test_stale_future_naive_nonutc_and_invalid_are_rejected(self):
        bad = (
            "2026-11-07T07:59:59Z",  # over 4 hours old
            "2026-11-07T12:05:01Z",  # > five minutes in future
            "2026-11-07T12:00:00",  # no timezone
            "2026-11-07T12:00:00+01:00",  # non-UTC offset
            "not-a-date",
            "2026-11-07T09:55:00-03:00",
            42,
            "X"*100,
        )
        for value in bad:
            with self.subTest(value=str(value)[:20]), self.assertRaises(PublishError):
                verified_catalog_fetch_time(
                    {"fetched_at_utc":value}, now=EXAMPLE_NOW, required=True
                )
        with self.assertRaises(PublishError):
            verified_catalog_fetch_time(
                {"fetched_at_utc":"2026-11-07T12:00:00Z"},
                now=datetime(2026, 11, 7, 12, 0),
                required=True
            )

    def test_timestamp_unchanged_same_local_date_to_avoid_repeat_writes(self):
        morning = catalog_retrieval_notice(
            {"fetched_at_utc":"2026-11-07T09:00:00Z"},
            now=datetime(2026,11,7,9,2,tzinfo=UTC))
        afternoon = catalog_retrieval_notice(
            {"fetched_at_utc":"2026-11-07T13:00:00Z"},
            now=datetime(2026,11,7,13,2,tzinfo=UTC))
        self.assertEqual(morning, afternoon)

    def test_live_like_guides_render_only_source_bound_dates(self):
        examples = [
            (creatine, [
                item(392,"Creatine Pure Creapure 1kg","Kreatin",900),
                item(393,"Creatine Monohydrate 500g","Kreatin",430),
                item(394,"Creatine Monohydrate 250g","Kreatin",270),
            ]),
            (whey, [
                item(482,"Whey WPC 1kg","Syrovátkové proteiny",700),
                item(483,"Whey Isolate 750g","Syrovátkové proteiny",1100),
                item(484,"Whey Concentrate 500g","Syrovátkové proteiny",450),
            ]),
        ]
        with patch("scripts.xfit_catalog_retrieval.datetime") as clock:
            clock.now.return_value = EXAMPLE_NOW
            for builder, products in examples:
                with self.subTest(builder=builder.__name__):
                    catalog={
                        "fetched_at_utc":"2026-11-07T11:58:00Z",
                        "merchant":"namaximum.cz",
                        "merchant_match":True,
                        "products":products,
                    }
                    html = builder(catalog, BASE, SAMPLE)["content"]
                    self.assertIn('class="xfit-feed-retrieval"', html)
                    self.assertEqual(html.count('class="xfit-feed-retrieval"'),1)
                    self.assertIn("7. 11. 2026", html)
                    self.assertIn("Datum označuje načtení katalogu", html)


if __name__ == "__main__":
    import unittest
    unittest.main()
