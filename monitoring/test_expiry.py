import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import expiry


class ExpiryTests(unittest.TestCase):
    def setUp(self):
        self.current = datetime(2026, 10, 21, tzinfo=timezone.utc)
        self.expiration = self.current + timedelta(days=12)
        self.result = {"kind": "certificate", "asset": "example.com", "expires": self.expiration}

    def test_threshold_boundaries_and_missed_windows(self):
        for days, expected in ((31, None), (30, 30), (15, 30), (14, 14), (8, 14), (7, 7), (1, 7), (0, 0), (-1, 0)):
            with self.subTest(days=days):
                self.assertEqual(expiry.threshold(self.current + timedelta(days=days), self.current, [30, 14, 7, 0]), (days, expected))

    def test_zero_day_reminder_while_certificate_is_still_valid(self):
        self.assertEqual(expiry.threshold(self.current + timedelta(hours=12), self.current, [30, 14, 7, 0]), (0, 0))

    def test_only_domain_expiration_event_is_used(self):
        data = {"events": [{"eventAction": "registration", "eventDate": "2001-01-01T00:00:00Z"}, {"eventAction": "expiration", "eventDate": "2028-06-01T00:00:00Z"}]}
        self.assertEqual(expiry.parse_rdap_expiry(data).year, 2028)

    def test_missing_rdap_expiration_is_an_error(self):
        with self.assertRaises(ValueError):
            expiry.parse_rdap_expiry({"events": []})

    def test_registry_service_comes_from_iana(self):
        bootstrap = {"services": [[["org"], ["https://registry.example/rdap/"]]]}
        data = {"events": [{"eventAction": "expiration", "eventDate": "2028-06-01T00:00:00Z"}]}
        with patch.object(expiry, "get_json", side_effect=[bootstrap, data]) as get:
            expiry.domain_expiry("example.org")
        self.assertEqual(get.call_args_list[1].args[0], "https://registry.example/rdap/domain/example.org")

    def test_first_reminder_created_once_per_date_and_threshold(self):
        tag = expiry.marker("certificate", "example.com", self.expiration, 14)
        row = {"number": 1, "state": "closed", "body": tag, "title": "prior reminder"}
        with patch.dict(expiry.os.environ, {"GITHUB_RUN_ID": "1"}), patch.object(expiry, "api") as api:
            expiry.reconcile("owner/repo", [], self.result, [30, 14, 7, 0], self.current)
            self.assertEqual(api.call_args.args[0], "POST")
            api.reset_mock()
            expiry.reconcile("owner/repo", [row], self.result, [30, 14, 7, 0], self.current)
            api.assert_not_called()

    def test_escalation_sends_new_threshold_notification(self):
        row = {"number": 1, "state": "open", "body": expiry.marker("certificate", "example.com", self.expiration, 30), "title": "prior reminder"}
        with patch.dict(expiry.os.environ, {"GITHUB_RUN_ID": "1"}), patch.object(expiry, "api") as api:
            expiry.reconcile("owner/repo", [row], self.result, [30, 14, 7, 0], self.current)
        self.assertEqual(api.call_args.args[0], "POST")
        self.assertIn("14-day threshold", api.call_args.args[2]["title"])

    def test_renewal_resolves_old_reminders(self):
        old_date = self.current - timedelta(days=1)
        row = {"number": 1, "state": "open", "body": expiry.marker("certificate", "example.com", old_date, 0), "title": "prior reminder"}
        with patch.dict(expiry.os.environ, {"GITHUB_RUN_ID": "1"}), patch.object(expiry, "api") as api:
            expiry.reconcile("owner/repo", [row], {**self.result, "expires": self.current + timedelta(days=90)}, [30, 14, 7, 0], self.current)
        self.assertEqual(api.call_args.args[0], "PATCH")
        self.assertEqual(api.call_args.args[2]["state"], "closed")

    def test_lookup_error_not_reported_as_expired(self):
        with patch.dict(expiry.os.environ, {"GITHUB_RUN_ID": "1"}), patch.object(expiry, "api") as api:
            expiry.reconcile("owner/repo", [], {"kind": "domain", "asset": "example.org", "error": "lookup unavailable"}, [30, 14, 7, 0], self.current)
        self.assertIn("Expiry check failed", api.call_args.args[2]["title"])
        self.assertNotIn("Expiry reminder", api.call_args.args[2]["title"])

    def test_recovered_lookup_closes_error_issue(self):
        row = {"number": 1, "state": "open", "body": expiry.PREFIX + "certificate:example.com:lookup-error -->", "title": "Expiry check failed"}
        with patch.dict(expiry.os.environ, {"GITHUB_RUN_ID": "1"}), patch.object(expiry, "api") as api:
            expiry.reconcile("owner/repo", [row], {**self.result, "expires": self.current + timedelta(days=90)}, [30, 14, 7, 0], self.current)
        self.assertEqual(api.call_args.args[0], "PATCH")

    def test_lookup_failure_retries_then_returns_error(self):
        with patch.object(expiry, "certificate_expiry", side_effect=OSError("TLS error")) as lookup, patch.object(expiry.time, "sleep"):
            result = expiry.lookup(("certificate", "example.com"))
        self.assertEqual(lookup.call_count, 3)
        self.assertEqual(result["error"], "TLS error")


if __name__ == "__main__":
    unittest.main()
