# AI Pulse — Operational Runbook

**Audience**: Site Reliability Engineers (SRE), DevOps, Backend Engineers  
**Target Environments**: Development, Staging, Render Production  
**Classification**: Internal Operations Manual  

---

## 1. Secrets Management & Key Rotation

### 1.1 Application Secret Key (`SECRET_KEY`)
- **Usage**: Signs and verifies HMAC-SHA256 session and organization tokens.
- **Requirements**: Minimum 32 characters; must not use default development strings (`ai-pulse-dev`, `pulse-7f`).
- **Rotation Procedure**:
  1. Generate a cryptographically secure 48-byte token:
     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```
  2. Update `SECRET_KEY` in deployment environment variables (e.g. Render Dashboard or `.env`).
  3. Restart application instances.
  4. *Impact*: Active sessions will be invalidated. Users will receive `401 Unauthorized` and will be required to re-authenticate via `/auth/login`.

### 1.2 LLM Provider API Keys (`LLM_API_KEY`)
- **Usage**: Authenticates requests to the remote LLM chat-completions endpoint (e.g., Gemini on Google Cloud).
- **Rotation Procedure**:
  1. Generate new API key in Google AI Studio / GCP IAM Console.
  2. Update `LLM_API_KEY` in environment variables.
  3. Trigger zero-downtime service restart.
  4. Verify scoring with `python scripts/evaluate.py --split holdout --live`.
  5. Decommission the prior key in GCP IAM.

---

## 2. Backup & Disaster Recovery Procedures

### 2.1 SQLite Production Backups
The backup utility leverages SQLite's online backup API (`sqlite3.Connection.backup`) to capture a point-in-time snapshot without blocking active read or write transactions.

- **Trigger Backup**:
  ```bash
  python scripts/backup.py --output-dir /var/data/backups
  ```
- **Output**:
  - `aipulse_backup_<TIMESTAMP>.db`: Binary database snapshot.
  - `aipulse_backup_<TIMESTAMP>.json`: Manifest containing SHA-256 hash and table-by-table row counts.

### 2.2 Restore Drill Procedure
The restore utility guarantees tamper resistance by verifying the cryptographic checksum and schema constraints before replacing the live database.

- **Trigger Restore**:
  ```bash
  python scripts/restore.py /var/data/backups/aipulse_backup_<TIMESTAMP>.db --target /data/aipulse.db
  ```
- **Automated Verification Performed During Restore**:
  1. Verifies SHA-256 matches manifest.
  2. Copies to `.tmp_restore` and executes atomic rename.
  3. Executes `PRAGMA foreign_key_check` to ensure zero orphaned records.
  4. Verifies exact row counts across all 7 core tables match the manifest.

### 2.3 PostgreSQL Disaster Recovery
For PostgreSQL hosted instances:
- **Backup**:
  ```bash
  pg_dump -Fc "$DATABASE_URL" > "aipulse_pg_backup_$(date +%Y%m%d_%H%M%S).dump"
  ```
- **Restore**:
  ```bash
  pg_restore --clean --if-exists -d "$DATABASE_URL" <backup_file.dump>
  ```

---

## 3. Schema Migrations & Rollback Protocol

- **Apply Pending Migrations**:
  ```bash
  alembic upgrade head
  ```
- **Rollback Protocol**:
  - `001_pilot` intentionally raises `RuntimeError` on automatic downgrade to prevent destructive data loss of completed employee assessments.
  - **Standard Rollback Procedure**:
    1. Stop the application service.
    2. Restore the pre-migration database snapshot using `python scripts/restore.py`.
    3. Deploy previous container image / Git commit.
    4. Start application service and verify `/ready` health check.

---

## 4. Third-Party Provider Outage & Degradation

### 4.1 Symptoms
- Diagnostic submission `/diagnostic/submit` returns `status: "pending"` instead of `"completed"`.
- `/health` and `/ready` remain healthy (DB is up), but scoring queue remains pending.
- Provider logs indicate HTTP 429 (Rate Limit / Quota) or HTTP 503 (High Demand).

### 4.2 Automated Fail-Closed Behavior
- Provider failures **never** inject fabricated or default scores.
- Unscored assessments remain in `status: "pending"` with `error: "provider_unavailable"`.
- Employees can retry scoring via `POST /diagnostic/retry` once the provider recovers.

### 4.3 Mitigation Steps
1. Verify provider quota status in cloud console.
2. If the provider model is experiencing sustained downtime, switch `LLM_MODEL` in configuration (e.g. from `gemini-3.8-flash` to `gemini-3.5-flash-lite`).
3. Note: The application rejects silent provenance shifts. Changing model configuration requires employees to resubmit under the new model provenance.

---

## 5. Incident Response & Threat Containment

### 5.1 Compromised Account or Token
- If an employee token is suspected compromised:
  - User can delete their data or admin can delete membership:
    ```sql
    DELETE FROM memberships WHERE user_id = <USER_ID>;
    ```
  - The API verifies membership existence on every request; the compromised token is instantly rejected with `403 Forbidden`.

### 5.2 Denial of Service / Credential Stuffing
- Bounded Body middleware (`BodyLimit`) drops requests exceeding 64KB with HTTP 413.
- Rate limiter throttles IP and client accounts exceeding 10 requests per minute with HTTP 429 and `Retry-After: 60`.
- Behind reverse proxies (e.g. Render/Cloudflare), trusted proxy forwarding extracts true client IPs rather than rate-limiting the load balancer.

