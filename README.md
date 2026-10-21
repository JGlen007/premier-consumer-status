# Premier Consumer website monitoring

Five-minute HTTPS availability checks for Premier Consumer, powered by GitHub Actions and Issues.

[Latest checks](https://github.com/JGlen007/premier-consumer-status/actions/workflows/uptime.yml) · [Outage history](https://github.com/JGlen007/premier-consumer-status/issues?q=is%3Aissue)

| Check | Address | Required keyword |
| --- | --- | --- |
| English: Home | https://premierconsumer.org/ | `Consent not required to enroll` |
| English: Free counseling analysis | https://premierconsumer.org/free-credit-counseling-analysis/ | `Get My Free Analysis` |
| English: Free | https://premierconsumer.org/free/ | `Get My Free Analysis` |
| English: Free credit | https://premierconsumer.org/free-credit/ | `Get My Free Analysis` |
| English: Debt management | https://premierconsumer.org/debt-management/ | `Benefits of Our Debt Management Program` |
| English: Bankruptcy counseling | https://premierconsumer.org/bankruptcy-counseling-and-education/ | `Pre-Bankruptcy Course` |
| English: Tax preparation | https://premierconsumer.org/tax-preparation/ | `Get My Tax Estimate` |
| English: Identity protection | https://premierconsumer.org/id-protection-program/ | `Identity Restoration` |
| English: Contact | https://premierconsumer.org/contact-us/ | `Corporate Relations` |
| Spanish: Debt consolidation | https://premierconsumer.org/consolidacion-de-deudas/?lang=es | `Beneficios de nuestro programa` |
| Spanish: Home | https://premierconsumer.org/?lang=es | Status only |
| Spanish: Free analysis | https://premierconsumer.org/analisis-gratis/?lang=es | Status only |
| Spanish: Bankruptcy counseling | https://premierconsumer.org/asesoria-y-educacion-sobre-bancarrota/?lang=es | Status only |
| Spanish: Tax preparation | https://premierconsumer.org/preparacion-de-impuestos/?lang=es | Status only |
| Spanish: Identity protection | https://premierconsumer.org/programa-de-proteccion-de-identidad/?lang=es | Status only |
| Spanish: Contact | https://premierconsumer.org/contacto/?lang=es | Status only |
| Bankruptcy subsite | https://bankruptcy.premierconsumer.org/ | Status only |
| Tax subsite | https://tax.premierconsumer.org/ | Status only |

The checks retry failures three times, ten seconds apart. A confirmed failure opens one incident issue per address. Recovery closes that incident. Each Actions run records response duration and a check summary. Check issue history as well as workflow status: a green run means the monitor executed successfully, and can still contain a website outage.

## Notifications

Select **Watch → All Activity** on this repository and enable your preferred GitHub email or mobile notification delivery. Check notification delivery before retiring UptimeRobot. No SMS or telephone notification service is configured.

## Keyword matching

All 18 URLs and the 10 required keywords match the supplied monitoring list, including the exact Spanish `?lang=es` query strings. Keywords must appear in the returned HTML; matching is case-insensitive. All addresses require valid HTTPS and final HTTP 200. Redirects are followed. Status-only checks do not require a keyword.

Outage and recovery emails were confirmed delivered during a simulated notification test. The test did not alter the websites. Run **Test outage notifications** manually to repeat the delivery test.

## Operating notes

Standard GitHub-hosted Actions runners in this public repository do not consume paid private-repository minutes. GitHub scheduling may be delayed or dropped. Public scheduled workflows can be disabled after 60 days without repository activity; review the Actions page regularly and keep the configuration maintained. This is not an immediate-alert or multi-region monitoring service.

The monitor validates the public response, not forms, payments, WordPress admin, all site pages, or office connectivity. An invalid TLS certificate fails the check, but advance expiry alerts are not configured. A cached page may conceal backend problems. Logs follow the repository's Actions retention setting; persistent incident issues record outages. This version does not calculate uptime percentages or host a separate status website.

Edit `monitoring/sites.json` to change checks. Use **Actions → Premier Consumer uptime → Run workflow** to run immediately. Disable that workflow to stop monitoring.

Local validation: `python3 -m unittest discover -s monitoring -v`.
