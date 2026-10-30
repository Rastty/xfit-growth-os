import unittest
from scripts.xfit_growth_graph import prioritize
EX={"id":"ok","lane":"ux","title":"ux","source":"live","reader_benefit":5,
"user_demand_evidence":3,"effort":2,"risk":1,"verified_revenue_czk":None}
class GrowthGraphTests(unittest.TestCase):
 def test_unknown_profit_not_zero(self):
  a=prioritize([EX])[0]
  self.assertEqual(a["economic_state"],"UNKNOWN")
  self.assertIsNone(a["verified_revenue_czk"])
  self.assertFalse(a["eligible_for_auto_production"])
 def test_rank_higher_reader_impact(self):
  low={**EX,"id":"low","reader_benefit":2}
  self.assertEqual(prioritize([low,EX])[0]["id"],"ok")
 def test_unknown_lane_rejected(self):
  with self.assertRaises(ValueError):prioritize([{**EX,"lane":"attack"}])
 def test_duplicate_ids_rejected(self):
  with self.assertRaises(ValueError):prioritize([EX,EX])
