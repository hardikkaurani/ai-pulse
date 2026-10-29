# Architecture and decisions

## One request through the system

~~~mermaid
flowchart LR
  UI[React workspace] --> Auth[JWT plus current database membership]
  Auth --> Validate[Validate assigned questions]
  Validate --> Save[Save complete answer snapshot]
  Save --> Score[Claim scoring lease]
  Score --> Model[Optional model request]
  Model --> Parse[Strict result validation]
  Parse --> Complete[Complete assessment and create plan]
  Parse --> Pending[Pending with retry]
  Complete --> Personal[Owner only report and plan]
  Complete --> Group[Per person average]
  Group --> Privacy[Protect small groups and risk complements]
  Privacy --> Admin[Organization admin dashboard]
~~~

FastAPI routes handle transport and authorization. Small service modules own question selection, assessment lifecycle, model validation, activity selection and publication privacy. React pages call the API; the browser never decides whether a person may access data.

## Local and hosted execution

Local development uses Vite on port 5173, FastAPI on 8000 and a private SQLite file. The root Dockerfile builds the frontend and serves its static files through FastAPI after the API routes. Hosted browser requests use the same HTTPS origin. The image runs as an unprivileged user and never includes the local environment file or database.

On Render, `render.yaml` connects the single web worker to a separate PostgreSQL database over the internal network. SQLAlchemy uses psycopg for PostgreSQL; the models and Alembic schema support both databases. Startup requires explicit storage and a stable signing secret, applies migrations and seeds fictional accounts only when the database has no users. A restart therefore cannot reset existing answers. The database connection checks stale pooled connections before reuse. The Google key stays in Render's private runtime environment.

The free hosting choice is for the assessment demo: the website sleeps when idle, and the database expires after 30 days without an upgrade. Separate storage establishes persistence across web-service restarts, not a backup or recovery guarantee. Horizontal scaling and production operations remain out of scope.

## Ownership

A user has memberships in organizations. A membership carries role, department, job role and seniority. An assessment belongs to exactly one membership. Answers and activities belong to that assessment.

The JWT contains a subject and optional organization scope. Signature, issuer, audience and expiry are validated. The database is consulted again on every request. An organization parameter cannot override the token. Activity updates join back to the owning assessment instead of trusting a browser-provided user ID.

Ravi makes this visible: the same account is an employee at Northwind and an admin at Bluepeak. Switching the organization swaps the scoped token and clears the rendered workspace.

## Completion and concurrency

The server, not the UI, determines the assigned questions. It rejects an incomplete set, duplicates, foreign question IDs, invalid choices and empty written evidence before mutating stored answers.

A membership revision provides an optimistic concurrency check. The update succeeds only if the revision still matches the one read for the request. A stale request returns 409 instead of replacing a newer assessment.

A fingerprint covers normalized answers, the questionnaire version, rubric version, mode and model. An identical submission reuses the current assessment. A changed submission deletes the previous assessment and its derived plan, then saves the new snapshot atomically.

Scoring claims the saved assessment and records the claim time. The database transaction is released before network I/O. Only the same assessment and scoring lease may publish the result. If the employee deleted or replaced it, a late response cannot insert it again. An abandoned lease can be retried after 60 seconds. An old worker also cannot overwrite a newer lease.

A provider failure leaves the assessment pending and excluded from aggregates. Answers are retained for explicit retry. Valid scores and the plan are committed together. The request performs scoring synchronously; there is no hidden background worker.

## Publication privacy

The publication function receives people, each with an average and risk-label set. It does not receive names or answer text. Below five completed people, protected fields are null or empty.

Each participant has equal weight. This matters because an engineering lead answers more questions than a junior support employee. Averaging all answer rows would give some people more influence.

Risk categories are fixed, and each flagged person counts once per category. An exact risk count requires at least five flagged and five unflagged people. Otherwise the count is null, including zero and all-person counts. For example, publishing five flagged people out of six would reveal a one-person complement, so the count stays protected. No company total is exposed. These rules block simple subtraction attacks, but not every inference using outside information or snapshots over time.

The Unassigned row is included whenever organization memberships lack a valid department, independently of completed assessments. Its presence cannot reveal a first submission or last deletion. Named department rows likewise come from the department roster, not participation.

## Deletion

Deletion increments the affected membership revisions, removes responses, deletes assessments, and cascades to activities inside one transaction. Current or all memberships are resolved from the authenticated user. No report cache or raw-answer audit log needs a separate purge.

The account remains. Deleted rows may remain recoverable in database storage pages, external backups or provider systems; the pilot does not claim forensic erasure. A production retention policy must cover those systems. Fresh database-backed dashboard reads no longer include the rows; browser views refresh every two seconds when visible and on focus.

## Why the plan uses rules

The added feature addresses the gap between “here is your result” and “what do I do this week?” A short catalog makes recommendations inspectable, repeatable and safe to explain. Data handling, review and policy gaps take priority. A practice workflow is the fallback.

The application stores only activity identity, due date and completion. It does not collect the employee’s practice notes or proof. Progress is self-reported, private and excluded from scoring.

## Where to make common changes

| Change | Start here | Check afterwards |
| --- | --- | --- |
| Change a role or seniority question | backend/data/questions.json; services/questions.py | Assigned-question tests and complete submissions |
| Change privacy threshold | app/config.py; services/privacy.py | 0/1/4/5/6 tests and UI wording |
| Add a risk label | services/llm.py, scoring.py, privacy.py | Parser, risk publication and live smoke cases |
| Add an activity | services/actions.py | Plan ownership, selection, deletion and completion tests |
| Change login or roles | app/auth.py; routes/auth_routes.py | Ravi and cross-tenant denial tests |
| Change schema | A new Alembic revision | Fresh and legacy migration tests |
| Change visual appearance | frontend/src/styles.css | Desktop and mobile browser checks |

Avoid changing an already-applied migration. Add the next revision. The current migration preserves legacy answers but excludes them from completed results because their completeness is unknown.
