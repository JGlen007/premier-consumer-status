"""HTTPS requests using urllib, with IPv4 priority and IPv6 fallback."""
import http.client
import socket
import ssl
import time
import urllib.error
import urllib.request


def connect_ipv4_first(address, timeout=15, source_address=None):
    started = time.monotonic()
    hosts = sorted(socket.getaddrinfo(*address, type=socket.SOCK_STREAM),
                   key=lambda row: row[0] != socket.AF_INET)
    last_error = OSError("No addresses found")
    for family, socktype, proto, _, sockaddr in hosts:
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Connection timed out")
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(min(5, remaining))
        try:
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            sock.settimeout(max(0.1, timeout - (time.monotonic() - started)))
            return sock
        except OSError as error:
            last_error = error
            sock.close()
    raise last_error


class PriorityHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = connect_ipv4_first


class PriorityHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(PriorityHTTPSConnection, request, context=self._context)


class HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith("https://"):
            raise ValueError("Redirected to an insecure HTTP address")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def request(url, timeout=15):
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS URLs are supported")
    started = time.monotonic()
    opener = urllib.request.build_opener(
        PriorityHTTPSHandler(),
        HTTPSRedirectHandler(),
    )
    req = urllib.request.Request(url, headers={"User-Agent": "PremierConsumer-Uptime/1.0"})
    try:
        response = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as error:
        # urllib treats unfollowed redirects and 4xx/5xx as exceptions.
        # Return them for the monitor's explicit status-class policy.
        response = error
    with response:
        return (response.code, response.url, response.read(5_000_000),
                round(time.monotonic() - started, 3))
