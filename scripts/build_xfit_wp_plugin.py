#!/usr/bin/env python3
"""Build a deterministic, installable WordPress plugin ZIP; no remote writes."""
import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.2"
MANIFEST = (
    ("wordpress-plugin/xfit-analytics/xfit-analytics.php",
     "xfit-analytics/xfit-analytics.php"),
    ("assets/analytics/xfit-webtoffee-bridge.js",
     "xfit-analytics/assets/xfit-webtoffee-bridge.js"),
    ("assets/analytics/xfit-outbound.js",
     "xfit-analytics/assets/xfit-outbound.js"),
)


def build(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        for source_path, output_path in MANIFEST:
            original = ROOT / source_path
            if original.is_symlink() or not original.is_file():
                raise ValueError("Missing or unsafe approved plugin file")
            data = original.read_bytes()
            data.decode("utf-8")
            if not data:
                raise ValueError("Cannot package empty plugin file")
            info = zipfile.ZipInfo(output_path, date_time=(2026, 11, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(output) as archive:
        if tuple(archive.namelist()) != tuple(path for _source, path in MANIFEST):
            raise ValueError("Archive manifest changed")
        if archive.testzip():
            raise ValueError("ZIP integrity failed")
    return {
        "status": "INSTALLABLE_PLUGIN_PACKAGE_BUILT",
        "version": VERSION,
        "package": output.name,
        "contents": len(MANIFEST),
        "wp_installed": False,
        "ga4_events_observed": False,
        "wordpress_writes": 0,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="dist/xfit-analytics-0.1.2.zip")
    args = ap.parse_args(argv)
    try:
        receipt = build(args.output)
        print(json.dumps(receipt))
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print("XFIT_PLUGIN_PACKAGE_ERROR: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
