"""Check the public homepage and reconcile a single GitHub incident per outage."""
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from http_probe import request as http_request
from html.parser import HTMLParser


class PageLanguage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.language = ""

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            self.language = dict(attrs).get("lang", "").lower()

URL = "https://www.premierconsumer.org/"
MARKER = "<!-- premier-consumer-uptime:v1 -->"
DEFAULT_SITE = {"id": "homepage", "name": "PremierConsumer.org", "url": URL, "keyword": "Premier"}


def probe(site=None):
    site = site or DEFAULT_SITE
    started = time.monotonic()
    try:
        status, final_url, body, seconds = http_request(site["url"], timeout=15)
        if not 200 <= status < 400:
            raise ValueError(f"HTTP {status}")
        if not final_url.startswith("https://"):
            raise ValueError("Redirected to an insecure HTTP address")
        keyword = site.get("keyword")
        html = body.decode("utf-8", errors="replace")
        if keyword and keyword.casefold() not in html.casefold():
            raise ValueError(f"Page did not contain the expected keyword: {keyword}")
        if site.get("language"):
            page = PageLanguage()
            page.feed(html)
            if page.language.split("-")[0] != site["language"]:
                raise ValueError(f"Expected {site['language']} page language; received {page.language or 'no language declaration'}")
        return {"up": True, "detail": f"HTTP {status}; HTTPS verified" + ("; keyword matched" if keyword else ""), "seconds": seconds}
    except (urllib.error.URLError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {"up": False, "detail": str(error)[:300], "seconds": round(time.monotonic() - started, 3)}


def check(site=None, attempts=3, pause=10):
    results = []
    for attempt in range(attempts):
        results.append(probe(site))
        if results[-1]["up"]:
            break
        if attempt < attempts - 1:
            time.sleep(pause)
    return {**results[-1], "attempts": len(results), "checked_at": datetime.now(timezone.utc).isoformat()}


def api(method, path, payload=None):
    token = os.environ["GH_TOKEN"]
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        "https://api.github.com/" + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def marker(site=None):
    site = site or DEFAULT_SITE
    return MARKER if site["id"] == "homepage" else f"<!-- premier-consumer-uptime:v1:{site['id']} -->"


def open_incidents(repo, site=None):
    incidents = []
    page = 1
    while True:
        rows = api("GET", f"repos/{repo}/issues?state=open&per_page=100&page={page}")
        incidents.extend(row for row in rows if "pull_request" not in row and marker(site) in (row.get("body") or "")
                         and row.get("user", {}).get("login") == "github-actions[bot]")
        if len(rows) < 100:
            return incidents
        page += 1


def reconcile(repo, result, site=None):
    site = site or DEFAULT_SITE
    incidents = open_incidents(repo, site)
    run_url = f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    detail = (f"Checked: {result['checked_at']} (UTC)\n\n"
              f"Website: {site['url']}\n\nResult: {result['detail']}\n\n"
              f"Response duration: {result['seconds']} seconds; attempts: {result['attempts']}.\n\n"
              f"[Check details]({run_url})")
    if not result["up"] and not incidents:
        api("POST", f"repos/{repo}/issues", {
            "title": "Website outage: " + site["name"],
            "body": marker(site) + "\n\nThree consecutive attempts failed.\n\n" + detail,
        })
        return "New outage recorded"
    if result["up"] and incidents:
        for issue in incidents:
            # Put recovery details in the close request so a retry cannot duplicate comments.
            api("PATCH", f"repos/{repo}/issues/{issue['number']}", {
                "state": "closed", "state_reason": "completed",
                "title": "Recovered: " + site["name"],
                "body": issue["body"] + "\n\n---\n\n## Recovery\n\n" + detail,
            })
        return "Recovery recorded; incident closed"
    return "Healthy" if result["up"] else "Existing outage continues; no duplicate incident"


def main():
    from group_alerts import reconcile_group
    from report_state import load, save, performance, append_sample, incident_history
    sites = json.loads(Path(__file__).with_name("sites.json").read_text())
    repo = os.environ["GITHUB_REPOSITORY"]
    data, sha = load(repo, "docs/monitor-data.json")
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(check, sites))
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write("## Premier Consumer website checks\n\n")
        failures = []
        for site, result in zip(sites, results):
            print(json.dumps({"site": site["id"], **result}))
            message = "Healthy" if result["up"] else result["detail"]
            if not result["up"]:
                failures.append({**site, "detail": result["detail"]})
            summary.write(f"### {site['name']}: {'UP' if result['up'] else 'DOWN'}\n\n"
                          f"{message}\n\nChecked: {result['checked_at']} (UTC)\n\n"
                          f"Duration: {result['seconds']} s · Attempts: {result['attempts']}\n\n"
                          f"[Website]({site['url']})\n\n")
        summary.write("\n" + reconcile_group(repo, "availability", failures) + "\n")
        performance_state, slow = performance(data.get("performance", {}), sites, results)
        summary.write("\n" + reconcile_group(repo, "slow pages", slow) + "\n")
    stamp = datetime.now(timezone.utc).isoformat()
    run_id = os.environ["GITHUB_RUN_ID"]
    record = {"generated_at": stamp, "cadence_seconds": 300,
              "run_url": f"https://github.com/{repo}/actions/runs/{run_id}",
              "sites": sites, "ids": [s["id"] for s in sites], "checks": results,
              "history": append_sample(data, sites, results, run_id, stamp),
              "performance": performance_state, "incidents": incident_history(repo)}
    save(repo, "docs/monitor-data.json", record, sha)


if __name__ == "__main__":
    main()
