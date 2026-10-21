import socket
import unittest
from unittest.mock import MagicMock, patch

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
        addresses = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 443)),
                     (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        ipv4, ipv6 = MagicMock(), MagicMock()
        ipv4.connect.side_effect = OSError("IPv4 unavailable")
        with patch.object(http_probe.socket, "getaddrinfo", return_value=addresses), patch.object(http_probe.socket, "socket", side_effect=[ipv4, ipv6]):
            connected = http_probe.connect_ipv4_first(("example.com", 443))
        self.assertIs(connected, ipv6)
        ipv4.connect.assert_called_once_with(("127.0.0.1", 443))
        ipv4.close.assert_called_once()
        ipv6.connect.assert_called_once_with(("::1", 443))

    def test_insecure_redirect_is_rejected(self):
        with self.assertRaises(ValueError):
            http_probe.HTTPSRedirectHandler().redirect_request(None, None, 302, "", {}, "http://example.com")

    def test_fallback_cannot_restart_fifteen_second_budget(self):
        addresses = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
                     (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 443))]
        sock = MagicMock()
        sock.connect.side_effect = OSError("timeout")
        with patch.object(http_probe.time, "monotonic", side_effect=[0, 0, 15.1]), patch.object(http_probe.socket, "getaddrinfo", return_value=addresses), patch.object(http_probe.socket, "socket", return_value=sock) as create:
            with self.assertRaises(TimeoutError):
                http_probe.connect_ipv4_first(("example.com", 443))
        self.assertEqual(create.call_count, 1)


if __name__ == "__main__":
    unittest.main()
