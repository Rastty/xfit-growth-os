import unittest
from scripts.xfit_legacy_gymwear_reader_fix import revise, REPLACEMENTS, FAKE_LABELS, MARKER, TARGET
from scripts.wp_publish import PublishError

class GymwearReaderFixTests(unittest.TestCase):
    def test_exact_fake_links_and_media_preservation(self):
        raw = "<h2>Pro ženy se štíhlou postavou</h2><h2>Dámské sportovní legíny</h2><h2>Dámské sportovní boty</h2>"
        raw += "".join("<p>"+old+"</p>" for old,_ in REPLACEMENTS)
        raw += "".join('<a href="https://www.example.com/x">'+label+'</a>' for label in sorted(FAKE_LABELS))
        raw += '<img src="https://xfit.cz/a.jpg" alt="fitness">'+'<p>Text.</p>'*100
        updated,coupons,placeholders=revise(raw)
        self.assertEqual((coupons,placeholders),(0,10))
        self.assertIn(MARKER,updated)
        self.assertIn(TARGET,updated)
        self.assertIn('<img src="https://xfit.cz/a.jpg" alt="fitness">',updated)
        self.assertNotIn("example.com",updated)
        with self.assertRaises(PublishError):
            revise(raw.replace("náš blog","jiný odkaz"))
