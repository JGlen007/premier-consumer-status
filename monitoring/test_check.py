import unittest
from unittest.mock import patch
import check


class MonitorTests(unittest.TestCase):
    def test_monitor_incidents_are_isolated(self):
        rows = [{"number": 1, "body": check.MARKER, "user": {"login": "github-actions[bot]"}},
                {"number": 2, "body": check.marker({"id": "tax"}), "user": {"login": "github-actions[bot]"}}]
        with patch.object(check, "api", return_value=rows):
            self.assertEqual([i["number"] for i in check.open_incidents("owner/repo", {"id": "tax"})], [2])

    def test_transient_failure_recovers_without_false_outage(self):
        with patch.object(check, "probe", side_effect=[{"up": False}, {"up": True}]), patch.object(check.time, "sleep"):
            result = check.check()
        self.assertTrue(result["up"])
        self.assertEqual(result["attempts"], 2)

    def test_retries_three_failures(self):
        with patch.object(check, "probe", return_value={"up": False}), patch.object(check.time, "sleep"):
            result = check.check()
        self.assertFalse(result["up"])
        self.assertEqual(result["attempts"], 3)

    def test_incidents_are_not_duplicated(self):
        result = {"up": False, "detail": "timeout", "seconds": 20, "attempts": 3, "checked_at": "now"}
        with patch.dict(check.os.environ, {"GITHUB_RUN_ID": "123"}), patch.object(check, "open_incidents", return_value=[{"number": 1}]), patch.object(check, "api") as api:
            check.reconcile("owner/repo", result)
            api.assert_not_called()

    def test_new_outage_opens_issue_and_recovery_closes_it(self):
        result = {"up": False, "detail": "timeout", "seconds": 20, "attempts": 3, "checked_at": "now"}
        with patch.dict(check.os.environ, {"GITHUB_RUN_ID": "123"}), patch.object(check, "open_incidents", return_value=[]), patch.object(check, "api") as api:
            check.reconcile("owner/repo", result)
            self.assertEqual(api.call_args.args[:2], ("POST", "repos/owner/repo/issues"))
        with patch.dict(check.os.environ, {"GITHUB_RUN_ID": "124"}), patch.object(check, "open_incidents", return_value=[{"number": 1, "body": check.MARKER}]), patch.object(check, "api") as api:
            check.reconcile("owner/repo", {**result, "up": True})
            self.assertEqual(api.call_args.args[:2], ("PATCH", "repos/owner/repo/issues/1"))
            self.assertEqual(api.call_args.args[2]["state"], "closed")

    def test_api_error_is_not_silenced(self):
        with patch.object(check, "api", side_effect=RuntimeError("permission denied")):
            with self.assertRaises(RuntimeError):
                check.open_incidents("owner/repo")


if __name__ == "__main__":
    unittest.main()
