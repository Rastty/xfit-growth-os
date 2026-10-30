import unittest
from scripts.xfit_ai_visibility import inspect
class VisibilityTests(unittest.TestCase):
 def test_good_document(self):
  html='<head><title>Test</title><meta name="description" content="desc"><link rel="canonical" href="https://xfit.cz/example/"></head><h1>One</h1><h2>A</h2><h2>B</h2><h2>C</h2>'
  d=inspect(html,"/example/")
  self.assertNotIn("canonical_mismatch",d["flags"])
  self.assertNotIn("h1_count_not_one",d["flags"])
 def test_bad_document(self):
  d=inspect('<meta name="robots" content="noindex"><h1>One</h1><h1>Two</h1>',"/test/")
  self.assertIn("noindex",d["flags"])
  self.assertIn("h1_count_not_one",d["flags"])
