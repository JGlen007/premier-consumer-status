"""Persist public monitoring samples in the repository; no customer data."""
import base64
import json
import urllib.error
from check import api


def load(repo, path):
    try:
        row = api("GET", f"repos/{repo}/contents/{path}")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}, None
        raise
    if not row.get("content"):
        raise ValueError("Monitoring history could not be read; refusing to overwrite it")
    return json.loads(base64.b64decode(row["content"])), row["sha"]


def save(repo, path, data, sha):
    payload = {"message": f"Record {path.rsplit('/',1)[-1]} check results",
               "content": base64.b64encode(json.dumps(data, separators=(",", ":")).encode()).decode()}
    if sha:
        payload["sha"] = sha
    api("PUT", f"repos/{repo}/contents/{path}", payload)


def performance(previous, sites, results):
    state, failures = {}, []
    for site, result in zip(sites, results):
        old = previous.get(site["id"], {})
        slow = result["up"] and result["seconds"] > 5
        good = result["up"] and result["seconds"] <= 4
        bad_count = old.get("bad", 0) + 1 if slow else 0
        good_count = old.get("good", 0) + 1 if good else 0
        active = old.get("active", False)
        if bad_count >= 3:
            active = True
        if good_count >= 2:
            active = False
        # An availability incident already covers a page that stops responding.
        state[site["id"]] = {"bad": bad_count, "good": good_count, "active": active}
        if active:
            failures.append({**site, "detail": "Sustained slow response (over 5 seconds); recovery requires two checks at 4 seconds or less"})
    return state, failures


def append_sample(data, sites, results, run_id, timestamp):
    ids = [site["id"] for site in sites]
    # A changed monitor list starts a new series rather than mislabeling columns.
    history = data.get("history", []) if data.get("ids") == ids else []
    history = [row for row in history if row.get("run") != run_id]
    history.append({"at": timestamp, "run": run_id,
                    "up": [r["up"] for r in results],
                    "ms": [round(r["seconds"] * 1000) for r in results]})
    return history[-2016:]


def incident_history(repo):
    rows = api("GET", f"repos/{repo}/issues?state=all&sort=updated&direction=desc&per_page=100")
    return [{"title": r["title"], "state": r["state"], "opened": r["created_at"],
             "closed": r.get("closed_at"), "url": r["html_url"]}
            for r in rows if "pull_request" not in r and "<!-- premier-group:v1:" in (r.get("body") or "")
            and r.get("user", {}).get("login") == "github-actions[bot]"][:20]
