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

if __name__=="__main__":unittest.main()
