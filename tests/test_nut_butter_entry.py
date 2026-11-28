import unittest
from scripts.xfit_sugar_label_revision import expected
from scripts.xfit_nut_butter_refresh import splice,segments,END
from scripts.xfit_nut_butter_comparison import build_document
from scripts.wp_publish import MARKER,PublishError
from test_equipment_comparison import item
from test_plant_comparison import BASE,SAMPLE,catalog
from datetime import datetime,timezone

class NutButterEntryTests(unittest.TestCase):
    def test_sugar_label_content_is_ready(self):
        self.assertIn("18 g celkových cukrů",expected())
    def test_refresh_preserves_editorial_text(self):
        def doc(price):
            data=catalog(item(11,"Arašídové máslo 500 g",price,category="Zdravá másla"),
                         item(12,"Mandlové máslo 250 g",170,category="Zdravá másla"))
            data["fetched_at_utc"]=datetime.now(timezone.utc).isoformat()
            return build_document(data,BASE,SAMPLE)["content"]
        body=MARKER+"\n"+doc(100)
        body=body.replace("<h2>Jak rozhodnout mezi malým a velkým balením</h2>","<h2>Jak rozhodnout mezi malým a velkým balením</h2><p>Redakční doplněk.</p>")
        fresh=splice(body,doc(110))
        self.assertIn("Redakční doplněk.",fresh)
        self.assertIn("110,00 Kč",fresh)
        self.assertEqual(splice(body,doc(100)),body)
        with self.assertRaises(PublishError):
            splice(body.replace(END,END+END),doc(110))

    def test_daily_refresh_excludes_powder_before_ranking(self):
        from scripts.xfit_nut_butter_refresh import build_document as current
        data=catalog(item(11,"Arašídové máslo 500 g",100,category="Zdravá másla"),
                     item(12,"Mandlové máslo 250 g",170,category="Zdravá másla"),
                     item(13,"Powdered Peanut Butter 400 g",30,category="Zdravá másla"),
                     item(14,"Arašídové máslo v prášku 400 g",20,category="Zdravá másla"))
        data["fetched_at_utc"]=datetime.now(timezone.utc).isoformat()
        old=MARKER+"\n"+build_document(data,BASE,SAMPLE)["content"]
        doc=current(data,BASE,SAMPLE)["content"]
        live=splice(old,doc)
        self.assertNotIn("Powdered Peanut Butter",live)
        self.assertNotIn("Arašídové máslo v prášku 400 g",live)
        self.assertIn("Hotové máslo vs. prášek",live)
        self.assertEqual(live.count('class="xfit-product-card"'),2)
        self.assertEqual(splice(live,doc),live)
