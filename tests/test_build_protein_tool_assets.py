"""The static hosting archive cannot include a competing HTML page or plugin."""

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts import build_xfit_protein_tool_assets as tool


class StaticBundleTests(unittest.TestCase):
    def test_immutable_directory_has_only_reviewed_asset_pair_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "static.zip"
            receipt = tool.build(archive_path)
            prefix = receipt["directory"]
            self.assertRegex(prefix, r"^protein-price/[0-9a-f]{16}/$")
            self.assertEqual(receipt["wordpress_writes"], 0)
            self.assertEqual(receipt["external_uploads"], 0)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), [
                    prefix + "calculator.js", prefix + "calculator.css",
                    prefix + "manifest.json",
                ])
                manifest = json.loads(archive.read(prefix + "manifest.json"))
                self.assertEqual(manifest["directory"], prefix)
                for filename in tool.SOURCES:
                    self.assertEqual(archive.read(prefix + filename),
                                     (tool.SOURCE_DIR / filename).read_bytes())
                    self.assertEqual(len(manifest["files"][filename]), 64)

    def test_archive_bytes_are_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "a.zip", Path(tmp) / "b.zip"
            tool.build(first)
            tool.build(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
