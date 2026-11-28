import unittest
from scripts.xfit_apparel_refresh import splice, EDITORIAL_MARKER, END
from scripts.xfit_apparel_comparison import build_document
from scripts.wp_publish import MARKER, PublishError
from test_equipment_comparison import item
from test_plant_comparison import BASE,SAMPLE,catalog
from datetime import datetime,timezone

class ApparelRefreshTests(unittest.TestCase):
    def test_editorial_and_refresh_preserve_source(self):
        def doc(price):
            data=catalog(item(11,"Pánské tričko A M",price,category="Pánská trička"),
                         item(12,"Pánská mikina B L",499,category="Pánské mikiny"),
                         item(13,"Fitness legíny C S",399,category="Fitness legíny"))
            data["fetched_at_utc"]=datetime.now(timezone.utc).isoformat()
            return build_document(data,BASE,SAMPLE)["content"]
        before=MARKER+"\n"+doc(100)
        fresh=splice(before,doc(110))
        self.assertIn("110,00 Kč",fresh)
        self.assertEqual(fresh.count(EDITORIAL_MARKER),1)
        self.assertIn("Cena za jedno",fresh.replace("cena za jedno","Cena za jedno"))
        fresh=fresh.replace("Modelový příklad","Redakční příklad")
        self.assertIn("Redakční příklad",splice(fresh,doc(120)))
        self.assertEqual(splice(fresh,doc(110)),fresh)
        with self.assertRaises(PublishError):
            splice(before.replace(END,END+END),doc(110))
