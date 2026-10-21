"""Check the public homepage and reconcile a single GitHub incident per outage."""
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.premierconsumer.org/"
MARKER = "<!-- premier-consumer-uptime:v1 -->"
DEFAULT_SITE = {"id": "homepage", "name": "PremierConsumer.org", "url": URL, "keyword": "Premier"}


def probe(site=None):
    site = site or DEFAULT_SITE
    started = time.monotonic()
    request = urllib.request.Request(site["url"], headers={"User-Agent": "PremierConsumer-Uptime/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(2_000_000).lower()
            if response.status != 200:
                raise ValueError(f"HTTP {response.status}")
            if not response.url.startswith("https://"):
                raise ValueError("Redirected to an insecure HTTP address")
            keyword = site.get("keyword")
            if keyword and keyword.lower().encode() not in body:
                raise ValueError(f"Page did not contain the expected keyword: {keyword}")
            return {"up": True, "detail": "HTTP 200; HTTPS verified" + ("; keyword matched" if keyword else ""), "seconds": round(time.monotonic() - started, 3)}
    except (urllib.error.URLError, OSError, ValueError) as error:
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
    sites = json.loads(Path(__file__).with_name("sites.json").read_text())
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(check, sites))
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write("## Premier Consumer website checks\n\n")
        for site, result in zip(sites, results):
            print(json.dumps({"site": site["id"], **result}))
            message = reconcile(os.environ["GITHUB_REPOSITORY"], result, site)
            summary.write(f"### {site['name']}: {'UP' if result['up'] else 'DOWN'}\n\n"
                          f"{message}\n\nChecked: {result['checked_at']} (UTC)\n\n"
                          f"Duration: {result['seconds']} s · Attempts: {result['attempts']}\n\n"
                          f"[Website]({site['url']})\n\n")


if __name__ == "__main__":
    main()
