# FieldOps Intelligence

## Product purpose

Operations intelligence for small field-service businesses. One connected operating
path — lead capture, qualification, conversion to customer and job, scheduling, worker
assignment, completion — plus analytics and deterministic operational insights over it.

It is a student portfolio project and a lightweight business demonstration, currently
running as a private hosted pilot for Summit Outdoor Services. It is not an enterprise
application.

## Architecture

A modular Python monolith. Keep the layering; do not introduce a separate frontend or
a separate API.

```
app/main.py            startup, workspace selection, navigation, first-run setup
app/config.py          Pydantic settings from FIELDOPS_* environment variables
app/database/          engine, sessions, models, repositories, deterministic seed
app/schemas/           Pydantic validation at form and service boundaries
app/services/          transactional business workflows
app/analytics/         pure metric and schedule-overlap functions
app/ui/                Streamlit pages, components, formatting, theme
migrations/            Alembic baseline schema
scripts/               seed, reset, quality, deployment-readiness helpers
tests/                 unit and integration tests
```

`app/database/engine.py` holds engine construction and deliberately has no module-level
engines, so tooling can build connections without importing the application's global
operational and demo engines. `app/database/session.py` owns those globals and the
workspace routing.

## Invariants

**Operational and demo data are physically separate.** Two databases, always. The
configuration refuses to start when both URLs resolve to the same target. Switching
workspaces only changes which database a session reads — no record is ever copied
between them, and a demo record can never become an operational record.

**Never seed operational data.** Seeding writes only to the demo database, only when
explicitly requested. A real workspace is created blank: the business profile with
`demo_data=false` and nothing else. `FIELDOPS_AUTO_SEED` stays `false`.

**Never expose connection details.** Do not log, print, or render a database URL,
username, password, hostname, or query parameter. Display the driver name only
(`app/utils/database_url.py` provides safe helpers). `app/config.py` raises
`ConfigurationError` rather than `ValueError` specifically so Pydantic cannot echo the
offending URL into a `ValidationError` message.

**Real customer personal information is prohibited in the pilot.** Synthetic or
anonymized records only. The pilot has no authentication, encryption workflow, backups,
or retention controls.

## Out of scope

Custom authentication, user accounts, password storage, roles, and permissions. Hosted
access is controlled by Streamlit Community Cloud viewer invitations. Also out of
scope: payments, invoices, AI features, messaging, calendar integration, mobile apps,
multi-tenancy, and enterprise infrastructure.

## Working style

Preserve the existing visual design and the lead-to-job workflow. Make targeted
changes; avoid broad rewrites and refactors that are not required by the task.

## Persistence

SQLite is the local development and test default — two files, `fieldops_operational.db`
and `fieldops_demo.db`. PostgreSQL is used only for hosted persistence, via
`postgresql+psycopg://` URLs supplied through Streamlit secrets. Provider query
parameters such as `sslmode=require` are passed through untouched. Keep both backends
working; do not add provider-specific SQL.

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

streamlit run app/main.py           # run the app
alembic upgrade head                # apply migrations
python scripts/seed_demo_data.py    # seed the demo database only
python scripts/reset_database.py    # clear and reseed the demo database only
python scripts/check_deployment.py  # verify both databases without seeding

ruff format --check .
ruff check .
mypy --no-incremental app scripts
pytest
```

Run everything from the repository root. `pyproject.toml` is the authoritative package
definition; `requirements.txt` holds pinned production dependencies for Streamlit
Community Cloud and must not contain development tools.
