import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from scripts.xfit_public_freshness import (
    TARGETS, owns_public_url, visible_has, probe, product_card_texts,
    typography_key, public_get, cta_metadata, metadata_readiness,
    catalog_retrieval_readiness,
)
from scripts.wp_publish import PublishError
from scripts.xfit_beginner_hub_choice_onepost import NEW_NAV, CHOICES
from scripts.xfit_public_freshness import hub_choice_readiness


def post(slug, post_id, marker):
    source = "<!-- xfit-growth-os:v1 -->\n<h2>" + marker + "</h2>"
    if slug in ("xfit-os-kreatin-poradce", "xfit-os-syrovatkovy-protein-porovnani"):
        checked = datetime.now(ZoneInfo("Europe/Prague")).date()
        display = f"{checked.day}. {checked.month}. {checked.year}"
        source += (
            '<h2 id="xfit-price-tradeoff">Rozpočet a porovnání balení</h2>'
            '<p data-xfit-tradeoff="upfront">Nejnižší výdaj při nákupu: '
            'menší balení vyžaduje méně peněz při prvním nákupu.</p>'
            '<p data-xfit-tradeoff="unit">Nejnižší cena za 100 g prášku: '
            'větší balení může mít lepší jednotkovou cenu.</p>'
            '<p data-xfit-tradeoff="difference">Co to znamená pro rozpočet? '
            'Větší balení může stát dnes více; porovnejte skutečnou spotřebu.</p>'
            '<p class="xfit-feed-retrieval"><small>'
            '<strong>Kdy jsme data nabídky načetli:</strong> ' + display +
            ' (produktový XML katalog NaMaximum.cz). '
            'Datum označuje načtení katalogu, nikoli okamžik změny ceny '
            'u prodejce. Aktuální cenu, složení a dostupnost ověřte '
            'v obchodě.</small></p>'
            "<article class='xfit-product-card'><h3>Produkt A</h3><p>Cena: 200,00 Kč</p>"
            "<a rel='sponsored nofollow' href='https://www.namaximum.cz/produkt-a"
            "?utm_medium=affiliate&a_aid=demo&a_bid=test'>Zobrazit</a></article>"
            "<article class='xfit-product-card'><h3>Produkt B</h3><p>Cena: 300,00 Kč</p>"
            "<a rel='sponsored nofollow' href='https://www.namaximum.cz/produkt-b"
            "?utm_medium=affiliate&a_aid=demo&a_bid=test'>Zobrazit</a></article>")
    return {"id":post_id, "slug":slug, "status":"publish",
            "content":{"raw":source},
            "link":"https://xfit.cz/"+slug+"/"}


class PublicFreshnessTests(unittest.TestCase):
    def test_released_beginner_hero_is_current_and_four_exact_choices(self):
        slug, ident, _ = TARGETS[0]
        original = {
            "id":ident, "slug":slug, "status":"publish",
            "link":"https://xfit.cz/"+slug+"/",
            "content":{"raw":"<!-- xfit-growth-os:v1 -->\\n"+NEW_NAV+
                "<p>Further valid original educational copy</p>"},
        }
        public = "<html><head><title>Začátečníci</title></head><body>" + (
            original["content"]["raw"]) + "</body></html>"
        result = probe(TARGETS[0], read_post=lambda _:original,
                       read_public=lambda _: (public,{"Age":"0"}))
        self.assertEqual(result["status"], "PUBLIC_FRESH")
        self.assertEqual(result["hub_choice_stage"], "PUBLIC_HUB_CHOICES_VERIFIED")
        self.assertEqual(result["source_hub_choice_link_count"], 4)
        self.assertEqual(result["public_hub_choice_link_count"], 4)
        self.assertEqual(tuple(CHOICES), (
            "#zacatecnik-rozhodnuti",
            "https://xfit.cz/xfit-os-syrovatkovy-protein-porovnani/",
            "https://xfit.cz/xfit-os-kreatin-poradce/",
            "https://xfit.cz/xfit-os-kreatin-nebo-protein/",
        ))
        self.assertNotIn("namaximum.cz", str(result))

    def test_released_hero_missing_link_or_old_cdn_is_not_fresh(self):
        slug, ident, _ = TARGETS[0]
        source = "<!-- xfit-growth-os:v1 -->\\n" + NEW_NAV
        original = {"id":ident,"slug":slug,"status":"publish",
                    "link":"https://xfit.cz/"+slug+"/",
                    "content":{"raw":source}}
        # Missing a single real source link is a publish/source problem.
        missing = dict(original)
        missing["content"]={"raw":source.replace(
            'href="https://xfit.cz/xfit-os-kreatin-poradce/"',
            'href="https://xfit.cz/unreviewed/"', 1)}
        no_source = probe(TARGETS[0],read_post=lambda _:missing,
                          read_public=lambda _:("<html>"+source+"</html>",{}))
        self.assertEqual(no_source["status"],"WP_SOURCE_INCOMPLETE")
        self.assertEqual(no_source["hub_choice_stage"],"SOURCE_HUB_CHOICES_INCOMPLETE")
        # Normal public response with old hero, or just the new heading,
        # cannot hide absent links even though source is approved.
        stale = source.replace(
            'href="https://xfit.cz/xfit-os-kreatin-poradce/"',
            'href="https://xfit.cz/unreviewed/"', 1)
        report = probe(TARGETS[0],read_post=lambda _:original,
                       read_public=lambda _:("<html>"+stale+"</html>",{}))
        self.assertEqual(report["status"],"PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertEqual(report["hub_choice_stage"],"PUBLIC_HUB_CHOICES_MISSING_OR_DIFFERENT")
        self.assertTrue(report["wp_source_has_target"])
        self.assertTrue(report["public_has_target"])
        self.assertNotIn("unreviewed",str(report))
        only_heading = ("<h2>Co potřebujete právě teď?</h2>" +
                        "".join('<a href="'+u+'">link</a>' for u in CHOICES))
        self.assertEqual(hub_choice_readiness(source,only_heading)["hub_choice_stage"],
                         "PUBLIC_HUB_CHOICES_MISSING_OR_DIFFERENT")

    def test_known_canonical_urls_only(self):
        self.assertTrue(owns_public_url("https://xfit.cz/xfit-os-kreatin-poradce/", "xfit-os-kreatin-poradce"))
        self.assertFalse(owns_public_url("https://external.example/xfit-os-kreatin-poradce/", "xfit-os-kreatin-poradce"))
        self.assertFalse(owns_public_url("https://xfit.cz/xfit-os-kreatin-poradce/?token=private", "xfit-os-kreatin-poradce"))

    def test_public_view_checks_edited_body_not_unchanged_title(self):
        target = TARGETS[2]
        original = post(*target)
        success = probe(target, read_post=lambda _:original,
                        read_public=lambda url:("<html><h1>Jak vybrat kreatin</h1>"+original["content"]["raw"]+"</html>",{"Age":"0"}))
        self.assertEqual(success["status"],"PUBLIC_FRESH")
        stale = probe(target, read_post=lambda _:original,
                      read_public=lambda url:("<html><h1>Jak vybrat kreatin</h1><p>Starý obsah</p></html>",{"Age":"720"}))
        self.assertEqual(stale["status"],"PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertTrue(stale["wp_source_has_target"])
        self.assertFalse(stale["public_has_target"])

    def test_new_equal_mass_block_cannot_disappear_behind_old_cache(self):
        from scripts.xfit_public_freshness import price_decision_readiness
        target = TARGETS[3]
        original = post(*target)
        current = original["content"]["raw"]
        fresh_extra = (
            '<p data-xfit-tradeoff="same-mass"><strong>Model stejné '
            'hmotnosti prášku:</strong> 2 menší balení po 1000 g '
            'by stála 1 758,00 Kč; jedno větší balení 2000 g stojí '
            '1 699,00 Kč. Rozdíl je 59,00 Kč. Tento model neověřuje '
            'stejné složení, trvanlivost po otevření ani cenu dopravy.</p>'
        )
        self.assertIn('data-xfit-tradeoff="difference"', current)
        current = current.replace(
            '</p><p class="xfit-feed-retrieval">',
            '</p>' + fresh_extra + '<p class="xfit-feed-retrieval">',
            1
        )
        self.assertIn('data-xfit-tradeoff="same-mass"', current)
        original["content"]["raw"] = current

        # Old edge/cache is still serving valid affiliate links, cards,
        # prices, feed date, and heading. Those do NOT prove new buyer copy.
        old_public = current.replace(fresh_extra, "")
        stale = probe(target, read_post=lambda _: original,
                      read_public=lambda _: ("<html>" + old_public + "</html>", {}))
        self.assertEqual(stale["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertTrue(stale["product_cards_match"])
        self.assertEqual(stale["catalog_retrieval_stage"], "PUBLIC_DATE_VERIFIED")
        self.assertEqual(stale["price_decision_stage"],
                         "PUBLIC_PRICE_DECISION_MISSING_OR_DIFFERENT")
        self.assertEqual(stale["source_decision_kinds"][-1], "same-mass")
        self.assertNotIn("same-mass", stale["public_decision_kinds"])
        self.assertEqual(stale["price_decision_first_difference"], 4)
        self.assertNotIn("1 758", str(stale))  # no raw price or affiliate leak

        fresh = probe(target, read_post=lambda _: original,
                      read_public=lambda _: ("<html>" + current + "</html>", {}))
        self.assertEqual(fresh["status"], "PUBLIC_FRESH")
        self.assertEqual(fresh["price_decision_stage"],
                         "PUBLIC_PRICE_DECISION_VERIFIED")
        self.assertTrue(fresh["price_decision_source_public_match"])

        equivalent = price_decision_readiness(
            current, current.replace("menší balení", "menší balení"))
        self.assertTrue(equivalent["price_decision_source_public_match"])

    def test_public_price_decision_drift_detected_without_card_drift(self):
        target = TARGETS[2]
        original = post(*target)
        current = original["content"]["raw"]
        altered = current.replace(
            "větší balení může mít lepší jednotkovou cenu",
            "větší balení je vždy nejlepší pro každého kupujícího")
        report = probe(target, read_post=lambda _: original,
                       read_public=lambda _: ("<html>" + altered + "</html>", {}))
        self.assertEqual(report["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertTrue(report["product_cards_match"])
        self.assertEqual(report["price_decision_first_difference"], 2)

    def test_missing_source_decision_is_not_a_valid_public_release(self):
        target = TARGETS[3]
        original = post(*target)
        source = original["content"]["raw"].replace(
            'data-xfit-tradeoff="unit"', 'data-xfit-tradeoff="untrusted"', 1)
        original["content"]["raw"] = source
        result = probe(target, read_post=lambda _: original,
                       read_public=lambda _: ("<html>" + source + "</html>", {}))
        self.assertEqual(result["status"], "WP_SOURCE_INCOMPLETE")
        self.assertEqual(result["price_decision_stage"],
                         "SOURCE_PRICE_DECISION_INCOMPLETE")

    def test_regular_cached_view_can_disagree_with_fresh_no_cache_without_mutation(self):
        target = TARGETS[3]
        original = post(*target)
        latest = original["content"]["raw"]
        same_mass = (
            '<p data-xfit-tradeoff="same-mass">Model stejné hmotnosti prášku: '
            '2 malá balení za 1 758,00 Kč proti jednomu velkému za 1 699,00 Kč; '
            'cenový rozdíl činí 59,00 Kč a neprokazuje stejné složení výrobků.</p>'
        )
        latest = latest.replace('<p class="xfit-feed-retrieval">',
                                same_mass + '<p class="xfit-feed-retrieval">')
        original["content"]["raw"] = latest
        older = latest.replace(same_mass, "")
        report = probe(
            target, read_post=lambda _: original,
            read_public_normal=lambda _: ("<html>" + older + "</html>",
                                          {"Cache-Control":"max-age=300", "Age":"89"}),
            read_public=lambda _: ("<html>" + latest + "</html>",
                                   {"Age":"0"}),
        )
        self.assertEqual(report["status"], "PUBLIC_CACHE_VIEW_DIVERGENCE")
        self.assertEqual(report["price_decision_stage"],
                         "PUBLIC_PRICE_DECISION_VERIFIED")
        self.assertTrue(report["product_cards_match"])
        self.assertEqual(report["ordinary_public_view_state"],
                         "ORDINARY_PUBLIC_VIEW_STALE_OR_DIFFERENT")
        self.assertEqual(report["ordinary_cache_headers"]["Age"], "89")
        self.assertNotIn("1 758", str(report))
        self.assertNotIn("namaximum.cz", str(report))

    def test_ordinary_view_is_explicitly_unknown_on_transport_failure(self):
        target = TARGETS[2]
        original = post(*target)
        body = original["content"]["raw"]
        result = probe(
            target, read_post=lambda _: original,
            read_public_normal=lambda _: (_ for _ in ()).throw(OSError("secret")),
            read_public=lambda _: ("<html>" + body + "</html>", {}),
        )
        self.assertEqual(result["status"], "PUBLIC_FRESH")
        self.assertEqual(result["ordinary_public_view_state"],
                         "ORDINARY_PUBLIC_READ_UNKNOWN")
        self.assertNotIn("secret", str(result))

    def test_regular_http_read_does_not_silently_request_cache_bypass(self):
        import io
        class Response(io.BytesIO):
            status = 200
            headers = {"Age":"1","Cache-Control":"max-age=300"}
            def geturl(self):
                return "https://xfit.cz/xfit-os-kreatin-poradce/"
        url = "https://xfit.cz/xfit-os-kreatin-poradce/"
        sent = []
        def fake_get(req, **kwargs):
            sent.append({key.lower(): val for key,val in req.header_items()})
            return Response(b"<html>test</html>")
        with patch("scripts.xfit_public_freshness.urllib.request.urlopen",
                   side_effect=fake_get):
            public_get(url, bypass_cache=False)
            public_get(url)
        self.assertNotIn("cache-control", sent[0])
        self.assertNotIn("pragma", sent[0])
        self.assertEqual(sent[1].get("cache-control"), "no-cache")
        self.assertEqual(sent[1].get("pragma"), "no-cache")

    def test_catalog_date_match_and_drift_are_evidence_not_just_price(self):
        target = TARGETS[2]
        original = post(*target)
        source = original["content"]["raw"]
        good = probe(target, read_post=lambda _:original,
                     read_public=lambda _:("<html>"+source+"</html>",{}))
        self.assertEqual(good["status"], "PUBLIC_FRESH")
        self.assertEqual(good["catalog_retrieval_stage"], "PUBLIC_DATE_VERIFIED")
        self.assertTrue(good["catalog_date_source_public_match"])

        stale = probe(
            target, read_post=lambda _:original,
            read_public=lambda _:("<html>"+source.replace(
                "Datum označuje načtení katalogu", "Ceny jsou vždy aktuální"
            )+"</html>",{})
        )
        self.assertEqual(stale["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertEqual(stale["catalog_retrieval_stage"],
                         "PUBLIC_DATE_MISSING_OR_DIFFERENT")
        self.assertTrue(stale["product_cards_match"])
        self.assertFalse(stale["catalog_date_source_public_match"])

        no_public = probe(target, read_post=lambda _: original,
                          read_public=lambda _:("<html>"+source.replace(
                              "xfit-feed-retrieval", "removed-class"
                          )+"</html>",{}))
        self.assertEqual(no_public["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertEqual(no_public["public_retrieval_notice_count"], 0)

    def test_missing_or_outdated_source_date_fails_closed(self):
        target = TARGETS[3]
        original = post(*target)
        source = original["content"]["raw"]
        missing = dict(original)
        missing["content"]={"raw":source.replace("xfit-feed-retrieval","other-class")}
        report = probe(target, read_post=lambda _:missing,
                       read_public=lambda _:("<html>"+source+"</html>",{}))
        self.assertEqual(report["status"], "WP_SOURCE_INCOMPLETE")
        self.assertEqual(report["catalog_retrieval_stage"],
                         "SOURCE_DATE_MISSING_OR_INVALID")

        note = ('<p class="xfit-feed-retrieval">'
                'Kdy jsme data nabídky načetli: 1. 11. 2026. '
                'Datum označuje načtení katalogu.</p>')
        stale = catalog_retrieval_readiness(
            note, note, today=date(2026,11,7))
        self.assertEqual(stale["catalog_retrieval_stage"],
                         "SOURCE_DATE_STALE_OR_IN_FUTURE")
        future = catalog_retrieval_readiness(
            note.replace("1. 11.", "9. 11."),
            note.replace("1. 11.", "9. 11."),
            today=date(2026,11,7))
        self.assertEqual(future["catalog_retrieval_stage"],
                         "SOURCE_DATE_STALE_OR_IN_FUTURE")
        self.assertNotIn("namaximum", str(future))

    def test_duplicate_provenance_is_rejected_even_with_fresh_cards(self):
        target = TARGETS[2]
        original = post(*target)
        source = original["content"]["raw"]
        start = source.index('<p class="xfit-feed-retrieval">')
        end = source.index('</p>', start)+4
        duplicate=source[:end]+source[start:end]+source[end:]
        original["content"]["raw"]=duplicate
        result=probe(target, read_post=lambda _:original,
                     read_public=lambda _:("<html>"+duplicate+"</html>",{}))
        self.assertEqual(result["status"],"WP_SOURCE_INCOMPLETE")
        self.assertEqual(result["source_retrieval_notice_count"],2)

    def test_stale_pricing_cards_fail_even_if_new_heading_is_already_visible(self):
        target = TARGETS[3]
        fresh_post = post(*target)
        changed_prices = fresh_post["content"]["raw"].replace("200,00 Kč", "999,00 Kč")
        report = probe(target, read_post=lambda _:fresh_post,
                       read_public=lambda _:("<html>"+changed_prices+"</html>",{}))
        self.assertEqual(report["status"],"PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertTrue(report["public_has_target"])
        self.assertFalse(report["product_cards_match"])
        self.assertEqual(report["wp_product_cards"],2)
        self.assertEqual(report["public_product_cards"],2)

    def test_product_parser_ignores_unrelated_outer_articles(self):
        cards = product_card_texts(
            "<article><h3>Theme shell</h3><article class='xfit-product-card'>"
            "<h3>Whey A</h3><p>Cena: <strong>900&nbsp;Kč</strong></p>"
            "</article></article>")
        self.assertEqual(cards, ["whey a cena: 900 kč"])

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

    def test_commercial_drift_report_distinguishes_price_from_copy(self):
        target = TARGETS[2]
        original = post(*target)
        source = original["content"]["raw"]
        source = source.replace(
            "Cena: 200,00 Kč</p>",
            "Cena: 200,00 Kč · Balení: 500 g</p>"
            "<p>Cena za 100 g prášku: 40,00 Kč</p>"
        ).replace(
            "Cena: 300,00 Kč</p>",
            "Cena: 300,00 Kč · Balení: 600 g</p>"
            "<p>Cena za 100 g prášku: 50,00 Kč</p>"
        )
        source = source.replace(
            "</article>",
            '<a href="https://www.namaximum.cz/product?secret=private">'
            "Zobrazit balení</a></article>", 1
        )
        original["content"]["raw"] = source

        price_drift = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + source.replace(
                "Cena: 200,00 Kč", "Cena: 220,00 Kč") + "</html>", {})
        )
        self.assertEqual(price_drift["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertEqual(price_drift["commercial_fact_drift_positions"], [1])
        self.assertEqual(price_drift["noncommercial_copy_drift_positions"], [])
        self.assertNotIn("secret", str(price_drift))
        self.assertNotIn("namaximum", str(price_drift))

        copy_drift = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + source.replace(
                "Produkt B", "Produkt B upravený") + "</html>", {})
        )
        self.assertEqual(copy_drift["commercial_fact_drift_positions"], [])
        self.assertEqual(copy_drift["noncommercial_copy_drift_positions"], [2])
        self.assertEqual(copy_drift["mismatched_card_positions"], [2])

    def test_same_visible_card_text_with_changed_affiliate_url_fails(self):
        target = TARGETS[2]
        original = post(*target)
        source = original["content"]["raw"]
        tampered = source.replace(
            "https://www.namaximum.cz/produkt-a",
            "https://external-merchant.example/produkt-a",
            1
        )
        result = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + tampered + "</html>", {})
        )
        self.assertTrue(result["public_has_target"])
        self.assertEqual(result["wp_product_cards"], 2)
        self.assertEqual(result["public_product_cards"], 2)
        self.assertFalse(result["product_cards_match"])
        self.assertFalse(result["public_affiliate_link_integrity"])
        self.assertEqual(result["affiliate_link_drift_positions"], [1])
        self.assertEqual(result["unsafe_affiliate_link_positions"], [1])
        self.assertEqual(result["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
        self.assertNotIn("a_aid", str(result))
        self.assertNotIn("demo", str(result))

    def test_card_budget_backlink_is_not_a_second_merchant_offer(self):
        """The real guides have one merchant CTA plus a same-page return link."""
        for target in TARGETS[2:]:
            with self.subTest(guide=target[0]):
                original = post(*target)
                source = original["content"]["raw"].replace(
                    "</article>",
                    '<a href="#xfit-vyber-podle-rozpoctu">Zpět k rozpočtu</a></article>',
                )
                original["content"]["raw"] = source
                result = probe(
                    target, read_post=lambda _: original,
                    read_public=lambda _: ("<html>" + source + "</html>", {}),
                )
                self.assertEqual(result["status"], "PUBLIC_FRESH")
                self.assertTrue(result["public_affiliate_link_integrity"])
                self.assertEqual(result["unsafe_affiliate_link_positions"], [])

                # Extra external links and undisclosed merchant CTAs still
                # fail, even if source and public HTML contain the same flaw.
                changes = {
                    "unapproved_external": source.replace(
                        "</article>",
                        '<a href="https://unapproved.example/offer">Jiný obchod</a></article>', 1,
                    ),
                    "duplicate_merchant": source.replace(
                        "</article>",
                        '<a rel="sponsored" href="https://www.namaximum.cz/offer'
                        '?utm_medium=affiliate&amp;a_aid=demo&amp;a_bid=test">Duplicitní CTA</a>'
                        '</article>', 1,
                    ),
                    "sponsored_internal": source.replace(
                        'href="#xfit-vyber-podle-rozpoctu"',
                        'href="#xfit-vyber-podle-rozpoctu" rel="sponsored"', 1,
                    ),
                    "missing_disclosure": source.replace(
                        "rel='sponsored nofollow'", "rel='nofollow'", 1,
                    ),
                }
                for reason, changed in changes.items():
                    with self.subTest(guide=target[0], reason=reason):
                        original["content"]["raw"] = changed
                        failed = probe(
                            target, read_post=lambda _: original,
                            read_public=lambda _: ("<html>" + changed + "</html>", {}),
                        )
                        self.assertEqual(failed["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")
                        self.assertFalse(failed["public_affiliate_link_integrity"])

    def test_wordpress_typographic_title_is_equivalent_without_weakening_prices(self):
        target = TARGETS[2]
        original = post(*target)
        original["content"]["raw"] = original["content"]["raw"].replace(
            "Produkt A", "Produkt A - Natural"
        )
        public = original["content"]["raw"].replace(
            "Produkt A - Natural", "Produkt A – Natural"
        )
        result = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + public + "</html>", {})
        )
        self.assertEqual(result["status"], "PUBLIC_FRESH")
        self.assertTrue(result["product_cards_match"])
        self.assertTrue(result["public_product_title_integrity"])
        self.assertTrue(result["public_affiliate_link_integrity"])
        self.assertEqual(result["product_title_drift_positions"], [1])
        self.assertEqual(result["typographic_title_drift_positions"], [1])
        self.assertEqual(result["substantive_title_drift_positions"], [])
        self.assertEqual(result["commercial_fact_drift_positions"], [])

    def test_missing_sponsored_disclosure_fails_even_with_matching_prices(self):
        target = TARGETS[3]
        original = post(*target)
        public = original["content"]["raw"].replace(
            "rel='sponsored nofollow'", "rel='nofollow'", 1
        )
        result = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + public + "</html>", {})
        )
        self.assertFalse(result["public_affiliate_link_integrity"])
        self.assertEqual(result["affiliate_link_drift_positions"], [1])
        self.assertIn(1, result["unsafe_affiliate_link_positions"])
        self.assertEqual(result["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")

    def test_noncommercial_title_change_is_identified(self):
        target = TARGETS[2]
        original = post(*target)
        public = original["content"]["raw"].replace("Produkt A", "Produkt A nová verze")
        result = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + public + "</html>", {})
        )
        self.assertEqual(result["product_title_drift_positions"], [1])
        self.assertEqual(result["typographic_title_drift_positions"], [])
        self.assertEqual(result["substantive_title_drift_positions"], [1])
        self.assertEqual(result["affiliate_link_drift_positions"], [])
        self.assertTrue(result["public_affiliate_link_integrity"])
        self.assertFalse(result["public_product_title_integrity"])
        self.assertEqual(result["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")

    def test_unparsable_card_is_not_mistaken_for_matching_price(self):
        target = TARGETS[3]
        original = post(*target)
        altered = original["content"]["raw"].replace("Produkt A", "Jiný produkt")
        report = probe(
            target, read_post=lambda _: original,
            read_public=lambda _: ("<html>" + altered + "</html>", {})
        )
        self.assertEqual(report["unparsed_commercial_fact_positions"], [1])
        self.assertEqual(report["commercial_fact_drift_positions"], [])
        self.assertEqual(report["status"], "PUBLIC_STALE_OR_RENDERED_DIFFERENTLY")

    def test_title_triage_never_confuses_typographic_and_substantive_drift(self):
        self.assertEqual(
            typography_key("Creatine monohydrate - Natural"),
            typography_key("Creatine monohydrate – Natural"),
        )
        self.assertNotEqual(
            typography_key("Creatine monohydrate - Natural 1kg"),
            typography_key("Creatine monohydrate - Natural 500g"),
        )

    def test_public_http_get_retries_only_readonly_transient_failures(self):
        class FakeResponse:
            status = 200
            headers = {"Age": "0"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return "https://xfit.cz/xfit-os-kreatin-poradce/"

            def read(self, size):
                return b"<html>public card</html>"

        url = "https://xfit.cz/xfit-os-kreatin-poradce/"
        with patch("scripts.xfit_public_freshness.urllib.request.urlopen",
                   side_effect=[URLError("temporary"), FakeResponse()]) as get, \
             patch("scripts.xfit_public_freshness.time.sleep") as pause:
            page, headers = public_get(url)
            self.assertEqual(page, "<html>public card</html>")
            self.assertEqual(headers["Age"], "0")
            self.assertEqual(get.call_count, 2)
            pause.assert_called_once_with(2)

        with patch("scripts.xfit_public_freshness.urllib.request.urlopen",
                   side_effect=HTTPError(url, 404, "Not Found", None, None)) as get, \
             patch("scripts.xfit_public_freshness.time.sleep") as pause:
            with self.assertRaises(HTTPError):
                public_get(url)
            self.assertEqual(get.call_count, 1)
            pause.assert_not_called()

        with patch("scripts.xfit_public_freshness.urllib.request.urlopen",
                   side_effect=URLError("still unavailable")) as get, \
             patch("scripts.xfit_public_freshness.time.sleep") as pause:
            with self.assertRaises(URLError):
                public_get(url)
            self.assertEqual(get.call_count, 3)
            self.assertEqual(pause.call_count, 2)

    def test_product_metadata_stage_distinguishes_source_public_and_missing(self):
        source = (
            '<article class="xfit-product-card">'
            '<a href="https://www.namaximum.cz/p?secret=never-log" rel="sponsored" '
            'data-xfit-engine="creatine" data-xfit-partner="namaximum" '
            'data-xfit-product-id="392">koupit</a></article>'
            '<article class="xfit-product-card">'
            '<a href="https://www.namaximum.cz/q" rel="sponsored" '
            'data-xfit-engine="creatine" data-xfit-partner="namaximum" '
            'data-xfit-product-id="393">koupit</a></article>'
        )
        values = cta_metadata(source)
        ready = metadata_readiness(values, values, "creatine", 2)
        self.assertEqual(ready["cta_measurement_stage"], "PUBLIC_METADATA_VERIFIED")
        self.assertTrue(ready["cta_metadata_match"])
        self.assertNotIn("secret", str(ready))
        self.assertNotIn("392", str(ready))

        public = cta_metadata(source.replace('data-xfit-product-id="393"', ""))
        missing = metadata_readiness(values, public, "creatine", 2)
        self.assertEqual(missing["cta_measurement_stage"],
                         "PUBLIC_METADATA_MISSING_OR_DIFFERENT")
        self.assertFalse(missing["cta_metadata_match"])
        source_missing = metadata_readiness(public, values, "creatine", 2)
        self.assertEqual(source_missing["cta_measurement_stage"],
                         "SOURCE_METADATA_INCOMPLETE")

    def test_visible_text_decodes_entities_and_whitespace(self):
        self.assertTrue(visible_has("<h2>Dvě&nbsp;cesty k výběru podle ceny</h2>",
                                    "Dvě cesty k výběru podle ceny"))

if __name__ == "__main__":
    unittest.main()
