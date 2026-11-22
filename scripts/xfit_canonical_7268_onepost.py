"""Exact original WP #7268 canonical repair, using the previously live-verified onepost guard.

NO shared global values survive execution: temporary runtime configuration
uses context managers and restores the existing #8713 release configuration.
This runner may run once after its own guarded workflow; it never retries POST.
"""
import json
from pathlib import Path
import sys
from unittest.mock import patch

from scripts import xfit_canonical_8713_onepost as guarded
from scripts.wp_publish import PublishError

POST_ID = 7268
BACKUP = Path("reports/backups/xfit-canonical-7268-full-original.json")


def run(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"snapshot", "deploy"}:
        raise PublishError("Usage: snapshot|deploy")
    with patch.object(guarded, "POST_ID", POST_ID), \
         patch.object(guarded, "BACKUP", BACKUP):
        (guarded.snapshot if args[0] == "snapshot" else guarded.deploy)()


if __name__ == "__main__":
    try:
        run()
    except (PublishError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"state": "BLOCKED_NO_BLIND_RETRY",
                          "post_id": POST_ID, "error_type": type(exc).__name__}),
              file=sys.stderr)
        raise SystemExit(2)
