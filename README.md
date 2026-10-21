# Premier Consumer website monitoring

Five-minute HTTPS availability checks for Premier Consumer, powered by GitHub Actions and Issues.

[Latest checks](https://github.com/JGlen007/premier-consumer-status/actions/workflows/uptime.yml) · [Outage history](https://github.com/JGlen007/premier-consumer-status/issues?q=is%3Aissue)

| Check | Address | Expected result |
| --- | --- | --- |
| Main website | https://www.premierconsumer.org/ | HTTPS, HTTP 200, contains `Premier` |
| Main website without www | https://premierconsumer.org/ | HTTPS, HTTP 200 |
| Bankruptcy | https://bankruptcy.premierconsumer.org/ | HTTPS, HTTP 200 |
| Tax | https://tax.premierconsumer.org/ | HTTPS, HTTP 200 |
| Spanish page | https://premierconsumer.org/librededeudas/ | HTTPS, HTTP 200 |

The checks retry failures three times, ten seconds apart. A confirmed failure opens one incident issue per address. Recovery closes that incident. Each Actions run records response duration and a check summary. Check issue history as well as workflow status: a green run means the monitor executed successfully, and can still contain a website outage.

## Notifications

Select **Watch → All Activity** on this repository and enable your preferred GitHub email or mobile notification delivery. Check notification delivery before retiring UptimeRobot. No SMS or telephone notification service is configured.

## Remaining UptimeRobot settings

The source screenshot truncates the `/debt-m...` address, the Spanish page query string, and does not show the keyword values or whether each keyword must be present or absent. Those settings have not been copied. `Premier` is a provisional homepage check. The Spanish check currently uses the visible base path without the unknown query. Keep existing monitors until these settings and alert delivery have been verified.

## Operating notes

Standard GitHub-hosted Actions runners in this public repository do not consume paid private-repository minutes. GitHub scheduling may be delayed or dropped. Public scheduled workflows can be disabled after 60 days without repository activity; review the Actions page regularly and keep the configuration maintained. This is not an immediate-alert or multi-region monitoring service.

The monitor validates the public response, not forms, payments, WordPress admin, all site pages, or office connectivity. An invalid TLS certificate fails the check, but advance expiry alerts are not configured. A cached page may conceal backend problems. Logs follow the repository's Actions retention setting; persistent incident issues record outages. This version does not calculate uptime percentages or host a separate status website.

Edit `monitoring/sites.json` to change checks. Use **Actions → Premier Consumer uptime → Run workflow** to run immediately. Disable that workflow to stop monitoring.

Local validation: `python3 -m unittest discover -s monitoring -v`.
