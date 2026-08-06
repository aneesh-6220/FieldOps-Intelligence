# Summit private pilot deployment

This runbook deploys FieldOps Intelligence as one private Streamlit Community Cloud
application for Summit Outdoor Services, backed by two separate managed PostgreSQL
databases.

Follow the sections in order. Every command is run from the repository root.

## 1. Pilot purpose and the synthetic-data limitation

The pilot lets a small number of invited Summit people use the real lead-to-job
workflow on a hosted URL, and lets the developer demonstrate the project as portfolio
work. It is not a production system.

**Only synthetic or anonymized records may be entered during the pilot. Real customer
personal information — real names, addresses, phone numbers, or email addresses — is
prohibited.** The application has no authentication of its own, no encryption workflow,
no audit trail, no backups, and no retention controls. Access is limited only by
Streamlit Community Cloud's viewer invitations. Treat anything entered as
demonstration data that other invited viewers can see.

## 2. Required accounts

| Account | Used for | Owned by |
| --- | --- | --- |
| GitHub | Private repository holding the code | Developer |
| Streamlit Community Cloud | Hosting, private access, secrets | Developer |
| A managed PostgreSQL provider | Two hosted databases | Developer |

The developer owns all three during the pilot. Summit people receive viewer
invitations only; they never need an account on the database or GitHub.

## 3. Create or select a private GitHub repository

1. Create a new repository, or open the existing one.
2. Confirm its visibility is **Private**.
3. Push the current `main` branch.
4. Confirm the repository contains no `.env`, no `.streamlit/secrets.toml`, and no
   `*.db` files. `.gitignore` already excludes all of them.

## 4. Create one managed PostgreSQL project

Any provider offering a managed PostgreSQL instance with SSL works. A free tier is
acceptable; occasional cold starts on first request are expected and fine.

1. Create a single PostgreSQL project or instance.
2. Choose a region near the users.
3. Note that the free tier may pause when idle — the first page load after a pause
   can take several seconds.

## 5. Create `fieldops_operational`

Inside that one project, create a database named:

```
fieldops_operational
```

This holds Summit's real workspace. It must start completely empty.

## 6. Create `fieldops_demo`

Inside the same project, create a second, physically separate database named:

```
fieldops_demo
```

This holds the deterministic synthetic Summit dataset. It must be a different
database — not a different schema, and not the same database with a prefix. The
application refuses to start if both URLs resolve to the same database.

## 7. Obtain two distinct SQLAlchemy-compatible connection URLs

From the provider's connection panel, copy the connection string for each database.
Providers usually hand out a `postgresql://` URL. Convert each one to the SQLAlchemy
form below.

## 8. Use the `postgresql+psycopg` URL form

SQLAlchemy needs the driver named explicitly so it selects Psycopg 3:

```
postgresql+psycopg://USERNAME:PASSWORD@HOST/fieldops_operational?sslmode=require
postgresql+psycopg://USERNAME:PASSWORD@HOST/fieldops_demo?sslmode=require
```

Replace `USERNAME`, `PASSWORD`, and `HOST` with the provider's values. If the provider
gave you `postgresql://…`, change only the scheme to `postgresql+psycopg://` and leave
the rest untouched.

## 9. Enable SSL through the provider's supplied URL

Keep the provider's SSL query parameter on the URL — usually `?sslmode=require`. The
application passes query parameters straight through to the driver and never rewrites
them. Do not strip it.

## 10. Add the URLs through Streamlit Community Cloud secrets

In the app's **Settings → Secrets** panel, paste the following template and replace the
placeholders with the real values. **Placeholders only ever appear in this document;
real values are typed into Streamlit's Secrets interface and nowhere else.**

```toml
FIELDOPS_DATABASE_URL = "postgresql+psycopg://..."
FIELDOPS_DEMO_DATABASE_URL = "postgresql+psycopg://..."
FIELDOPS_LOG_LEVEL = "INFO"
FIELDOPS_AUTO_SEED = "false"
```

Streamlit exposes these as environment variables, which is exactly how the application
reads its configuration. Never commit these values to Git, never paste them into an
issue or chat, and never put them in `.env` on a shared machine.

`FIELDOPS_AUTO_SEED` must stay `"false"`. Demo data is loaded deliberately from the
sidebar, and only into the demo database.

## 11. Select Python 3.12

In the deploy dialog's advanced settings, choose **Python 3.12**. `requirements.txt`
pins versions that have prebuilt Python 3.12 Linux wheels, so installation needs no
compiler.

## 12. Select `app/main.py`

Set the main file path to:

```
app/main.py
```

## 13. Deploy the app

Click **Deploy**. The first build installs dependencies from `requirements.txt` and can
take a few minutes. The application creates its own tables on first run in both
databases; no separate migration step is required for a fresh deployment.

## 14. Make the app private

In **Settings → Sharing**, set the app so it is **not** public. Only invited viewers
should be able to open the URL. Confirm by opening the URL in a private browser window
while signed out — it must ask for sign-in rather than showing the workspace.

## 15. Invite Summit viewers by email

In **Settings → Sharing**, add each Summit person's email address as a **viewer**.
Invite individual addresses rather than a whole domain. Each person signs in with that
email address to open the app.

## 16. Remove a viewer

In the same **Sharing** panel, delete the person's email address. Access ends
immediately. Do this as soon as someone no longer needs the pilot.

## 17. Run the deployment-readiness command locally

Before or after deploying, verify both databases from your own machine. Export the same
two URLs into your shell — or put them in a local `.env` that is never committed — then
run:

```bash
python scripts/check_deployment.py
```

The command connects to both databases, creates the baseline schema if missing,
verifies the operational database holds no demo data and the demo database holds no
real workspace, and prints only the role, dialect, connection status, schema status,
and workspace state. **It never seeds either database and never prints a URL, username,
password, hostname, or query parameter.** It exits `0` when ready and non-zero with a
short actionable message when it is not.

## 18. Create Summit's blank operational workspace

Open the deployed URL. Because the operational database is empty, the app shows the
setup screen with two choices. Choose **Create a real workspace** and enter Summit's
business name, industry, currency code, and timezone.

This creates only the business profile with `demo_data=false`. It creates zero leads,
customers, workers, services, jobs, and activity records. The demo banner never appears
in this workspace.

## 19. Configure Summit's company profile and service catalog

1. Open **Settings** and confirm the business details and insight thresholds.
2. Open **Services** and add Summit's real service offerings with prices, durations,
   and default costs.
3. Open **Team** and add workers. Use initials or role labels rather than real full
   names and contact details during the pilot.

## 20. Load the demo workspace

Click **Open demo workspace** in the sidebar. This seeds the deterministic Summit
dataset into `fieldops_demo` only, and the app enters a clearly labelled demo mode with
a warning in the sidebar and a banner above the page. Nothing is written to
`fieldops_operational`.

## 21. Reset demo data

While in demo mode, click **Reset demo workspace**. This clears and reseeds only
`fieldops_demo`. It refuses to run against a database containing a real workspace, so
operational data cannot be touched.

## 22. Return to operational mode

Click **Return to real workspace**. Switching modes only changes which database the
session reads; no record is ever copied between the two databases, and a demo record
can never become an operational record.

## 23. Export CSV files before important demonstrations

Open **Exports** and download the CSV files you care about before any meeting. The free
database tier has no backups, so an export is the only copy of the operational data.
Store the downloads somewhere you control.

## 24. Redeploy after GitHub updates

Streamlit Community Cloud redeploys automatically when the tracked branch is pushed. To
force it, use **Manage app → Reboot**. If dependencies changed, confirm the build log
shows them installing. Database contents survive redeployment because they live in
PostgreSQL, not in the container.

## 25. Review Streamlit logs without exposing secrets

Open **Manage app** in the bottom-right of the running app to see logs. The application
logs exception details but never logs a database URL, and the About page shows only the
driver name. If you paste a log excerpt anywhere, still read it first and remove
anything that looks like a host or credential.

## 26. Troubleshooting: dependency failures

- Confirm Python 3.12 is selected in the app's advanced settings.
- Confirm `requirements.txt` is at the repository root and was pushed.
- Read the build log for the first failing package; a later error is usually a
  consequence of it.
- Reboot the app to retry a transient network failure during installation.

## 27. Troubleshooting: database connection failures

- Run `python scripts/check_deployment.py` locally with the same URLs.
- Confirm the scheme is `postgresql+psycopg://`, not `postgres://` or `postgresql://`.
- Confirm the SSL query parameter from the provider is still on the URL.
- Confirm the two URLs name two different databases; identical targets are rejected.
- Confirm the database is not paused. On a free tier the first request after idling can
  time out; retry once.
- Re-copy the password. A password containing `@`, `/`, or `:` must be percent-encoded.

## 28. Troubleshooting: `ModuleNotFoundError`

- The main file must be `app/main.py`, so that the repository root is the working
  directory and the `app` package is importable.
- Confirm the missing package is listed in `requirements.txt`.
- If it is a development-only tool, it belongs in the `dev` extra of `pyproject.toml`
  and should not be imported by application code.

## 29. Confirm the command is run from the repository root

`python scripts/check_deployment.py`, `pytest`, and `alembic upgrade head` all assume
the repository root as the working directory. Run `pwd` and confirm you are in the
directory containing `pyproject.toml` before reporting a failure.

## 30. Remove or shut down the pilot

1. Export any CSV files worth keeping.
2. Remove every viewer from **Settings → Sharing**.
3. Delete the app from the Streamlit Community Cloud dashboard.
4. Delete `fieldops_operational` and `fieldops_demo`, or delete the whole PostgreSQL
   project.
5. Rotate or delete the database credentials at the provider.
6. Delete the Streamlit secrets entry if the app is kept but paused.

## 31. Real customer personal information is prohibited

This restates section 1 because it is the pilot's most important limit. The hosted
pilot has no authentication of its own, no encryption workflow, no backups, and no
retention or deletion controls. Enter synthetic or anonymized records only. If Summit
wants to run real customer data, that requires authentication, roles, a privacy and
security review, backups, and tested recovery — none of which are in scope here.
