import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request

from scripts.xfit_merchant_destination_probe import (
    MerchantOnlyRedirect, STATUS_AVAILABLE, STATUS_REVIEW, STATUS_UNKNOWN,
    card_destinations, clean_product_destination, diagnose,
    probe_clean_destination,
)

BASE = ("https://www.namaximum.cz/?utm_medium=affiliate"
        "&utm_campaign=affial.com&utm_source=pap"
        "&a_aid=TESTID&a_bid=TESTCAMPAIGN")


def tracked(ident):
    return (f"https://www.namaximum.cz/kategorie/protein/example?variant={ident}"
            "&utm_medium=affiliate&utm_campaign=affial.com&utm_source=pap"
            "&a_aid=TESTID&a_bid=TESTCAMPAIGN&data1=xfit&data2=creatine")


def page(engine, ids):
    return "".join(
        f'<article class="xfit-product-card"><a href="{tracked(ident).replace("&", "&amp;")}" '
        f'rel="sponsored nofollow" data-xfit-engine="{engine}" '
        f'data-xfit-partner="namaximum" data-xfit-product-id="{ident}">'
        'Ověřit cenu a dostupnost</a></article>'
        for ident in ids
    )


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request.full_url)
        assert timeout == 9
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class MerchantDestinationProbeTests(unittest.TestCase):
    def test_strips_every_tracking_parameter_before_network_request(self):
        html = page("creatine", [392, 393])
        urls = card_destinations(html, "xfit-os-kreatin-poradce", BASE)
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0],
                         "https://www.namaximum.cz/kategorie/protein/example?variant=392")
        for url in urls:
            self.assertNotIn("a_aid", url)
            self.assertNotIn("utm", url)
            self.assertNotIn("data1", url)
            self.assertNotIn("TESTID", url)

    def test_rejects_variant_mismatch_and_unapproved_hosts(self):
        with self.assertRaisesRegex(ValueError, "unverified_merchant_variant"):
            clean_product_destination(tracked(392), "393", "TESTID", "TESTCAMPAIGN")
        with self.assertRaises(ValueError):
            clean_product_destination(tracked(392).replace("www.namaximum.cz", "evil.example"),
                                      "392", "TESTID", "TESTCAMPAIGN")
        with self.assertRaises(ValueError):
            probe_clean_destination("https://evil.example/product?variant=392")
        with self.assertRaises(ValueError):
            probe_clean_destination("https://www.namaximum.cz/product?variant=392&a_aid=TESTID")
        with self.assertRaises(ValueError):
            probe_clean_destination("https://www.namaximum.cz/product?variant=392&variant=393")

    def test_bounded_aggregate_never_leaks_merchant_urls_or_product_ids(self):
        pages = {
            "xfit-os-kreatin-poradce": page("creatine", [392, 393]),
            "xfit-os-syrovatkovy-protein-porovnani": page("whey", [394, 395]),
        }
        urls_seen = []

        def stub(url):
            urls_seen.append(url)
            return STATUS_REVIEW if "variant=393" in url else STATUS_AVAILABLE

        result = diagnose(pages, BASE, probe=stub)
        self.assertEqual(len(urls_seen), 4)
        self.assertEqual(result[0]["statuses"], {STATUS_AVAILABLE: 1, STATUS_REVIEW: 1})
        self.assertEqual(result[1]["statuses"], {STATUS_AVAILABLE: 2})
        self.assertNotIn("variant=", str(result))
        self.assertNotIn("TESTID", str(result))

    def test_never_follows_external_or_changed_product_redirects(self):
        handler = MerchantOnlyRedirect()
        original = Request("https://www.namaximum.cz/p/x?variant=392")
        for url in (
            "https://evil.example/product?variant=392",
            "https://www.namaximum.cz/p/y?variant=392",
            "https://www.namaximum.cz/p/x?variant=393",
            "https://www.namaximum.cz/p/x?variant=392&a_aid=TESTID",
            "http://www.namaximum.cz/p/x?variant=392",
        ):
            with self.subTest(url=url):
                self.assertIsNone(handler.redirect_request(
                    original, None, 302, "Moved", {}, url))

    def test_merchant_errors_are_review_or_unknown_not_false_stock_claims(self):
        url = "https://www.namaximum.cz/p/x?variant=392"
        for result, expected in (
            (Response(), STATUS_AVAILABLE),
            (HTTPError(url, 404, "Not Found", {}, None), STATUS_REVIEW),
            (HTTPError(url, 410, "Gone", {}, None), STATUS_REVIEW),
            (HTTPError(url, 403, "Bot blocked", {}, None), STATUS_UNKNOWN),
            (HTTPError(url, 503, "Unavailable", {}, None), STATUS_UNKNOWN),
            (URLError("timeout"), STATUS_UNKNOWN),
        ):
            with self.subTest(expected=expected):
                opener = FakeOpener(result)
                self.assertEqual(probe_clean_destination(url, opener), expected)
                self.assertEqual(opener.requests, [url])


if __name__ == "__main__":
    unittest.main()
