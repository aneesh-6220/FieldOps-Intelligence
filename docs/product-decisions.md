# Product decisions

## ADR-001: Lead-to-job before adjacent finance workflows

**Status:** Accepted for Phase 1

The first complete operating loop is lead → qualified opportunity → customer and job → schedule and worker → completed actuals. Estimates, invoicing, payments, and expenses are useful adjacent domains, but including them would weaken the transaction and workflow depth of the MVP.

## ADR-002: Transactional conversion with explicit confirmation

**Status:** Accepted

The operator reviews and may edit a proposed customer and job before confirming. `LeadService` creates both records, changes lead status, and writes activity entries in one session. A failed child insert rolls back the entire conversion. A unique originating-lead relationship prevents duplicates.

## ADR-003: Streamlit over a split web stack

**Status:** Accepted for the local MVP

Streamlit provides a usable Python-only interface with minimal installation surface. Schemas and services remain independent of Streamlit so a future API or client does not require rewriting domain rules.

## ADR-004: SQLite with SQLAlchemy and Alembic

**Status:** Accepted for local use

SQLite provides zero-service persistence. SQLAlchemy supplies relationships and transactions; Alembic supplies repeatable setup. PostgreSQL, authenticated tenancy, backups, and production operations are deferred rather than implied.

## ADR-005: Modular monolith

**Status:** Accepted

The domain is connected and the product runs as one process. Separate modules for UI, schemas, services, repositories, persistence, and analytics preserve responsibility boundaries without distributed transactions or premature services.

## ADR-006: Warn-and-acknowledge schedule conflicts

**Status:** Accepted

Phase 1 detects worker overlaps during scheduling and assignment. It blocks the first attempt and allows an explicit acknowledgement because real field operations sometimes intentionally overlap crews or handoffs. The app continues to show the conflict until the schedule changes.

## ADR-007: Decimal money and unknown-value exclusion

**Status:** Accepted

Money uses `Decimal` and fixed-point database fields. Missing final revenue, actual cost, or actual duration is unavailable—not zero—and is excluded from dependent averages. This avoids false precision while allowing rules to identify missing completion data.

## ADR-008: Rules before forecasting or machine learning

**Status:** Accepted for Phase 1

Operational insights use named thresholds and direct record evidence. Forecasting, statistical anomaly detection, and machine learning are deferred until the workflow produces enough trustworthy longitudinal data to evaluate them.

## Deferred roadmap

Likely next layers are estimates; invoices, payments, and expenses; authentication and roles; PostgreSQL deployment; CSV import; calendar and messaging integrations; mobile workflows; maps and routes; and validated forecasting or statistical analysis. They are roadmap candidates, not present product capabilities.
