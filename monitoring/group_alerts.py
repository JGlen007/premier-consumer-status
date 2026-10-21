"""One incident per category, with email updates only when affected pages change."""
import hashlib
import json
import os
from datetime import datetime, timezone
from check import api


def reconcile_group(repo, category, failures):
    tag = f"<!-- premier-group:v1:{category} -->"
    incidents, page = [], 1
    while True:
        rows = api("GET", f"repos/{repo}/issues?state=open&per_page=100&page={page}")
        incidents += [r for r in rows if "pull_request" not in r and tag in (r.get("body") or "")
                      and r.get("user", {}).get("login") == "github-actions[bot]"]
        if len(rows) < 100:
            break
        page += 1
    stamp = datetime.now(timezone.utc).isoformat()
    run = f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    if not failures:
        for issue in incidents:
            api("PATCH", f"repos/{repo}/issues/{issue['number']}", {
                "state": "closed", "state_reason": "completed",
                "title": f"Recovered: Premier Consumer {category}",
                "body": issue["body"] + f"\n\n## Recovered\n\nAll checks in this category passed at {stamp}. [Run details]({run}).",
            })
        return "Recovery notification recorded" if incidents else "Healthy"
    failures = sorted(failures, key=lambda r: r["id"])
    fingerprint = hashlib.sha256(json.dumps([(r["id"], r["detail"]) for r in failures]).encode()).hexdigest()
    fp_tag = f"<!-- fingerprint:{fingerprint} -->"
    details = "\n".join(f"- **{r['name']}**: {r['detail']} ([page]({r['url']}))" for r in failures)
    body = f"{tag}\n{fp_tag}\n\n## Current affected pages\n\n{details}\n\nChecked: {stamp} (UTC). [Run details]({run})."
    if not incidents:
        api("POST", f"repos/{repo}/issues", {"title": f"Attention: Premier Consumer {category} ({len(failures)} pages)", "body": body})
        return "Grouped notification recorded"
    for issue in incidents:
        if fp_tag not in issue["body"]:
            api("POST", f"repos/{repo}/issues/{issue['number']}/comments", {"body": "## Affected pages changed\n\n" + details + f"\n\n[Run details]({run})"})
            api("PATCH", f"repos/{repo}/issues/{issue['number']}", {"body": body, "title": f"Attention: Premier Consumer {category} ({len(failures)} pages)"})
    return "Existing incident continues"
