import json
import unittest
from pathlib import Path
from scripts.xfit_editorial_gate import check_document

PATH=Path("content/ready/xfit-os-kreatin-nebo-protein.json")
class ProteinOrCreatineChooserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(PATH.read_text(encoding="utf-8"))
    def test_distinct_search_intent_and_editorial_quality(self):
        doc=self.doc
        self.assertEqual(doc["slug"],"xfit-os-kreatin-nebo-protein")
        result=check_document(doc)
        self.assertGreaterEqual(result["word_count"],1000)
        self.assertGreaterEqual(result["h2_count"],6)
        self.assertFalse(result["commerce"])
    def test_six_use_cases_and_no_purchase_option(self):
        body=self.doc["content"]
        self.assertGreaterEqual(body.count("<details>"),6)
        self.assertIn("Nekupujte zatím nic",body)
        self.assertIn("alergii",body.casefold())
    def test_verified_guide_crosslinks(self):
        s=self.doc["content"]
        for target in ("/xfit-os-protein-guide/","/xfit-os-kreatin-poradce/",
                       "/xfit-os-syrovatkovy-protein-porovnani/",
                       "/xfit-os-doplnky-pro-zacatecniky/"):
            self.assertIn(target,s)
    def test_first_screen_handoff_and_checkout_arithmetic(self):
        body=self.doc["content"]
        first=body.split('<h2 id="xfit-rozhodnuti"',1)[0]
        self.assertIn('<nav aria-label="Rychlé další kroky">',first)
        self.assertIn('Nejsem si jistý – nejdřív ověřit potřebu',first)
        self.assertIn('/xfit-os-syrovatkovy-protein-porovnani/',first)
        self.assertIn('/xfit-os-kreatin-poradce/',first)
        self.assertIn('affiliate odkazy',first)
        self.assertIn('hmotnost balení × údaj z etikety / 100',body)
        self.assertIn('cenu za 100 g bílkovin',body)
        self.assertIn('gramy, které skutečně využijete',body)
        self.assertNotIn('Modelový příklad proteinu:',body)
        self.assertNotIn('Modelový příklad kreatinu:',body)
        self.assertEqual(self.doc["wp_post_id"],25504)

    def test_safety_and_evidence(self):
        s=self.doc["content"]
        self.assertIn("ods.od.nih.gov",s)
        self.assertIn("pmc.ncbi.nlm.nih.gov",s)
        self.assertIn("ledvin",s)
        self.assertIn("1,4–2,0",s)
        self.assertNotIn("utm_source=heureka",s)
if __name__=="__main__":unittest.main()
