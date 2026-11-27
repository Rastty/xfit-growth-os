import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from urllib.error import HTTPError
from scripts.xfit_archive_full import AnchorLinks, fetch, inventory, main

def post(i,slug,title,body):
    return {"id":i,"slug":slug,"link":"https://xfit.cz/"+slug+"/",
       "modified":"2026-01-01T00:00:00","title":{"rendered":title},
       "content":{"rendered":"<p>"+body+"</p>"}}
class ArchiveAuditTests(unittest.TestCase):
    def test_coupon_triage_scores_reader_text_and_preserves_raw_diagnostics(self):
        report = inventory([
            post(1, "kreatin-skryty-kod", "Kreatin",
                 '<!-- 5NM2022 --><template>5NM2022</template>'
                 '<a href="https://example.org/?coupon=5NM2022">Nabídka</a>'),
            post(2, "kreatin-slevovy-kod", "Kreatin a slevový kód",
                 'Slevový kód: <strong>5NM202&#50;</strong>'),
            post(3, "kreatin-jiny-kod", "Kreatin a jiný kód", "5NM20220"),
        ])
        self.assertEqual([p["id"] for p in report["stale_promo_candidates"]], [1, 3])
        self.assertEqual(report["visible_stale_2022_promo_posts"], 1)
        self.assertEqual(report["visible_stale_promo_candidates"], [{
            "id": 2, "slug": "kreatin-slevovy-kod",
            "url": "https://xfit.cz/kreatin-slevovy-kod/", "mentions": 1,
        }])
        queue = report["content_quality_review_queue"]
        self.assertEqual(queue["expired_promo_eligible"], 1)
        scored = {p["id"]: p["stale_2022_promo_mentions"] for p in queue["candidates"]}
        self.assertEqual(scored, {1: 0, 2: 1, 3: 0})

    def test_coupon_triage_preserves_inline_codes_and_separates_lines(self):
        report = inventory([
            post(1, "kreatin-kod", "Kreatin", "Slevový kód: <strong>5NM</strong>2022"),
            post(2, "protein-kod", "Protein", "5NM<br>2022"),
            post(3, "kreatin-rady", "Kreatin", "</p><p>5NM</p><p>2022</p><p>"),
            post(4, "protein-rady", "Protein", "5NM <em>2022</em>"),
            post(5, "protein-jiny-kod", "Protein", "5NM2022<span>0</span>"),
        ])
        self.assertEqual(report["visible_stale_2022_promo_posts"], 1)
        self.assertEqual(
            [p["id"] for p in report["visible_stale_promo_candidates"]], [1]
        )
        self.assertEqual(report["content_quality_review_queue"]["expired_promo_eligible"], 1)

    def test_reader_text_coupon_shortlist_has_its_own_cap(self):
        hidden = [
            post(i, f"kreatin-{i}", "Kreatin", "<!-- 5NM2022 -->")
            for i in range(1, 501)
        ]
        visible = [
            post(i, f"protein-{i}", "Protein", "Slevový kód: 5NM2022")
            for i in range(501, 1002)
        ]
        report = inventory(hidden + visible)
        self.assertEqual(report["stale_promo_candidates"][-1]["id"], 500)
        candidates = report["visible_stale_promo_candidates"]
        self.assertEqual([p["id"] for p in candidates], list(range(501, 1001)))
        self.assertEqual(report["visible_stale_2022_promo_posts"], 501)

    def test_template_links_are_not_reader_navigation_or_spam_evidence(self):
        body=('''<template><a href="/skryty/">Skryté</a>
            <template><a href="https://casino.example/">Skryté</a></template>
            <a href="https://example.org/">Skrytý zdroj</a></template>
            <a href="/kreatin/">Kreatin</a>
            <a href="https://ods.od.nih.gov/">Zdroj</a>''')
        row=inventory([post(1,"protein","Protein",body)])["flagged_candidates"][0]
        self.assertEqual(row["internal_link_count"],1)
        self.assertEqual(row["external_hosts"],{"ods.od.nih.gov":1})
        self.assertFalse(row["suspect_spam"])

    def test_self_closing_elements_do_not_end_or_extend_template_scope(self):
        anchors=AnchorLinks()
        anchors.feed('''<template/><a href="/protein/"/>
            <template><a href="/skryty/"/><template/>
            <a href="/take-skryty/"/></template><a href="/kreatin/"/>''')
        self.assertEqual(anchors.links,["/protein/","/kreatin/"])

    def test_inactive_html_does_not_hide_thin_reader_content(self):
        for hidden in ('<!-- {} -->', '<script>{}</script>',
                       '<style>{}</style>', '<template><p>{}</p></template>',
                       '<template><template>{}</template></template>'):
            with self.subTest(markup=hidden):
                body='<p>Krátká rada.</p>'+hidden.format('x'*400)
                report=inventory([post(1,"protein","Protein",body)])
                self.assertEqual(report["thin_count"],1)
                self.assertEqual(report["flagged_candidates"][0]["body_chars"],
                                 len("Krátká rada."))

    def test_reader_text_keeps_czech_entities_and_nested_visible_content(self):
        body='<p>Výživa&nbsp;<strong>a pohyb</strong> &amp; zdraví.</p>'
        row=inventory([post(1,"vyziva","Výživa",body)])["flagged_candidates"][0]
        self.assertEqual(row["body_chars"],len("Výživa a pohyb & zdraví."))

    def test_visible_text_after_inactive_html_is_still_counted(self):
        body='<template>Skryté</template><script>data</script><style>css</style>'
        body+='<p>'+('Praktická rada. '*40)+'</p>'
        self.assertEqual(inventory([post(1,"protein","Protein",body)])["thin_count"],0)

    def test_missing_or_malformed_rendered_fields_reject_the_whole_page(self):
        first=post(1,"protein","Protein","Praktické informace.")
        for field in ("title","content"):
            for value in (None, "text", [], {}, {"rendered":None}, {"rendered":123}):
                malformed=dict(post(2,"kreatin","Kreatin","Další informace."))
                malformed[field]=value
                with self.subTest(field=field,value=value), tempfile.TemporaryDirectory() as directory:
                    output=Path(directory)/"audit.json"
                    with patch("sys.argv",["audit","--pages","2","--size","2",
                                           "--output",str(output)]), \
                         patch("scripts.xfit_archive_full.fetch",
                               side_effect=[([first,first],2),([first,malformed],2)]), \
                         patch("builtins.print"):
                        self.assertEqual(main(),2)
                    report=json.loads(output.read_text(encoding="utf-8"))
                    self.assertFalse(report["complete"])
                    self.assertEqual(report["raw_page_records"],2)
                    self.assertEqual(report["scanned"],1)
                    self.assertEqual(report["pages_fetched"],1)
                    self.assertEqual(report["interrupted_at"],
                                     {"page":2,"error_type":"ValueError"})
                    self.assertFalse(report["mutated_wordpress"])

    def test_explicitly_empty_rendered_fields_are_valid_evidence(self):
        empty=post(1,"prazdny","","")
        empty["content"]["rendered"]=""
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"audit.json"
            with patch("sys.argv",["audit","--pages","1","--output",str(output)]), \
                 patch("scripts.xfit_archive_full.fetch",return_value=([empty],1)), \
                 patch("builtins.print"):
                self.assertEqual(main(),0)
            report=json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["complete"])
            self.assertEqual(report["thin_count"],1)

    def test_malformed_page_preserves_partial_report_as_incomplete(self):
        first=post(1,"kreatin","Kreatin","Praktické informace.")
        for batch in ({}, {"code":"rest_error"}, None, "", [first,None], [True]):
            with self.subTest(batch=batch), tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/"audit.json"
                with patch("sys.argv",["audit","--pages","2","--size","1",
                                       "--output",str(output)]), \
                     patch("scripts.xfit_archive_full.fetch",
                           side_effect=[([first],2),(batch,2)]), \
                     patch("builtins.print"):
                    self.assertEqual(main(),2)
                report=json.loads(output.read_text(encoding="utf-8"))
                self.assertFalse(report["complete"])
                self.assertEqual(report["scanned"],1)
                self.assertEqual(report["raw_page_records"],1)
                self.assertEqual(report["pages_fetched"],1)
                self.assertEqual(report["interrupted_at"],
                                 {"page":2,"error_type":"ValueError"})
                self.assertFalse(report["mutated_wordpress"])

    def test_empty_post_list_remains_a_valid_end_of_archive(self):
        first=post(1,"protein","Protein","Praktické informace.")
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"audit.json"
            with patch("sys.argv",["audit","--pages","2","--size","1",
                                   "--output",str(output)]), \
                 patch("scripts.xfit_archive_full.fetch",
                       side_effect=[([first],0),([],0)]), \
                 patch("builtins.print"):
                self.assertEqual(main(),0)
            report=json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["complete"])
            self.assertEqual(report["pages_fetched"],2)
            self.assertIsNone(report["interrupted_at"])

    def test_completeness_and_exit_status_agree(self):
        first=post(1,"kreatin","Kreatin","Praktické informace.")
        cases=[
            # Short page contradicts the API's remaining-page count.
            (2,2,[([first],3)],False),
            # Requested page limit is reached before the archive ends.
            (1,1,[([first],3)],False),
            # A short page without pagination metadata is still supported.
            (2,2,[([first],0)],True),
            # A full final page with explicit pagination metadata is complete.
            (1,1,[([first],1)],True),
        ]
        for pages,size,batches,complete in cases:
            with self.subTest(pages=pages,size=size,batches=batches), \
                 tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/"audit.json"
                with patch("sys.argv",["audit","--pages",str(pages),
                                       "--size",str(size),"--output",str(output)]), \
                     patch("scripts.xfit_archive_full.fetch",side_effect=batches), \
                     patch("builtins.print"):
                    self.assertEqual(main(),0 if complete else 2)
                report=json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["complete"],complete)
                self.assertEqual(report["scanned"],1)
                self.assertFalse(report["mutated_wordpress"])

    def test_changed_page_total_prevents_absence_conclusions(self):
        first=post(1,"protein","Protein","Praktické informace.")
        second=post(2,"kreatin","Kreatin","Jak vybrat kreatin.")
        for changed_total in (2,4):
            with self.subTest(changed_total=changed_total), \
                 tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/"audit.json"
                with patch("sys.argv",["audit","--pages","2","--size","1",
                                       "--output",str(output)]), \
                     patch("scripts.xfit_archive_full.fetch",
                           side_effect=[([first],3),([second],changed_total)]), \
                     patch("builtins.print"):
                    self.assertEqual(main(),2)
                report=json.loads(output.read_text(encoding="utf-8"))
                self.assertFalse(report["complete"])
                self.assertEqual(report["scanned"],1)
                self.assertEqual(report["declared_total_pages"],3)
                self.assertEqual(report["interrupted_at"],{
                    "page":2,"error_type":"PaginationTotalChanged",
                    "observed_total_pages":changed_total,
                })
                self.assertEqual(report["guide_inlink_coverage"]["coverage_state"],
                                 "PARTIAL_SCAN_NO_ABSENCE_CONCLUSIONS")

    def test_rejected_page_is_not_an_empty_successful_page(self):
        error=HTTPError("https://example.invalid/",400,"Bad Request",{},None)
        with patch("scripts.xfit_archive_full.urlopen",side_effect=error) as request:
            with self.assertRaises(HTTPError):
                fetch(2,1)
        self.assertEqual(request.call_count,1)

    def test_rejected_later_page_preserves_partial_report_as_incomplete(self):
        error=HTTPError("https://example.invalid/",400,"Bad Request",{},None)
        first=post(1,"kreatin","Kreatin","Praktické informace.")
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"audit.json"
            with patch("sys.argv",["audit","--pages","3","--size","1",
                                   "--output",str(output)]), \
                 patch("scripts.xfit_archive_full.fetch",
                       side_effect=[([first],3),error]), \
                 patch("builtins.print"):
                self.assertEqual(main(),2)
            report=json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(report["complete"])
        self.assertEqual(report["scanned"],1)
        self.assertEqual(report["pages_fetched"],1)
        self.assertEqual(report["interrupted_at"],
                         {"page":2,"error_type":"HTTPError"})
        self.assertFalse(report["mutated_wordpress"])

    def test_same_id_repeated_is_not_duplicate(self):
        p=post(5300,"ovesne-vlocky","Ovesné vločky", "Recept s ovesnými vločkami.")
        a=inventory([p,p])
        self.assertEqual(a["raw_page_records"],2)
        self.assertEqual(a["scanned"],1)
        self.assertEqual(a["repeated_pagination_post_count"],1)
        self.assertEqual(a["duplicate_title_groups"],0)
        self.assertEqual(a["exact_body_duplicate_groups"],0)
        self.assertEqual(a["conflicting_pagination_post_count"],0)

    def test_conflicting_repeated_post_makes_audit_incomplete(self):
        first=post(1,"protein","Protein",'<a href="/kreatin/">Rada</a>')
        variants=[
            post(1,"protein","Protein",'<a href="/vyziva/">Rada</a>'),
            dict(first,link="https://example.invalid/protein/"),
            dict(first,modified="2026-11-10T00:00:00"),
            dict(first),  # An unchanged repeated record remains supported.
        ]
        for repeated in variants:
            conflict=repeated!=first
            with self.subTest(repeated=repeated), tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/"audit.json"
                with patch("sys.argv",["audit","--pages","2","--size","1",
                                       "--output",str(output)]), \
                     patch("scripts.xfit_archive_full.fetch",
                           side_effect=[([first],2),([repeated],2)]), \
                     patch("builtins.print") as printed:
                    self.assertEqual(main(),2 if conflict else 0)
                report=json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["complete"],not conflict)
                self.assertEqual(report["scanned"],1)
                self.assertEqual(report["repeated_pagination_post_count"],1)
                self.assertEqual(report["conflicting_pagination_post_count"],int(conflict))
                self.assertEqual(report["conflicting_pagination_post_ids_sample"],
                                 [1] if conflict else [])
                self.assertEqual(report["exact_body_duplicate_groups"],0)
                self.assertFalse(report["mutated_wordpress"])
                self.assertEqual(json.loads(printed.call_args.args[0])[
                    "conflicting_pagination_post_count"],int(conflict))

    def test_conflicting_ids_count_posts_not_repeated_versions(self):
        first=post(1,"protein","Protein","Původní text")
        changed=post(1,"protein","Protein","Upravený text")
        report=inventory([first,changed,changed])
        self.assertEqual(report["repeated_pagination_post_count"],2)
        self.assertEqual(report["conflicting_pagination_post_count"],1)
        self.assertEqual(report["conflicting_pagination_post_ids_sample"],[1])
    def test_two_distinct_posts_with_same_body_are_real_duplicates(self):
        a=inventory([
            post(1,"post-jedna","Svalové cviky","Stejný obsah těla"),
            post(2,"post-dva","Svalové cviky","Stejný obsah těla")
        ])
        self.assertEqual(a["scanned"],2)
        self.assertEqual(a["duplicate_title_groups"],1)
        self.assertEqual(a["exact_body_duplicate_groups"],1)
    def test_unknown_id_is_not_counted(self):
        p=post(None,"bad","Bad","Thin")
        self.assertEqual(inventory([p])["scanned"],0)

    def test_invalid_ids_do_not_hide_behind_a_complete_page_count(self):
        for invalid_id in (None,0,-1,"2",True,False):
            with self.subTest(id=invalid_id), tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/"audit.json"
                valid=post(1,"protein","Protein","Praktické informace.")
                invalid=post(invalid_id,"kreatin","Kreatin","Další informace.")
                with patch("sys.argv",["audit","--pages","1","--size","2",
                                       "--output",str(output)]), \
                     patch("scripts.xfit_archive_full.fetch",return_value=([valid,invalid],1)), \
                     patch("builtins.print") as printed:
                    self.assertEqual(main(),2)
                report=json.loads(output.read_text(encoding="utf-8"))
                self.assertFalse(report["complete"])
                self.assertEqual(report["invalid_post_id_count"],1)
                self.assertEqual(report["scanned"],1)
                self.assertEqual(report["raw_page_records"],2)
                self.assertEqual(report["repeated_pagination_post_count"],0)
                self.assertFalse(report["mutated_wordpress"])
                self.assertEqual(json.loads(printed.call_args.args[0])["invalid_post_id_count"],1)

    def test_equal_text_with_different_content_is_not_exact_duplicate(self):
        pairs=[
            ('Rada<script>first()</script>', 'Rada<script>second()</script>'),
            ('<a href="https://example.org/source-a">Zdroj</a>',
             '<a href="https://example.org/source-b">Zdroj</a>'),
            ('<img src="/cvik-a.jpg" alt="Cvik">',
             '<img src="/cvik-b.jpg" alt="Cvik">'),
            ('Dávka 5 mg', 'Dávka 5 Mg'),
        ]
        for first,second in pairs:
            with self.subTest(first=first,second=second):
                a=inventory([post(1,"jedna","Výživa",first),
                             post(2,"dva","Výživa",second)])
                self.assertEqual(a["exact_body_duplicate_groups"],0)
                # Shared titles remain a separate, weaker review signal.
                self.assertEqual(a["duplicate_title_groups"],1)

    def test_identical_image_content_is_detected_without_visible_text(self):
        body='<img src="/cvik.jpg" alt="Provedení cviku">'
        a=inventory([post(1,"jedna","Cvik",body),
                     post(2,"dva","Cvik",body)])
        self.assertEqual(a["exact_body_duplicate_groups"],1)

    def test_internal_links_include_relative_and_case_insensitive_hosts(self):
        links=["/kreatin/", "../protein/", "trenink/", "//www.xfit.cz/pilates/",
               "https://XFIT.CZ/vyziva/?a=1&amp;b=2"]
        p=post(1,"cviceni","Cvičení", "".join(
            '<a href="'+href+'">Rada</a>' for href in links))
        row=inventory([p])["flagged_candidates"][0]
        self.assertEqual(row["internal_link_count"],5)
        self.assertEqual(row["external_hosts"],{})
    def test_foreign_urls_and_page_anchors_are_not_internal_links(self):
        links=["https://example.org/xfit.cz/protein/",
               "https://xfit.cz.example.org/", "https://xfit.cz@example.org/",
               "https://example.org/?next=https://xfit.cz/", "#davkovani", "",
               "mailto:poradna@xfit.cz", "javascript:void(0)"]
        p=post(1,"protein","Protein", "".join(
            '<a href="'+href+'">Odkaz</a>' for href in links))
        row=inventory([p])["flagged_candidates"][0]
        self.assertEqual(row["internal_link_count"],0)
        self.assertEqual(row["external_hosts"],{"example.org":3,"xfit.cz.example.org":1})

    def test_same_article_permalinks_are_not_navigation_to_other_pages(self):
        links=["https://xfit.cz/protein", "https://xfit.cz/protein/", "/protein/#davkovani",
               "https://WWW.XFIT.CZ/protein/#zdroje", "./#slozeni",
               "https://xfit.cz/kreatin/#davkovani"]
        p=post(1,"protein","Protein", "".join(
            '<a href="'+href+'">Rada</a>' for href in links))
        row=inventory([p])["flagged_candidates"][0]
        self.assertEqual(row["internal_link_count"],1)
        self.assertEqual(row["external_hosts"],{})

    def test_query_relative_links_preserve_the_article_path(self):
        p=post(1,"protein","Protein",
               '<a href="?page=2">Další část</a>'
               '<a href="?page=1#zdroje">Zdroje na této stránce</a>')
        p["link"]+="?page=1"
        row=inventory([p])["flagged_candidates"][0]
        self.assertEqual(row["internal_link_count"],1)
    def test_malformed_links_do_not_abort_inventory(self):
        links=["https://[broken/", "https://example.org／other/",
               "/kreatin/", "https://example.org/protein/"]
        p=post(1,"protein","Protein", "".join(
            '<a href="'+href+'">Rada</a>' for href in links))
        a=inventory([p,post(2,"trenink","Trénink","Krátký text")])
        self.assertEqual(a["scanned"],2)
        self.assertEqual(a["invalid_link_count"],2)
        row=next(r for r in a["flagged_candidates"] if r["id"]==1)
        self.assertEqual(row["invalid_link_count"],2)
        self.assertEqual(row["internal_link_count"],1)
        self.assertEqual(row["external_hosts"],{"example.org":1})
    def test_valid_links_have_no_parse_failures(self):
        p=post(1,"protein","Protein",'<a href="/kreatin/">Kreatin</a>')
        a=inventory([p])
        self.assertEqual(a["invalid_link_count"],0)
        self.assertEqual(a["flagged_candidates"][0]["invalid_link_count"],0)

    def test_invalid_http_ports_do_not_count_as_navigation_or_spam(self):
        body = ('<a href="https://xfit.cz:99999/kreatin/">Kreatin</a>'
                '<a href="//casino.example:bad/nabidka/">Nabídka</a>'
                '<a href="/vyziva/">Výživa</a>'
                '<a href="https://example.org:443/zdroj/">Zdroj</a>')
        report = inventory([post(1, "protein", "Protein", body)])
        row = report["flagged_candidates"][0]
        self.assertEqual(report["invalid_link_count"], 2)
        self.assertEqual(row["invalid_link_count"], 2)
        self.assertEqual(row["internal_link_count"], 1)
        self.assertEqual(row["external_hosts"], {"example.org": 1})
        self.assertFalse(row["suspect_spam"])

    def test_html_anchor_attribute_syntax_is_supported(self):
        body='''<A HREF = '/kreatin/'>Kreatin</A>
            <a href=/protein/>Protein</a>
            <a href = "https://example.org/vyziva/">Zdroj</a>'''
        row=inventory([post(1,"vyziva","Výživa",body)])["flagged_candidates"][0]
        self.assertEqual(row["internal_link_count"],2)
        self.assertEqual(row["external_hosts"],{"example.org":1})

    def test_inactive_markup_and_data_attributes_are_not_links(self):
        body='''<!-- <a href="/skryty/">Komentář</a> -->
            <script>const template = '<a href="/sablona/">Text</a>';</script>
            <a data-href="https://casino.example/">Bez odkazu</a>
            <a data-href="/odlozeny/" href="/protein/">Protein</a>'''
        row=inventory([post(1,"vyziva","Výživa",body)])["flagged_candidates"][0]
        self.assertEqual(row["internal_link_count"],1)
        self.assertEqual(row["external_hosts"],{})
        self.assertFalse(row["suspect_spam"])

    def test_attribute_entities_are_decoded_only_once(self):
        anchors=AnchorLinks()
        anchors.feed('<a href="/protein/?a=1&amp;b=&amp;sol;">Protein</a>')
        self.assertEqual(anchors.links,["/protein/?a=1&b=&sol;"])

if __name__=="__main__":unittest.main()
