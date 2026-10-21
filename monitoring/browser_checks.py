"""Read-only browser checks: no filling, clicking submit, or creating leads."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from group_alerts import reconcile_group
from report_state import load, save


def inspect_form(page):
    forms = page.locator("form.elementor-form")
    for form in forms.all():
        if not form.is_visible():
            continue
        required = [form.locator('input[name="form_fields[name]"]'),
                    form.locator('input[type="email"]'),
                    form.locator('input[id^="form-field-phone"]')]
        if not all(field.count() and field.first.is_visible() and field.first.is_enabled() for field in required):
            continue
        buttons = form.locator('button[type="submit"], input[type="submit"]')
        if any(button.is_visible() and button.is_enabled() for button in buttons.all()):
            return True
    return False


def main():
    from playwright.sync_api import sync_playwright
    sites = json.loads(Path(__file__).with_name("sites.json").read_text())
    selected = [s for s in sites if s["id"] in {"root", "free-analysis", "debt-management", "contact", "es-analysis", "tax", "bankruptcy"}]
    repo = os.environ["GITHUB_REPOSITORY"]
    _, sha = load(repo, "docs/browser-data.json")
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        for site in selected:
            page = context.new_page()
            page.set_default_timeout(15000)
            try:
                response = page.goto(site["url"], wait_until="domcontentloaded", timeout=45000)
                if not response or response.status >= 400:
                    raise ValueError(f"Browser received HTTP {response.status if response else 'no response'}")
                page.locator("form.elementor-form").first.wait_for(state="attached", timeout=15000)
                # Elementor initializes its controls after the document loads.
                page.wait_for_timeout(2000)
                if not inspect_form(page):
                    raise ValueError("No visible, enabled name/email/phone form and submit control found")
                lang = (page.locator("html").get_attribute("lang") or "").split("-")[0]
                if lang != site["language"]:
                    raise ValueError(f"Expected page language {site['language']}; received {lang or 'missing'}")
                result = {**site, "up": True, "detail": "Visible form fields and submit control are enabled; page language matched"}
            except Exception as error:
                result = {**site, "up": False, "detail": str(error).split("\n")[0][:300]}
            results.append(result)
            print(json.dumps(result), flush=True)
            page.close()
        browser.close()
    failures = [r for r in results if not r["up"]]
    enabled = os.environ.get("BROWSER_ALERTS", "false").lower() == "true"
    if enabled:
        reconcile_group(repo, "forms and buttons", failures)
    record = {"generated_at": datetime.now(timezone.utc).isoformat(), "checks": results,
              "alerts_enabled": enabled,
              "run_url": f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"}
    save(repo, "docs/browser-data.json", record, sha)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write("## Read-only form and button checks\n\nNo forms were filled or submitted.\n\n")
        for r in results:
            f.write(f"- **{r['name']}**: {'PASS' if r['up'] else 'ATTENTION'} — {r['detail']}\n")
    # Failed form checks are recorded as grouped incidents; infrastructure failures
    # throw and fail the workflow independently.


if __name__ == "__main__":
    main()
