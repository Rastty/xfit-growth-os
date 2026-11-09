"""Live advisors must refresh when any shared affiliate-link generator changes."""
from pathlib import Path
import unittest


LIVE_WORKFLOWS = {
    "creatine": ".github/workflows/xfit-creatine-live.yml",
    "whey": ".github/workflows/xfit-whey-live.yml",
}
COMMON = {
    "scripts/xfit_creatine_guide.py",
    "scripts/xfit_affil_deeplink.py",
    "scripts/wp_publish.py",
    "scripts/xfit_click_metadata.py",
}


def push_paths(file):
    text = Path(file).read_text(encoding="utf-8")
    block = text.split("\n  push:\n", 1)[1]
    block = block.split("\n  schedule:\n", 1)[0]
    block = block.split("\npermissions:\n", 1)[0]
    return {line.strip()[3:-1] for line in block.splitlines()
            if line.strip().startswith("- '")
            and line.strip().endswith("'")}


class SharedAdvisorDependencyTests(unittest.TestCase):
    def test_both_live_advisors_watch_the_actual_affiliate_builder(self):
        for name, file in LIVE_WORKFLOWS.items():
            with self.subTest(advisor=name):
                paths = push_paths(file)
                self.assertTrue(COMMON.issubset(paths),
                                f"Missing shared runtime dependency for {name}: {COMMON - paths}")
                self.assertIn(file, paths)

    def test_both_advisors_keep_safety_and_nonoverlapping_schedules(self):
        schedules = []
        for file in LIVE_WORKFLOWS.values():
            raw = Path(file).read_text(encoding="utf-8")
            self.assertIn("XFIT_AFFIL_FEED_ENABLED == 'true'", raw)
            self.assertIn("concurrency:", raw)
            self.assertIn("cancel-in-progress: false", raw)
            self.assertIn("python -m unittest discover -s tests -v", raw)
            self.assertIn("--deploy", raw)
            self.assertIn("workflow_dispatch:", raw)
            schedules.extend([line.strip() for line in raw.splitlines()
                              if line.strip().startswith("- cron:")])
        self.assertEqual(len(schedules), 2)
        self.assertNotEqual(schedules[0], schedules[1])


if __name__ == "__main__":
    unittest.main()
