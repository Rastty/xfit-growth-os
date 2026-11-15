import unittest
from scripts.xfit_agent_scope import RELEASE_BOUND_EDITOR_REVISIONS, verify
from scripts.xfit_protein_checkout_release import REVISION as CHECKOUT_REVISION
from scripts.xfit_protein_pack_release import REVISION as PACK_REVISION
from scripts.xfit_protein_table_optout_release import REVISION as OPTOUT_REVISION
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
 def test_editor_cannot_modify_release_bound_snapshots(self):
  self.assertEqual(
   RELEASE_BOUND_EDITOR_REVISIONS,
   {str(PACK_REVISION),str(CHECKOUT_REVISION),str(OPTOUT_REVISION)},
  )
  for path in sorted(RELEASE_BOUND_EDITOR_REVISIONS):
   with self.subTest(path=path),self.assertRaises(ValueError):
    verify("editor",[path])
 def test_editor_can_create_independent_revision_proposal(self):
  self.assertTrue(verify("editor",[
   "content/revisions/editor-new-independent-proposal.json",
   "scripts/xfit_editor_new_independent_proposal.py",
   "tests/test_editor_new_independent_proposal.py",
  ]))
