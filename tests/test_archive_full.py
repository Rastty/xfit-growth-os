import unittest
from scripts.xfit_archive_full import inventory

def post(i,slug,title,body):
    return {"id":i,"slug":slug,"link":"https://xfit.cz/"+slug+"/",
       "modified":"2026-01-01T00:00:00","title":{"rendered":title},
       "content":{"rendered":"<p>"+body+"</p>"}}
class ArchiveAuditTests(unittest.TestCase):
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

if __name__=="__main__":unittest.main()
