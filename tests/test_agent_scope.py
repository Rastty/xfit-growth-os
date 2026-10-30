import unittest
from scripts.xfit_agent_scope import verify
class ScopeTests(unittest.TestCase):
 def test_safe(self):
  self.assertTrue(verify("ux",["scripts/xfit_ux_selector.py","tests/test_ux_selector.py"]))
 def test_readonly_boundaries(self):
  for path in [".github/workflows/attack.yml","content/ready/fake.json","scripts/xfit_revenue_do.py","../secret.txt"]:
   with self.assertRaises(ValueError):verify("ux",[path])
 def test_unknown_lane(self):
  with self.assertRaises(ValueError):verify("unknown",["docs/foo.md"])
 def test_empty_diff(self):
  with self.assertRaises(ValueError):verify("editor",[])
