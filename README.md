# AI Pulse

A role-aware AI habits assessment with private employee reports and protected team insights. Built on the inherited application, with fixes for access, scoring and privacy, plus a private one-week improvement plan.

[Live Frontend (Vercel)](https://ai-pulse-rho-one.vercel.app/) · [Live Backend (Render)](https://aipulse-backend-msyi.onrender.com/) · [GitHub Repository](https://github.com/hardikkaurani/ai-pulse)

**Stack:** React · FastAPI · SQLAlchemy · SQLite locally / PostgreSQL on Render · Google Gemini

## Try it

All demo passwords are **`pulse123`**.

| Account | What to explore |
| --- | --- |
| `asha@northwind.test` | Northwind admin dashboard and protected departments |
| `priya@northwind.test` | Employee report, improvement plan and deletion |
| `new@northwind.test` | Take or retake a Support assessment |
| `dev@northwind.test` | Engineering lead's role-specific questions |
| `ravi@consult.test` | Employee at Northwind, admin at Bluepeak |
| `meera@bluepeak.test` | Bluepeak admin dashboard |

The public site uses live Google scoring; preloaded reports remain labelled samples. Accounts are shared, so use fictional answers only. Free hosting may take about a minute to wake.

## Run locally

Requires **Python 3.12+**, **Node.js 24**, npm and Git. From the repository root:

```sh
python scripts/setup.py --demo
python scripts/run.py
```

Open **http://127.0.0.1:5173**. API docs: **http://127.0.0.1:8000/docs**.

Setup installs dependencies, generates a private signing key and preserves existing data. Local setup defaults to labelled demo scoring without an API key. [Live AI configuration](docs/AI_SCORING.md) · [Hosting and VS Code](docs/DEPLOYMENT.md).

## Issues found and fixes

| Issue | Fix |
| --- | --- |
| Company access could cross boundaries | Check current membership and role on every protected request. |
| Partial or duplicate answers could produce reports | Validate the exact assigned questions; count only completed assessments, once per person. |
| Small departments exposed results | Hide scores, counts and risks below five completed people; protect small risk groups and their complements. |
| Employees could not delete their diagnostic | Delete answers, report and plan together; exclude them from dashboards and reject late AI results. |
| Model failures could produce unreliable results | Validate structured output; save answers as pending and offer retry when scoring fails. |
| Weak credentials and unsafe setup | Salted password hashes, generated secrets, request limits and migrations that preserve data. |

For the **client request**, I chose suppression rather than merging unrelated departments. No company total exposes hidden groups by subtraction. Deletion affects only the signed-in person, including admins. It takes effect in database-backed results immediately; open dashboards normally refresh within two seconds.

Before rollout, I would confirm whether deletion includes accounts, whether department names may stay visible, and the required provider/backup retention policy. [Design details](docs/ARCHITECTURE.md).

## Added feature: a private one-week plan

A score alone leaves employees asking what to do next. The plan selects up to three practical activities with a reason, steps, target date and completion control. Rules keep recommendations explainable without another AI call. Progress stays private and never increases the assessment score.

## Verification and limits

```sh
python scripts/check.py
```

**82 backend tests, 10 interface tests and the production build passed.** CI also covers PostgreSQL and container startup. Browser checks covered live scoring, saved progress, company switching and deletion. [Evidence and scope](docs/VERIFICATION.md).

This is a single-worker pilot. SSO, managed backups, load testing and independent model validation remain deferred. Scores describe self-reported habits, not verified job performance. The free hosted database expires after 30 days unless upgraded. [Rollout notes](docs/ROLLOUT.md).

## AI assistance

Codex helped with analysis, implementation, tests and documentation. One generated validation rule rejected valid browser dates; a failing test exposed it, and date parsing was corrected while completion remained a strict boolean.
