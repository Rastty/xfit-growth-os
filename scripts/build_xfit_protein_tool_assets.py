#!/usr/bin/env python3
"""Build an immutable static hosting bundle for XFIT; no WordPress writes."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("calculator.js", "calculator.css")
SOURCE_DIR = ROOT / "assets/tools/protein-price"
STAMP = (2026, 11, 17, 0, 0, 0)


def bundle_contents():
    reviewed = {}
    for filename in SOURCES:
        source = SOURCE_DIR / filename
        if source.is_symlink() or not source.is_file():
            raise ValueError("Missing or symlinked source asset")
        data = source.read_bytes()
        if not data or len(data) > 200_000:
            raise ValueError("Unsafe static asset size")
        data.decode("utf-8")
        reviewed[filename] = data
    digest = hashlib.sha256()
    for filename, content in reviewed.items():
        digest.update(filename.encode("ascii") + b"\x00" + content + b"\x00")
    revision = digest.hexdigest()[:16]
    prefix = f"protein-price/{revision}/"
    manifest = {
        "status": "REVIEWED_STATIC_ASSETS_NOT_DEPLOYED",
        "directory": prefix,
        "files": {name: hashlib.sha256(content).hexdigest()
                  for name, content in reviewed.items()},
        "wordpress_writes": 0,
        "external_uploads": 0,
    }
    return prefix, reviewed, manifest


def build(output):
    prefix, reviewed, manifest = bundle_contents()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        entries = {prefix + name: value for name, value in reviewed.items()}
        entries[prefix + "manifest.json"] = (
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        for path, data in entries.items():
            info = zipfile.ZipInfo(path, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(output) as archive:
        if tuple(archive.namelist()) != tuple(entries) or archive.testzip():
            raise ValueError("Static bundle integrity failed")
    return {**manifest, "package": output.name, "assets": len(reviewed)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="dist/xfit-protein-price-assets.zip")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile) as exc:
        print("XFIT_STATIC_BUNDLE_ERROR: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
