"""Guard the reversible archive cleanup against outdated traffic evidence."""

import copy
from datetime import date
import unittest
from unittest import mock

from scripts import xfit_archive_wave01 as wave
from scripts.wp_publish import PublishError


class FreshArchiveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "evidence": {
                "ga4_period": "2026-08-01..2026-10-29",
                "gsc_period": "2026-07-29..2026-10-28",
            }
        }

    def test_valid_evidence_within_fourteen_days(self):
        wave.assert_fresh_evidence(self.cfg, today=date(2026, 11, 9))

    def test_october_evidence_cannot_authorize_november_17_cleanup(self):
        with self.assertRaisesRegex(PublishError, "stale"):
            wave.assert_fresh_evidence(self.cfg, today=date(2026, 11, 17))

    def test_missing_both_or_one_source_fails_closed(self):
        for replacement in (None, {}, {"ga4_period": "2026-08-01..2026-10-29"}):
            cfg = copy.deepcopy(self.cfg)
            cfg["evidence"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(PublishError):
                wave.assert_fresh_evidence(cfg, today=date(2026, 11, 9))

    def test_future_date_and_short_window_fail_closed(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["evidence"]["ga4_period"] = "2026-08-19..2026-11-16"
        cfg["evidence"]["gsc_period"] = "2026-08-22..2026-11-19"
        with self.assertRaisesRegex(PublishError, "future-dated"):
            wave.assert_fresh_evidence(cfg, today=date(2026, 11, 17))
        cfg["evidence"]["gsc_period"] = "2026-11-01..2026-11-09"
        with self.assertRaisesRegex(PublishError, "near-90-day"):
            wave.assert_fresh_evidence(cfg, today=date(2026, 11, 17))

    def test_invalid_period_type_or_calendar_date_fails_closed(self):
        for period in (1, "2026-99-01..2026-10-29", "2026-08-01/2026-10-29"):
            cfg = copy.deepcopy(self.cfg)
            cfg["evidence"]["ga4_period"] = period
            with self.subTest(period=period), self.assertRaises(PublishError):
                wave.assert_fresh_evidence(cfg, today=date(2026, 11, 9))

    def test_snapshot_stops_before_any_wp_access_if_stale(self):
        with mock.patch.object(wave, "normalized_base") as base, \
             mock.patch.object(wave, "wp_request") as wp:
            with self.assertRaises(PublishError):
                wave.snapshot(self.cfg)
            base.assert_not_called()
            wp.assert_not_called()

    def test_apply_stops_before_any_wp_access_if_stale(self):
        with mock.patch.object(wave, "normalized_base") as base, \
             mock.patch.object(wave, "wp_request") as wp:
            with self.assertRaises(PublishError):
                wave.perform(self.cfg, "apply")
            base.assert_not_called()
            wp.assert_not_called()

    def test_restore_is_not_blocked_by_old_evidence(self):
        with mock.patch.object(wave, "normalized_base", side_effect=RuntimeError("restore reachable")):
            with self.assertRaisesRegex(RuntimeError, "restore reachable"):
                wave.perform(self.cfg, "restore")


if __name__ == "__main__":
    unittest.main()
