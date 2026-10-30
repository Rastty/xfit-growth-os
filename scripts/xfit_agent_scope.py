"""Fail-closed ownership and hygiene gate for untrusted AI-generated pull requests.

No model access, no WordPress writes and no tokens in this script.
Each lane has a disjoint file ownership policy to prevent cross-agent collisions.
"""
import argparse
from fnmatch import fnmatchcase
import re
import subprocess
from pathlib import Path

LANE_PATHS={
 "ux":[
  "scripts/xfit_creatine_guide.py","scripts/xfit_whey_guide.py",
  "tests/test_creatine_guide.py","tests/test_whey_guide.py",
  "scripts/xfit_ux_*.py","tests/test_ux_*.py","docs/ux/*"
 ],
 "archive":[
  "scripts/xfit_archive_full.py","scripts/xfit_archive_*.py",
  "tests/test_archive_*.py","config/xfit-offtopic-*.json","docs/archive/*"
 ],
 "editor":[
  "content/revisions/editor-*.json","scripts/xfit_editor_*.py",
  "tests/test_editor_*.py","docs/content/*"
 ],
 "revenue":[
  "scripts/xfit_revenue_*.py","tests/test_revenue_*.py","docs/revenue/*"
 ],
}
NO_EDIT_PREFIXES=(".github/workflows/",".github/agents/",".git/",".gemini/","content/ready/")
IMMUTABLE_EVIDENCE={"scripts/xfit_archive_wave01.py","config/xfit-offtopic-wave01.json"}
DANGEROUS_PATTERNS=(
  re.compile(r"(?:sk|ghp|gho|github_pat)_[A-Za-z0-9_-]{18,}"),
  re.compile(r"secretKey\s*=\s*[A-Za-z0-9_-]{20,}",re.I),
  re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
)
def verify(lane, paths):
 if lane not in LANE_PATHS:raise ValueError("unknown agent lane")
 if not paths:raise ValueError("agent made no changes")
 forbidden=[]
 for p in paths:
  p=p.strip().replace("\\","/")
  if not p or p.startswith("/") or "../" in p or p.startswith("../"):
   forbidden.append(p);continue
  if p in IMMUTABLE_EVIDENCE or any(p.startswith(prefix) for prefix in NO_EDIT_PREFIXES):
   forbidden.append(p);continue
  if not any(fnmatchcase(p,pattern) for pattern in LANE_PATHS[lane]):
   forbidden.append(p);continue
  source=Path(p)
  if source.is_symlink():forbidden.append(p);continue
  if source.exists() and source.is_file():
   if source.stat().st_size>200_000:forbidden.append(p);continue
   try:
    content=source.read_text(encoding="utf-8")
   except UnicodeError:
    forbidden.append(p);continue
   if any(rule.search(content) for rule in DANGEROUS_PATTERNS):
    forbidden.append(p)
 if forbidden:raise ValueError("cross-lane/secret/unsafe file modifications rejected: "+", ".join(forbidden))
 return True

def changed_files():
 # Includes untracked files, so the agent cannot bypass the gate by creating new files.
 tracked=subprocess.check_output(["git","diff","--name-only","HEAD"],text=True).splitlines()
 untracked=subprocess.check_output(["git","ls-files","--others","--exclude-standard"],text=True).splitlines()
 return sorted(set(tracked+untracked))

if __name__=="__main__":
 a=argparse.ArgumentParser();a.add_argument("--lane",required=True,choices=LANE_PATHS);args=a.parse_args()
 files=changed_files()
 verify(args.lane,files)
 print("AI_CHANGE_GATE_PASS lane="+args.lane+" changed_files="+str(len(files)))
