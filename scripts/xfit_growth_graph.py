"""Prometheus-inspired, Xfit-only evidence-to-action priority queue.

Heuristic utility is NOT a money estimate. Missing business outcomes are UNKNOWN.
Risk cannot be bypassed by high speculative revenue or an eager AI agent.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
LANES=("ux","archive","editor","revenue")
def prioritize(records,weights=None):
 weights=weights or {"reader":5,"demand":3,"effort":2,"risk":3}
 out=[]
 seen=set()
 for row in records:
  if row["id"] in seen:raise ValueError("Duplicate opportunity id")
  seen.add(row["id"])
  if row.get("lane") not in LANES:raise ValueError("Unknown lane")
  for field in ("reader_benefit","user_demand_evidence","effort","risk"):
   if type(row.get(field)) is not int or not 1<=row[field]<=5:
    raise ValueError("Invalid documented heuristic score")
  score=(weights["reader"]*row["reader_benefit"]+
         weights["demand"]*row["user_demand_evidence"]-
         weights["effort"]*row["effort"]-
         weights["risk"]*row["risk"])
  money=row.get("verified_revenue_czk")
  if money is not None and (type(money) not in (float,int) or money<0):
   raise ValueError("Revenue must be non-negative observed number or unknown")
  out.append({"id":row["id"],"lane":row["lane"],"title":row["title"],
    "source":row["source"],"heuristic_priority_score":score,
    "economic_state":"UNKNOWN" if money is None else "OBSERVED_VALUE",
    "verified_revenue_czk":money,
    "eligible_for_auto_discovery":True,
    "eligible_for_auto_production":False,
    "unresolved_blockers":row.get("blockers") or []})
 return sorted(out,key=lambda x:(-x["heuristic_priority_score"],x["id"]))
def main():
 cfg=json.loads(Path("config/xfit-priority-candidates.json").read_text(encoding="utf-8"))
 data=prioritize(cfg["opportunities"])
 result={"generated_at_utc":datetime.now(timezone.utc).isoformat(),
   "stage":"read_only_prioritization","rule":"do_not_invent_profit",
   "opportunities":data,"next_per_lane":{lane:next((o for o in data if o["lane"]==lane),None) for lane in LANES},
   "wordpress_mutations":0}
 Path("reports").mkdir(exist_ok=True)
 Path("reports/xfit-growth-priority.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"state":"PRIORITY_QUEUE","ranked":len(data),
   "next":[{"id":o["id"],"lane":o["lane"],"priority":o["heuristic_priority_score"],"money":o["economic_state"]} for o in data[:4]],
   "remote_writes":0},ensure_ascii=False))
if __name__=="__main__":main()
