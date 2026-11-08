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

    def test_equal_text_with_different_content_is_not_exact_duplicate(self):
        pairs=[
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
