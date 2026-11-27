import unittest
from scripts.xfit_beginner_four_lane_hub import (
    NEW_NAV, PLANT_HANDOFF, PLANT_COMMERCE, V2_CHOICES, V2_NAV,
    V2_PLANT_CONTEXT, GEAR_URL, revised, public_choice_check,
)
from scripts.wp_publish import PublishError, editorial_links

def fixture():
    return ("<p>Original introduction.</p>\n" + NEW_NAV + PLANT_HANDOFF + "\n" +
            PLANT_COMMERCE + "\n<h2 id=\"zacatecnik-rozhodnuti\">Rozhodnutí</h2>\n"
            "<p>Other original material with <a href=\"https://xfit.cz/xfit-os-protein-guide/\">link</a>.</p>")

class FourLaneHubTests(unittest.TestCase):
    def test_exact_local_replacement_keeps_links_and_other_source(self):
        old = fixture()
        new = revised(old)
        self.assertTrue(public_choice_check(new))
        self.assertEqual(len(V2_CHOICES), 6)
        self.assertEqual(set(editorial_links(new)), set(editorial_links(old)) | {GEAR_URL})
        self.assertEqual(new, old.replace(NEW_NAV, V2_NAV).replace(
            PLANT_HANDOFF, V2_PLANT_CONTEXT).replace(PLANT_COMMERCE + "\n", ""))
        self.assertLess(new.index("bez nákupu"), new.index("Hledám syrovátkový"))
        self.assertEqual(revised(new), new)
    def test_refuse_drift_and_missing_previous_release(self):
        for bad in (fixture().replace(PLANT_COMMERCE, ""),
                    fixture().replace(NEW_NAV, NEW_NAV.replace("Hledám protein", "Different")),
                    fixture() + NEW_NAV):
            with self.assertRaises(PublishError):
                revised(bad)
    def test_wrong_public_route_not_proven(self):
        self.assertFalse(public_choice_check(V2_NAV.replace(GEAR_URL, V2_CHOICES[1])))
        self.assertFalse(public_choice_check(NEW_NAV))

if __name__ == "__main__":
    unittest.main()
