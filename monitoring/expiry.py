"""Daily certificate and domain reminders, with GitHub issues as durable state."""
import json
import math
import os
import socket
import ssl
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from check import api
from http_probe import request

PREFIX = "<!-- premier-expiry:v1:"


def now():
    return datetime.now(timezone.utc)


def connect(host, port=443, timeout=15):
    started = time.monotonic()
    addresses = sorted(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM),
                       key=lambda entry: entry[0] != socket.AF_INET)
    last_error = OSError("No addresses found")
    for family, socktype, proto, _, address in addresses:
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Certificate connection timed out")
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(min(5, remaining))
        try:
            sock.connect(address)
            sock.settimeout(max(0.1, timeout - (time.monotonic() - started)))
            return sock
        except OSError as error:
            last_error = error
            sock.close()
    raise last_error


def certificate_expiry(host):
    context = ssl.create_default_context()
    with connect(host) as raw:
        with context.wrap_socket(raw, server_hostname=host) as connection:
            certificate = connection.getpeercert()
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(certificate["notAfter"]), timezone.utc)


def get_json(url):
    status, _, body, _ = request(url, timeout=15)
    if status != 200:
        raise ValueError(f"RDAP lookup returned HTTP {status}")
    return json.loads(body)


def parse_rdap_expiry(data):
    dates = [datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
             for event in data.get("events", []) if event.get("eventAction") == "expiration"]
    if not dates or any(date.tzinfo is None for date in dates):
        raise ValueError("Registry did not return a usable domain expiration date")
    return min(dates).astimezone(timezone.utc)


def domain_expiry(domain):
    bootstrap = get_json("https://data.iana.org/rdap/dns.json")
    tld = domain.rsplit(".", 1)[-1].lower()
    bases = [base for names, urls in bootstrap["services"] if tld in names
             for base in urls if base.startswith("https://")]
    if not bases:
        raise ValueError("No authoritative HTTPS RDAP service found")
    return parse_rdap_expiry(get_json(bases[0].rstrip("/") + "/domain/" + quote(domain, safe="")))


def threshold(expiration, current, thresholds):
    days = math.floor((expiration - current).total_seconds() / 86400)
    due = [value for value in thresholds if days <= value]
    return days, min(due) if due else None


def marker(kind, asset, expiration, level):
    return f"{PREFIX}{kind}:{asset}:{expiration.isoformat()}:{level} -->"


def list_notices(repo):
    rows = []
    page = 1
    while True:
        batch = api("GET", f"repos/{repo}/issues?state=all&per_page=100&page={page}")
        rows.extend(row for row in batch if "pull_request" not in row
                    and row.get("user", {}).get("login") == "github-actions[bot]"
                    and PREFIX in (row.get("body") or ""))
        if len(batch) < 100:
            return rows
        page += 1


def close_notice(repo, row, reason):
    api("PATCH", f"repos/{repo}/issues/{row['number']}", {
        "state": "closed", "state_reason": "completed",
        "title": "Resolved: " + row["title"].removeprefix("Resolved: "),
        "body": row["body"] + "\n\n## Resolved\n\n" + reason,
    })
    row["state"] = "closed"


def reconcile(repo, notices, result, thresholds, current=None):
    current = current or now()
    kind, asset = result["kind"], result["asset"]
    asset_prefix = f"{PREFIX}{kind}:{asset}:"
    error_marker = asset_prefix + "lookup-error -->"
    related = [row for row in notices if asset_prefix in row["body"]]
    run = f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    if "error" in result:
        if not any(row["state"] == "open" and error_marker in row["body"] for row in related):
            api("POST", f"repos/{repo}/issues", {
                "title": f"Expiry check failed: {kind} for {asset}",
                "body": error_marker + f"\n\nCould not verify expiry after three attempts. This does not establish that the asset is expired.\n\n{result['error']}\n\n[Check details]({run})",
            })
        return "Expiry lookup failed; notification recorded"
    expiration = result["expires"]
    days, level = threshold(expiration, current, thresholds)
    cycle_prefix = asset_prefix + expiration.isoformat() + ":"
    for row in related:
        if row["state"] == "open" and (error_marker in row["body"] or cycle_prefix not in row["body"]):
            close_notice(repo, row, f"Current verified expiration: {expiration.isoformat()}. [Check details]({run})")
    if level is None:
        return f"Healthy: {days} days until expiry ({expiration.date()})"
    tag = marker(kind, asset, expiration, level)
    if not any(tag in row["body"] for row in related):
        api("POST", f"repos/{repo}/issues", {
            "title": f"Expiry reminder: {kind} for {asset} ({level}-day threshold)",
            "body": tag + f"\n\n**{asset}** has {days} whole days remaining.\n\nExpiration: **{expiration.isoformat()}** (UTC).\n\nReminder threshold: {level} days.\n\n[Check details]({run})\n\n" +
                    ("Renew the certificate before it expires." if kind == "certificate" else "This is the registry-reported domain expiration date. Confirm renewal and billing dates with your registrar."),
        })
    return f"Reminder: {days} days remaining; {level}-day threshold ({expiration.date()})"


def lookup(item):
    kind, asset = item
    for attempt in range(3):
        try:
            expiration = certificate_expiry(asset) if kind == "certificate" else domain_expiry(asset)
            return {"kind": kind, "asset": asset, "expires": expiration}
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
            message = str(error)[:300]
            if attempt < 2:
                time.sleep(5)
    return {"kind": kind, "asset": asset, "error": message}


def main():
    settings = json.loads(Path(__file__).with_name("expiry-settings.json").read_text())
    items = [("certificate", host) for host in settings["certificate_hosts"]]
    items += [("domain", domain) for domain in settings["domains"]]
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lookup, items))
    repo = os.environ["GITHUB_REPOSITORY"]
    notices = list_notices(repo)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write("## Certificate and domain expiry\n\n")
        for result in results:
            print(json.dumps(result, default=str), flush=True)
            message = reconcile(repo, notices, result, settings["thresholds_days"])
            summary.write(f"### {result['kind']}: {result['asset']}\n\n{message}\n\n")
    if any("error" in result for result in results):
        raise SystemExit("One or more expiry lookups failed; see the summary and issues")


if __name__ == "__main__":
    main()
