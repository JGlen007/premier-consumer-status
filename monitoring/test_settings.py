import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import check
import http_probe


class HTTPSettingsTests(unittest.TestCase):
    def test_accepts_success_and_redirect_status_classes(self):
        for status in (200, 204, 206, 300, 304, 399):
            with self.subTest(status=status), patch.object(check, "http_request", return_value=(status, "https://example.com", b"", 0.2)):
                self.assertTrue(check.probe({"url": "https://example.com"})["up"])

    def test_http_error_still_fails(self):
        with patch.object(check, "http_request", return_value=(404, "https://example.com", b"", 0.2)):
            self.assertFalse(check.probe({"url": "https://example.com"})["up"])

    def test_keyword_required_even_if_http_status_is_healthy(self):
        with patch.object(check, "http_request", return_value=(200, "https://example.com", b"Wrong page", 0.2)):
            self.assertFalse(check.probe({"url": "https://example.com", "keyword": "Expected"})["up"])

    def test_unicode_case_insensitive_keyword(self):
        with patch.object(check, "http_request", return_value=(200, "https://example.com", "EDUCACIÓN".encode(), 0.2)):
            self.assertTrue(check.probe({"url": "https://example.com", "keyword": "educación"})["up"])

    def test_tls_validation_error_is_reported(self):
        with patch.object(check, "http_request", side_effect=OSError("certificate verify failed")):
            self.assertFalse(check.probe()["up"])

    def test_ipv4_preferred_then_ipv6_on_connection_failure(self):
        commands = []
        def execute(command, **kwargs):
            commands.append(command)
            if "--ipv4" in command:
                return subprocess.CompletedProcess(command, 7, b"", b"connect failed")
            Path(command[command.index("--output") + 1]).write_bytes(b"page")
            return subprocess.CompletedProcess(command, 0, b"200\nhttps://example.com", b"")
        with patch.object(http_probe.subprocess, "run", side_effect=execute):
            status, _, body, _ = http_probe.request("https://example.com")
        self.assertEqual((status, body), (200, b"page"))
        self.assertIn("--ipv4", commands[0])
        self.assertIn("--ipv6", commands[1])
        self.assertIn("--location", commands[0])
        self.assertLessEqual(float(commands[0][commands[0].index("--max-time") + 1]), 15)

    def test_no_ipv6_fallback_for_bad_certificate(self):
        with patch.object(http_probe.subprocess, "run", return_value=subprocess.CompletedProcess([], 60, b"", b"SSL certificate error")) as run:
            with self.assertRaises(OSError):
                http_probe.request("https://example.com")
        self.assertEqual(run.call_count, 1)

    def test_fallback_cannot_restart_fifteen_second_budget(self):
        with patch.object(http_probe.time, "monotonic", side_effect=[0, 0, 15.1]), patch.object(http_probe.subprocess, "run", return_value=subprocess.CompletedProcess([], 28, b"", b"timeout")) as run:
            with self.assertRaises(TimeoutError):
                http_probe.request("https://example.com")
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
