import unittest
from unittest.mock import patch
import check
import group_alerts
import report_state


class EnhancementTests(unittest.TestCase):
    def test_language_checks(self):
        for lang, expected in (("es-ES", True), ("en-US", False)):
            with patch.object(check, "http_request", return_value=(200, "https://example.com", f'<html lang="{lang}">'.encode(), 1)):
                self.assertEqual(check.probe({"url": "https://example.com", "language": "es"})["up"], expected)

    def test_performance_requires_three_slow_then_two_fast_checks(self):
        state, sites = {}, [{"id": "one", "name": "One", "url": "https://example.com"}]
        for seconds, expected in ((6, 0), (6, 0), (6, 1), (3, 1), (3, 0)):
            state, bad = report_state.performance(state, sites, [{"up": True, "seconds": seconds}])
            self.assertEqual(len(bad), expected)

    def test_unavailable_page_cannot_resolve_slow_incident(self):
        state, bad = report_state.performance({"one": {"active": True}}, [{"id": "one"}], [{"up": False, "seconds": 15}])
        self.assertEqual(len(bad), 1)

    def test_bounded_history_and_reruns(self):
        data = {"ids": ["one"], "history": [{"run": str(i)} for i in range(2020)]}
        history = report_state.append_sample(data, [{"id": "one"}], [{"up": True, "seconds": 1}], "2019", "now")
        self.assertEqual(len(history), 2016)
        self.assertEqual(sum(r["run"] == "2019" for r in history), 1)

    def test_changed_monitor_list_starts_new_series(self):
        history = report_state.append_sample({"ids": ["old"], "history": [{"run": "old"}]}, [{"id": "new"}], [{"up": True, "seconds": 1}], "new", "now")
        self.assertEqual(len(history), 1)

    def test_five_failed_pages_generate_one_grouped_issue(self):
        failures = [{"id": str(i), "name": str(i), "url": "https://example.com", "detail": "HTTP 500"} for i in range(5)]
        with patch.dict(group_alerts.os.environ, {"GITHUB_RUN_ID": "1"}), patch.object(group_alerts, "api", return_value=[]) as api:
            group_alerts.reconcile_group("owner/repo", "availability", failures)
        posts = [c for c in api.call_args_list if c.args[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertIn("5 pages", posts[0].args[2]["title"])

    def test_unchanged_incident_does_not_notify_again(self):
        failures = [{"id": "one", "name": "One", "url": "https://example.com", "detail": "HTTP 500"}]
        with patch.dict(group_alerts.os.environ, {"GITHUB_RUN_ID": "1"}), patch.object(group_alerts, "api", return_value=[]) as api:
            group_alerts.reconcile_group("owner/repo", "availability", failures)
            body = api.call_args.args[2]["body"]
        row = {"number": 1, "body": body, "user": {"login": "github-actions[bot]"}}
        with patch.dict(group_alerts.os.environ, {"GITHUB_RUN_ID": "2"}), patch.object(group_alerts, "api", return_value=[row]) as api:
            group_alerts.reconcile_group("owner/repo", "availability", failures)
        self.assertEqual([c.args[0] for c in api.call_args_list], ["GET"])

    def test_group_recovery_closes_issue(self):
        row = {"number": 1, "body": "<!-- premier-group:v1:availability -->", "user": {"login": "github-actions[bot]"}}
        with patch.dict(group_alerts.os.environ, {"GITHUB_RUN_ID": "2"}), patch.object(group_alerts, "api", return_value=[row]) as api:
            group_alerts.reconcile_group("owner/repo", "availability", [])
        self.assertEqual(api.call_args.args[2]["state"], "closed")


if __name__ == "__main__":
    unittest.main()
