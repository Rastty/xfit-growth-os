import unittest
from scripts.xfit_protein_commerce_routes import (
    SCOPES, PRICE_HEADING, PRICE_OWNER, PRICE_PANEL, guide_panel, panel, revise, proof, PLANT_URL, WHEY_URL,
)
from scripts.wp_publish import MARKER, PublishError, editorial_links

def article():
    # Realistic long independent paragraphs, three H2s and recognized source.
    return ("<h2>První samostatná sekce</h2><p>" + " ".join(
        "Vysvětlení číslo " + str(i) + " s vlastní informací o bílkovinách a výběru etikety."
        for i in range(45)) + "</p><h2>Druhá část</h2><p>Čtěte složení.</p>"
        "<h2>Zdroje</h2><p><a href=\"https://food.ec.europa.eu/food-safety\">EU</a></p>")

class ProteinCommerceRoutesTests(unittest.TestCase):
    def test_existing_guide_panel_only_updated(self):
        cfg = SCOPES["protein-guide"]
        old = MARKER + "\n" + panel() + article()
        new = revise(cfg, old)
        self.assertTrue(proof(cfg, new))
        self.assertEqual(new.replace(guide_panel(), panel(), 1), old)
        self.assertEqual(set(editorial_links(new)), set(editorial_links(old)) | {PLANT_URL})
        self.assertEqual(revise(cfg, new), new)
    def test_price_guide_two_real_choices_and_no_buy(self):
        cfg = SCOPES["protein-price"]
        old = (MARKER + '<section data-xfit-ai-edit="' + PRICE_OWNER + '">' + article() + '</section>' + PRICE_HEADING
               + '<p><a href="' + WHEY_URL + '">Původní syrovátkové srovnání</a></p>')
        new = revise(cfg, old)
        self.assertTrue(proof(cfg, new))
        self.assertEqual(new.replace(PRICE_PANEL + "\n", "", 1), old)
        self.assertEqual(set(editorial_links(new)), set(editorial_links(old)) | {PLANT_URL})
        self.assertIn("prášek nemusíte kupovat", new)
        self.assertEqual(editorial_links(new).count(WHEY_URL), editorial_links(old).count(WHEY_URL))
        self.assertEqual(revise(cfg, new), new)
        for bad in (old.replace(PRICE_OWNER,"other"), old + PRICE_HEADING,
                    old.replace(WHEY_URL,"https://xfit.cz/other/"),
                    old + '<a href="' + PLANT_URL + '">Already linked</a>'):
            with self.assertRaises(PublishError):
                revise(cfg, bad)
    def test_missing_original_or_wrong_destination_fails(self):
        cfg = SCOPES["protein-guide"]
        with self.assertRaises(PublishError):
            revise(cfg, MARKER + article())
        self.assertFalse(proof(cfg, guide_panel().replace(PLANT_URL, WHEY_URL)))

if __name__ == "__main__":
    unittest.main()
