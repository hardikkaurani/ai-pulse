# AI Pulse

AI Pulse helps an enterprise understand how well its employees use AI at work, department by department, with mathematical privacy protections and employee data sovereignty.

---

## Key Features

1. **Role & Seniority-Adaptive Diagnostics**:
   - Employees sign in, select their active organization, and complete a targeted diagnostic.
   - Questions adapt dynamically to their specific department role (Engineering, Sales, Support, HR, Management) and seniority level (Junior, Mid, Senior, Lead).
2. **AI-Powered Evaluation**:
   - Open-ended responses are analyzed for maturity level, security risks (e.g., prompt injection, confidential customer data exposure, unreviewed output), and targeted next steps.
   - Operates in deterministic mock mode (`AI_MODE=mock`) or connects to any OpenAI-compatible completions endpoint (`AI_MODE=live`).
3. **Small-Group Privacy Engine (k-Anonymity $\ge$ 5)**:
   - To protect individual employee anonymity, departments with fewer than 5 completed diagnostics are suppressed from individual display.
   - Small departments are safely aggregated into an `"Other teams"` cohort only when the combined participant count reaches 5 or more.
   - Suppressed departments never leak individual scores, headcounts, or risk flags into organization-wide analytics.
4. **Employee Right-to-Delete**:
   - Any employee can permanently delete all their diagnostic answers and evaluation data directly from their report.
   - Deletions are atomic and strictly scoped to the active organization membership.
   - Company dashboards and reports recalculate immediately.
5. **Multi-Organization Membership & BOLA Protection**:
   - Users belonging to multiple organizations select their active workspace upon login.
   - All diagnostic, report, and dashboard queries strictly enforce server-side organization membership checks (preventing Broken Object Level Authorization / IDOR).

---

## Technology Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy, SQLite (configurable to PostgreSQL via `DATABASE_URL`), PyJWT.
- **Frontend**: React 18, Vite, Native CSS Variables (zero third-party UI framework overhead).
- **Containerization**: Multi-stage Docker build, Nginx Alpine, Docker Compose with healthchecks.
- **Testing**: Pytest with automated session-scoped temporary SQLite database isolation.

---

## Running Locally

### Option A: Docker Compose (Recommended)

Run the full stack (backend API on `http://localhost:8000` + frontend on `http://localhost:3000`):

```bash
docker compose up -d --build
```

Seed demo accounts into the containerized database:

```bash
docker compose exec backend python -m app.seed
```

Open `http://localhost:3000` in your browser.

To stop:

```bash
docker compose down
```

---

### Option B: Bare-Metal / Local Environment

#### 1. Backend Setup

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Seed demo data (passwords for all seeded users: pulse123)
python -m app.seed

# Run FastAPI backend server (http://localhost:8000)
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
# App will run at http://localhost:5173
```

---

## Running Tests

All 45 backend regression tests run in complete isolation against a temporary database:

```bash
python -m pytest backend/tests -v
```

### Test Suite Coverage:
- `backend/tests/test_api.py`: Authentication, RBAC, multi-org access, BOLA prevention, and DB isolation.
- `backend/tests/test_dashboard_privacy.py`: 10 comprehensive tests validating small-group privacy threshold ($N_c \ge 5$), 2-step population aggregation, "Other teams" grouping, and risk flag isolation.
- `backend/tests/test_deletion.py`: 8 tests verifying employee right-to-delete, atomic database transactions, rollback on failure, IDOR immunity, and multi-org isolation.
- `backend/tests/test_questions.py`: Seniority ranking and department-specific question assignment.
- `backend/tests/test_scoring.py`: LLM markdown fence stripping, score clamping (1.0–5.0), word-to-number parsing, and fallback handling.

To build and verify the frontend bundle:

```bash
npm run build --prefix frontend
```

---

## Demo Accounts

All seeded demo accounts use password: `pulse123`

| Email | Organization(s) | Role & Department |
|---|---|---|
| `asha@northwind.test` | Northwind Logistics | Administrator |
| `meera@bluepeak.test` | Bluepeak Retail | Administrator |
| `ravi@consult.test` | Both | Employee at Northwind, Admin at Bluepeak |
| `priya@northwind.test` | Northwind Logistics | Employee (Support, Junior) |
| `arjun@northwind.test` | Northwind Logistics | Employee (Support, Senior) |
| `dev@northwind.test` | Northwind Logistics | Employee (Engineering, Lead) |
| `sara@northwind.test` | Northwind Logistics | Employee (Engineering, Mid) |

---

## Configuration & Environment Variables

Copy `.env.example` to configure custom environments:

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `ai-pulse-dev-secret` | Cryptographic key for signing JWT session tokens. |
| `DATABASE_URL` | `sqlite:///./aipulse.db` | Database connection string (SQLite, PostgreSQL). |
| `TOKEN_HOURS` | `12` | JWT token lifespan in hours. |
| `AI_MODE` | `mock` | `mock` (uses deterministic canned responses) or `live` (calls LLM endpoint). |
| `LLM_API_URL` | `""` | Chat completions endpoint URL (OpenAI, Azure, Gemini). |
| `LLM_API_KEY` | `""` | Bearer token for LLM provider API. |
| `LLM_MODEL` | `""` | LLM model name (e.g., `gpt-4o-mini`). |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed frontend origins. |
| `VITE_API_URL` | `http://localhost:8000` | Frontend configuration for backend API address. |

---

## Known Considerations & Security Notes

1. **Password Hashing**: Demo seed uses SHA-256 for lightweight local setup. In a multi-tenant production environment, migration to Argon2id or bcrypt with per-user salt should be implemented.
2. **AI Provider Fallback**: If `AI_MODE=live` is configured but the provider times out or returns malformed text, the scoring engine gracefully falls back to deterministic heuristic evaluation so user workflows are never blocked.
