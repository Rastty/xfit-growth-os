"""Public XFIT indexability checks are read-only and never claim GSC indexing."""
import unittest
from scripts import xfit_indexability_preflight as probe


def page(slug, *, canonical=True, meta="", links=()):
    head = (
        "<head>" +
        ('<link rel="canonical" href="https://xfit.cz/' + slug + '/">' if canonical else "") +
        ('<meta name="robots" content="' + meta + '">' if meta else "") +
        "</head>"
    )
    anchors = "".join('<a href="https://xfit.cz/' + link + '/">See page</a>'
                      for link in links)
    return "<html>" + head + "<body><h1>Praktický průvodce</h1><p>" + (
        "Užitečný text a metodika ověřitelných doporučení. " * 10
    ) + "</p>" + anchors + "</body></html>"


class TechnicalReadOnlyTests(unittest.TestCase):
    def test_normal_self_canonical_and_no_noindex(self):
        row = probe.assess_html(
            probe.OWNED[0], page(probe.OWNED[0],
                                links=(probe.OWNED[1],)),
            {"x-robots-tag": ""})
        self.assertEqual(row["html_access"], "PUBLIC_HTTP_200")
        self.assertEqual(row["canonical_status"], "SELF_CANONICAL")
        self.assertEqual(row["robots_meta_or_header"], "NO_NOINDEX_DIRECTIVE_OBSERVED")
        self.assertIn(probe.SITE + "/" + probe.OWNED[1] + "/",
                      row["_internal_links"])
        self.assertEqual(row["visible_h1_count"], 1)

    def test_noindex_in_meta_and_x_robots_header_is_detected(self):
        slug = probe.OWNED[1]
        self.assertEqual(probe.assess_html(
            slug, page(slug, meta="noindex, follow")
        )["robots_meta_or_header"], "NOINDEX_DIRECTIVE_OBSERVED")
        self.assertEqual(probe.assess_html(
            slug, page(slug), {"x-robots-tag": "noindex, nofollow"}
        )["robots_meta_or_header"], "NOINDEX_DIRECTIVE_OBSERVED")
        self.assertFalse(probe.has_noindex(["index, follow"]))

    def test_wrong_canonical_and_missing_canonical_are_distinguished(self):
        slug = probe.OWNED[2]
        none = probe.assess_html(slug, page(slug, canonical=False))
        self.assertEqual(none["canonical_status"], "NO_CANONICAL_TAG_OBSERVED")
        changed = page(slug).replace(
            'href="https://xfit.cz/' + slug + '/"',
            'href="https://xfit.cz/different-article/"')
        self.assertEqual(probe.assess_html(
            slug, changed)["canonical_status"], "DIFFERENT_OR_UNTRUSTED_CANONICAL")
        both = page(slug).replace("</head>", (
            '<link rel="canonical" href="https://xfit.cz/another/">'
            "</head>"))
        self.assertEqual(probe.assess_html(
            slug, both)["canonical_status"], "MULTIPLE_CANONICAL_TAGS")

    def test_exact_owned_url_rejects_cross_host_query_and_unsafe_redirect(self):
        slug = probe.OWNED[2]
        good = "https://xfit.cz/" + slug + "/"
        self.assertTrue(probe.exact_owned_url(good, slug))
        for bad in ("http://xfit.cz/"+slug+"/", "https://evil.example/"+slug+"/",
                    "https://xfit.cz/"+slug+"/?sort=new",
                    "https://xfit.cz:443/"+slug+"/",
                    "https://xfit.cz/other/"):
            self.assertFalse(probe.exact_owned_url(bad, slug))

    def test_readonly_report_never_sends_full_html_or_affiliate_links(self):
        expected = {slug: page(slug, links=probe.OWNED)
                    for slug in probe.OWNED + probe.REFERERS}
        expected["robots.txt"] = "User-agent: *\nDisallow: /wp-admin/"
        expected["wp-sitemap.xml"] = '<sitemapindex><sitemap><loc>https://xfit.cz/wp-sitemap-posts-post-1.xml</loc></sitemap></sitemapindex>'
        expected["sitemap_index.xml"] = "<urlset><url><loc>https://xfit.cz/example/</loc></url></urlset>"
        expected["sitemap.xml"] = "<sitemapindex></sitemapindex>"
        calls = []
        def reader(path, **kwargs):
            calls.append(path)
            return expected[path.lstrip("/").rstrip("/")], {"Content-Type": "text/html"}
        result = probe.run(reader=reader)
        self.assertEqual(result["page_count"], 6)
        self.assertEqual(len(calls), 11)
        self.assertEqual(result["wordpress_writes"], 0)
        self.assertEqual(result["plugins_installed"], 0)
        self.assertEqual(result["seo_mutations"], 0)
        self.assertEqual(result["pages"][0]["observed_internal_inlinks_from_seven_reviewed_articles"], 7)
        self.assertEqual(result["infrastructure"]["wordpress_sitemap"], "ACCESSIBLE_XML")
        serialized = str(result)
        self.assertNotIn("<html>", serialized)
        self.assertNotIn("Disallow: /wp-admin", serialized)
        self.assertNotIn("<loc>", serialized)

    def test_robots_declared_same_origin_sitemap_is_checked_but_not_other_sites(self):
        text = (
            "User-agent: *\nDisallow: /wp-admin/\n"
            "Sitemap: https://xfit.cz/sitemaps/sitemap-main.xml\n"
            "Sitemap: https://evil.example/leak.xml\n"
            "Sitemap: https://xfit.cz/private.xml?token=secret\n"
        )
        evidence = probe.robots_evidence(text)
        self.assertEqual(evidence["safe_same_origin_sitemap_paths"],
                         ["/sitemaps/sitemap-main.xml"])
        self.assertFalse(evidence["observed_general_or_googlebot_root_disallow"])
        self.assertTrue(probe.robots_evidence(
            "User-agent: Googlebot\nDisallow: /\n"
        )["observed_general_or_googlebot_root_disallow"])

        paths = {slug: page(slug) for slug in probe.OWNED + probe.REFERERS}
        paths.update({
            "robots.txt": text,
            "wp-sitemap.xml": "<html>Not XML</html>",
            "sitemap_index.xml": "<html>Not XML</html>",
            "sitemap.xml": "<html>Not XML</html>",
            "sitemaps/sitemap-main.xml": "<sitemapindex></sitemapindex>",
        })
        seen = []
        def reader(path, **kwargs):
            seen.append(path)
            return paths[path.strip("/")], {}
        report = probe.run(reader=reader)
        self.assertEqual(report["declared_sitemap_probes"], {
            "/sitemaps/sitemap-main.xml": "ACCESSIBLE_XML"})
        self.assertEqual(report["infrastructure"]["generic_sitemap"],
                         "UNKNOWN_UNEXPECTED_RESPONSE")
        self.assertNotIn("evil.example", str(report))
        self.assertNotIn("token=secret", str(report))
        self.assertEqual(report["wordpress_writes"], 0)
        self.assertEqual(len(seen), 12)

    def test_failed_public_fetch_is_unknown_not_unindexed(self):
        def reader(path, **kwargs):
            if path.startswith("/xfit-os-"):
                raise OSError("untrusted token in remote exception")
            if path.startswith("/jaky-"):
                return page(probe.REFERERS[0]), {}
            raise OSError("unavailable")
        result = probe.run(reader=reader)
        self.assertEqual(result["pages"][0]["html_access"], "UNKNOWN_FETCH")
        self.assertEqual(result["pages"][0]["robots_meta_or_header"], "UNKNOWN")
        self.assertEqual(result["infrastructure"]["robots_txt"], "UNKNOWN_UNAVAILABLE")
        self.assertNotIn("token", str(result))

    def test_unknown_owner_slug_cannot_enter_assessment(self):
        with self.assertRaises(ValueError):
            probe.assess_html("not-owned", page(probe.OWNED[0]))


    def test_sitemap_failure_class_preserves_exact_status_without_private_detail(self):
        from urllib.error import HTTPError
        for code, expected in ((301, "HTTP_REDIRECT_301"),
                               (302, "HTTP_REDIRECT_302"),
                               (403, "HTTP_403"),
                               (404, "HTTP_404"),
                               (429, "HTTP_429"),
                               (503, "HTTP_503"),
                               (418, "HTTP_OTHER")):
            with self.subTest(status=code):
                err = HTTPError("https://xfit.cz/wp-sitemap.xml?secret=PRIVATE",
                                code, "untrusted PRIVATE", {}, None)
                self.assertEqual(probe.sitemap_fetch_failure(err), expected)
                self.assertNotIn("PRIVATE", probe.sitemap_fetch_failure(err))
        self.assertEqual(probe.sitemap_fetch_failure(OSError("PRIVATE")),
                         "UNKNOWN_UNAVAILABLE")

    def test_declared_sitemap_http_404_is_not_conflated_with_network_error(self):
        from urllib.error import HTTPError
        seen = []
        def reader(path, **kwargs):
            seen.append(path)
            if path == "/robots.txt":
                return ("User-agent: *\nSitemap: https://xfit.cz/wp-sitemap.xml\n", {})
            if path == "/wp-sitemap.xml":
                raise HTTPError("https://xfit.cz/wp-sitemap.xml", 404,
                                "Not Found", {}, None)
            if path in ("/sitemap_index.xml", "/sitemap.xml"):
                raise OSError("network outage")
            slug = path.strip("/")
            return page(slug), {}
        report = probe.run(reader=reader)
        self.assertEqual(report["infrastructure"]["wordpress_sitemap"], "HTTP_404")
        self.assertEqual(report["infrastructure"]["seo_sitemap_index"],
                         "UNKNOWN_UNAVAILABLE")
        self.assertEqual(report["declared_sitemap_probes"]["/wp-sitemap.xml"],
                         "HTTP_404")
        self.assertEqual(seen.count("/wp-sitemap.xml"), 1)
        self.assertEqual(report["seo_mutations"], 0)
        self.assertNotIn("Not Found", str(report))

    def test_sitemap_redirects_are_never_followed(self):
        handler = probe.NoRedirect()
        self.assertIsNone(handler.redirect_request(
            None, None, 302, "redirect", {},
            "https://untrusted.example/offsite.xml"))

if __name__ == "__main__":
    unittest.main()
