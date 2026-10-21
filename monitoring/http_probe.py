"""Bounded HTTPS requests, preferring IPv4 with an IPv6 fallback."""
import subprocess
import tempfile
import time
from pathlib import Path


def request(url, timeout=15):
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "body"
        for family in ("--ipv4", "--ipv6"):
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError(f"Request exceeded {timeout} seconds")
            process = subprocess.run([
                "curl", "--silent", "--show-error", "--location", "--max-redirs", "10",
                "--proto", "=https", "--proto-redir", "=https", family,
                "--connect-timeout", str(min(5, remaining)), "--max-time", str(remaining),
                "--max-filesize", "5000000", "--user-agent", "PremierConsumer-Uptime/1.0",
                "--output", str(output), "--write-out", "%{http_code}\n%{url_effective}",
                "--url", url,
            ], capture_output=True, timeout=remaining + 2)
            if process.returncode == 0:
                status, final_url = process.stdout.decode().split("\n", 1)
                return int(status), final_url, output.read_bytes(), round(time.monotonic() - started, 3)
            # Retry only network establishment/timeouts; an HTTP status, invalid
            # certificate, redirect error, or content error cannot trigger fallback.
            if family == "--ipv4" and process.returncode in (5, 6, 7, 28):
                continue
            raise OSError(process.stderr.decode(errors="replace")[:300] or f"curl error {process.returncode}")
    raise TimeoutError(f"Request exceeded {timeout} seconds")
