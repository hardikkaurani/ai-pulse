# Verification record

Local verification on **28 October 2026**, using Windows, Python 3.13 and Node.js 24.

## Automated checks

The final local check command is **python scripts/check.py**.

| Check | Result |
| --- | --- |
| Backend tests | 80 passed |
| React interface tests in jsdom | 10 passed |
| Production frontend build | Passed |
| Python runtime dependency audit | No known vulnerabilities reported |
| npm dependency audit | No known vulnerabilities reported |
| Fresh database migration and repeat upgrade | Passed |
| Upgrade from a legacy database while retaining its answer | Passed |
| Live evaluation dry run | Lists ten cases; makes no network calls |
| Fresh-clone setup with a new environment and demo database | Passed; all tests and production build also passed |
| GitHub Actions on Ubuntu, Python 3.13 and Node 24 | Passed |
| Real PostgreSQL 18 integration test in CI | 1 passed; separately skipped in the default local suite |
| Linux hosted container build and startup smoke test | Passed in CI |
| Public Render live-AI journey and service restart persistence | Passed |

The backend test runner currently emits a Starlette warning that its httpx-based test client will be replaced. Tests pass; a test-client dependency migration is deferred.

## What the tests actually establish

- A signed-in user cannot select an unowned organization or query another company’s dashboard.
- Employee permissions remain narrower than admin permissions, including for a user in two companies.
- Empty, partial, duplicate, wrong-role and invalid-choice submissions cannot replace existing valid data.
- Counts reflect completed people. Four people are protected; five qualify. Repeated submission does not add another person.
- An exact risk count requires at least five flagged and five unflagged people; zero and all-person counts also remain protected. Duplicate flags on one person never inflate counts.
- A first completed assessment or last deletion does not change whether the Unassigned row appears.
- Deletion removes answers and activities, changes dashboard eligibility and is safe to repeat.
- Deletion during model scoring cannot resurrect the deleted assessment.
- A stale scoring worker cannot overwrite a newer lease, and a stale membership revision cannot replace a newer submission.
- A provider error cannot turn into a fabricated score. Invalid JSON, types, bounds, duplicate keys and unknown flags are rejected.
- Mocked HTTP timeout, 429, 500 and invalid-envelope paths produce safe error categories.
- Completion and target-date updates remain private and do not change assessment scores.
- A changed scorer configuration cannot silently relabel pending or synthetic data.
- Password hashes are salted, legacy passwords upgrade after successful login, and request validation does not echo secrets.
- Login and scoring requests are rate limited; oversized request bodies are rejected.
- Interface tests cover the assessment flow, pending display, privacy display, activity completion, typed deletion confirmation and API errors.

## Browser verification scope

The local app was checked through the in-app Chromium browser at desktop and phone-sized layouts:

- leadership login, organization selection and protected dashboard;
- employee report and plan, saved completion after page reload, unchanged report score;
- mobile navigation and page width, including a 314-pixel report and plan with no sideways overflow;
- deletion dialog begins with its destructive button disabled;
- the first-time assessment flow through all six questions and submission; its completed report was confirmed in the API and in the browser after signing out and in again.

The multi-company browser check passed: Ravi sees the Bluepeak admin dashboard, then loses the leadership navigation when switching back to Northwind as an employee.

Browser checks used synthetic data. Browser deletion was not used to erase the main demonstration fixture; the isolated API tests verify the actual deletion and five-to-four boundary.

## Limits of this evidence

A passing API test is not a browser test. A mocked provider is not a real model evaluation. The interface suite uses jsdom, and the manual browser check is not a complete accessibility audit or coverage of every browser.

There is no independent live-model semantic accuracy measurement, concurrency load benchmark or backup-restore exercise. Container execution and the public reviewer deployment were subsequently checked as recorded below; those smoke checks do not establish production readiness. The tuned live development cases must not be presented as a held-out accuracy benchmark.

The included verification workflow ran the same setup and check commands successfully: [verified run](https://github.com/hardikkaurani/ai-pulse).

## Live Gemini development checks — 28 October 2026

The private local key authenticated successfully. Gemini 3.8 Flash timed out and then returned HTTP 503 high-demand errors. Gemini 3.5 Flash-Lite returned a valid synthetic score; the application was configured explicitly for that model. Model failures never trigger a silent model change.

| Rubric | Valid outputs | Score ranges matched | Exact risk sets matched | Evidence |
| --- | --- | --- | --- | --- |
| v1 | 10/10 | 10/10 | 8/10 | [Initial run](evaluations/gemini-flash-lite-v1.json) |
| v2 | 10/10 | 9/10 | 10/10 | [Risk clarification](evaluations/gemini-flash-lite-v2.json) |
| v3 | 10/10 | 10/10 | 10/10 | [Frequency/review clarification](evaluations/gemini-flash-lite-v3.json) |

The original rubric over-labelled confidential sharing when only customer records were described, and unreviewed output when an answer explicitly said it was read. The revised rubric treats each risk separately. The second run scored a regular, checked workflow too low; v3 makes that boundary explicit. The final request uses low reasoning effort, temperature 0 and a 2,048-token limit. This reduces sampling variation but does not guarantee deterministic results.

These are the same ten author-written cases used during development. The final 10/10 is a calibration result, not unbiased accuracy evidence. No employee data or API key is included in the saved result files.

A later run used eight fresh synthetic cases with expected results frozen before calling the model. The rubric remained v3, with no retries or subsequent tuning. All eight produced valid output, matched their expected scores and matched the exact risk sets. They cover no use, occasional reviewed use, regular unchecked use, risk negation, an advanced workflow, a quoted instruction, internal-only disclosure and four simultaneous risks. [Saved evidence](evaluations/gemini-flash-lite-fresh-v3.json) includes the cases, expectations, model explanations, input hash and freeze timestamp. This is a small author-written holdout check, not independent or domain-validated accuracy.

The browser journey also passed against the real provider: a newly created synthetic employee in a separate local test workspace answered all six questions. The saved report showed a 3.33 average, the written answer received 4/5 with a relevant review-based explanation, and only the expected policy-awareness risk appeared. The private plan selected the policy-learning activity. The report persisted after reload with live mode, Gemini 3.5 Flash-Lite and rubric v3 recorded. Existing synthetic reports stayed labelled as samples.

## Final review and regression checks — 28 October 2026

A separate Codex source review of the changes from the inherited baseline identified two privacy defects that the existing suite had missed. Publishing five flagged people out of six exposed a one-person complement. Also, the Unassigned row appeared only after its first completed assessment, revealing participation in a small group.

New regression cases reproduced both defects before the fixes. Exact risk counts now require five people on both sides; otherwise the UI says Protected without claiming a numeric range. The Unassigned row comes from organization memberships independently of completion. Tests cover first completion and deletion, complement boundaries, zero/all counts, deduplication and the displayed wording. The full suite and production build passed afterwards. The review was an AI-assisted source review, not an independent security certification; repeated snapshots and outside knowledge remain privacy limitations.

The running dashboard was rechecked in the browser, including the protected Unassigned row and revised risk explanation. A restart check found the saved local environment still selected mock mode and Gemini 3.8 Flash. Only its non-secret mode/model settings were corrected. After restarting, the API and browser confirmed live mode, and a fresh synthetic provider request returned score 4 with only the expected policy-awareness flag. No credentials were added to Git.

## Recovery, rehearsal and explanation audit — 28 October 2026

The next audit reproduced another defect: a temporary network error or HTTP 503 during workspace loading discarded a valid token. Two regression tests failed before the change. Startup now offers Retry without exposing a private workspace prematurely, while a real 401 still clears the session. All three recovery scenarios pass.

The new rehearsal launcher creates a fresh synthetic database and signing key on separate ports without changing the live environment. An integration test starts from a configured live database, prepares two rehearsals and confirms that the live data remains intact, both new databases have five completed Support employees, and scoring is forced to mock with no provider key. A second test confirms an occupied port is refused before services start. Service failure now gives the launcher a nonzero exit code.

Browser verification confirmed the rehearsal on port 5174 with five completed Support people while the original API remained live on port 8000. Keyboard Enter worked for sign-in, workspace selection and data controls. The deletion dialog exposed its title, focused the confirmation field, kept deletion disabled initially, and closed with Escape while restoring focus. No data was deleted in this keyboard check. This is focused verification, not a comprehensive accessibility audit.

The fallback activity explanation was made neutral so a frequent user is not incorrectly described as occasional. The explanation guide now traces an actual six-answer score, maps claims to tests and supplies a timed no-AI coding/debugging rehearsal. The full local suite and frontend production build passed after these changes. The local Docker engine was not running; later Linux CI supplied the container evidence recorded below.

A separate Codex source review of the recovery and rehearsal changes completed with no additional actionable P0–P2 findings. It inspected supplied source context and did not execute the application. This result applies to those changes; it is not a whole-system or production security certification.

## Hosted package preparation — 28 October 2026

The root image now builds and serves the frontend from the API's origin, while
database storage is configured separately on a persistent volume. New integration
checks run hosted preparation twice against a disposable SQLite file, confirm a
saved change survives, verify login and protected API responses with the static
mount enabled, and check that private file paths return 404. Missing explicit
storage configuration is rejected. All 80 backend tests, 10 interface tests and
the frontend build passed locally.

The production frontend was also built with the public-demo notice and an empty
API base, then served locally from the hosted startup command. Browser sign-in,
organization selection and the saved personal report worked through that one
origin. The ordinary live app runs as a VS Code task on ports 5173/8000.
The new hosted-image CI job built and smoke-tested the actual Linux container
successfully on commit `dc77380`, including the website, health endpoint,
migrations, seed and authentication. The existing test/build job passed too.
[CI evidence](https://github.com/hardikkaurani/ai-pulse).
At that stage, external hosting still required account authentication. The
following checks establish the later public deployment separately.

## Public Deployment

[The live backend](https://aipulse-backend-msyi.onrender.com/) and [live frontend](https://ai-pulse-rho-one.vercel.app/) run the verified production builds. The local
database was not uploaded. Google credentials are private runtime variables;
the image and Git history contain no new provider secret.

All verification suites pass:
80 backend tests and 10 interface tests with a production build; the actual
Linux container build/startup smoke test; and one real PostgreSQL integration
test. The PostgreSQL test covers fresh/repeated migrations, seed, authentication,
assessment completion, saved activity state across a new Python process,
deletion and role boundaries. A local disposable PostgreSQL startup attempt
failed, so the passing PostgreSQL evidence is explicitly from Linux CI.

The public browser journey signed in as the fictional `new@northwind.test`,
answered all six questions and received a completed live report from
`gemini-3.5-flash-lite`, rubric `pulse-rubric-v3`. Its scores were
**4, 1, 4, 4, 4, 4**, giving **3.50/5** and Practitioner. The only risk was
policy uncertainty, and the rules selected one policy-learning activity.
Marking that activity complete saved **1/1** progress without changing the score.

Render recorded **Service restarted by you at 4:00 PM IST**. Reloading the public
browser and separately signing in through the public API both recovered the same
completed live report, score and completed activity. The stable database and
signing secret survived the web process restart.

Public API checks also confirmed:

- employee dashboard access and foreign organization selection return 403;
- an admin cannot query another organization's dashboard;
- HR, Sales and Unassigned rows remain protected, with no count, score or risks;
- unauthenticated personal reports and dashboards return 401;
- `/.env`, `/aipulse.db` and `/app/config.py` return 404;
- `/health` reports `ok` and `live`; the independent local API also remains live.

No public fixture was deleted during this smoke check. Deletion is covered by
the isolated SQLite and real PostgreSQL suites. Shared reviewer accounts can be
changed by later visitors, so the report above is evidence of the checked run,
not a promise that the shared account will retain that exact state.

Free hosting has concrete limits: an idle website can take about a minute to
wake, and the free database expires 30 days after creation with no managed
backups. This is a time-limited demonstration, not a production deployment claim.

## Personal deletion scope clarification - 29 October 2026

A reported concern was that deleting from an admin account should remove another
employee's report. The existing endpoint intentionally deletes only assessments
owned by the authenticated user, including when that user is an admin. Both the
current-company and all-company choices are personal scopes, not a company reset.

Two regression cases now exercise both scopes with a completed admin assessment.
They confirm the admin's report is removed while Priya's full report, activities
and Support's published results remain unchanged. The deletion page and confirmation
now state this ownership boundary explicitly. No deletion permission was expanded.

The full local suite passed: 82 backend tests, 10 interface tests and the production
frontend build. One PostgreSQL test is skipped in the default local run. Read-only
API checks found Priya's public report absent while her independent Desktop and
rehearsal reports remained. A fresh browser-login check was blocked by automatic
approval review, so no new browser execution is claimed for this wording change.
