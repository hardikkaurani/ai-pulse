# Explain AI Pulse from one real journey

Read this with the source open. After each section, close the notes and explain it aloud. You are ready when you can point to the code, predict its behaviour and describe its limits without memorising these sentences.

## The product in 30 seconds

AI Pulse asks employees about their AI habits. Each employee gets a private report and a practical plan. A company admin sees protected department results. One person can belong to two companies and have a different role in each.

The main improvement is trust: the API checks ownership, requires a complete assessment, refuses fabricated AI scores and supports deletion. The added product feature is a private one-week plan that helps employees act on their results.

## The five components

| Component | Its job | Where to look |
| --- | --- | --- |
| React interface | Collect answers and display API results | frontend/src/App.jsx and pages/ |
| FastAPI routes | Validate requests and enforce access | backend/app/routes/ and auth.py |
| Assessment services | Manage completion, scoring and plans | backend/app/services/ |
| SQL database | Keep accounts, memberships, answers and progress across restarts; SQLite locally, PostgreSQL on Render | backend/app/models.py and db.py |
| Optional Gemini provider | Score the written answer against the stated rubric | backend/app/services/llm.py and scoring.py |

~~~mermaid
sequenceDiagram
    participant E as Employee's browser
    participant A as FastAPI
    participant D as SQL database
    participant M as AI provider
    E->>A: Sign in and choose company
    A->>D: Verify identity and membership
    A-->>E: Company-scoped token
    E->>A: Submit every assigned answer
    A->>A: Check ownership and exact question set
    A->>D: Save answers and a pending assessment
    A->>D: Claim this scoring attempt
    A->>M: Question and written answer only
    M-->>A: Proposed score, reason and risks
    A->>A: Strictly validate the result
    alt Valid result and assessment still exists
        A->>D: Save scores, complete assessment and create plan
    else Provider failure or invalid result
        A->>D: Keep pending with no invented score
    end
    E->>A: Read personal report
    A->>D: Read this membership's assessment
    A-->>E: Private report and plan
~~~

The database transaction is released before the provider request. A slow network call therefore does not hold the database write lock. In demo mode the provider call is replaced with a labelled fixed fixture.

For the public demo, Docker builds React once and FastAPI serves both the pages and API from one HTTPS address. Render runs that container and a separate PostgreSQL database. The Google key stays in the server's private environment; it is never shipped in React. Restarting the website replaces the running process but leaves the database intact. This was checked on the public site with a saved live report and completed activity. Local VS Code development keeps SQLite and separate Vite/API ports for a simpler setup.

**Check yourself:** Why would putting SQLite on an ephemeral hosting filesystem lose data? Where does the public Google key live, and why must it never be a frontend variable?

## 1. Sign-in does not decide every permission

Start at `routes/auth_routes.py`, then `auth.py`. A successful password check establishes identity. Choosing an organization verifies membership and produces a token scoped to it. Protected routes check the token and current database membership again.

Ravi is an employee at Northwind and an admin at Bluepeak. Role belongs to Membership, not User. Changing a browser-supplied organization number cannot grant access. Hiding the leadership button is presentation; the API's rejection is the actual protection.

The browser stores the token in sessionStorage. It survives reload, but is scoped to that tab's session. Tokens expire after one hour. Enterprise SSO and immediate server-side token revocation are not implemented.

**Check yourself:** Which function rejects a direct dashboard request? What changes when Ravi switches companies?

## 2. The server determines which answers are valid

`services/questions.py` selects common questions plus role-specific questions. Seniority uses explicit ranks instead of alphabetical comparisons. The browser receives choices, but the server validates submitted IDs and choices independently.

Follow `routes/diagnostic.py` into `services/assessments.py`. A submission must contain every assigned question exactly once. Partial submissions, duplicates, another role's questions and invented choices are rejected before saved data is replaced.

The assessment stores its questionnaire snapshot and version. Future questionnaire edits cannot rewrite what an earlier employee answered.

**Check yourself:** Why do six answer rows not necessarily prove a six-question assessment is complete?

## 3. Saving answers and finishing a report are different events

The states are pending, scoring and completed. Answers are saved first. The server claims a scoring attempt, calls the provider and validates the response: exactly the allowed fields, an integer score from 1 to 5, a nonempty reason and approved risk labels.

Timeouts, provider errors and malformed output leave the assessment pending. The employee can retry or delete it. Pending assessments do not contribute to leadership results. A fallback score would turn an operational failure into false evidence.

Valid JSON does not prove correct interpretation. Ten development cases helped tune the rubric; eight later cases were frozen before one unchanged-prompt run. Both are small author-written sets. Domain validation remains future work.

**Check yourself:** What is stored after a timeout? Why is returning a neutral score of 3 misleading?

## 4. Work through the score yourself

The verified public live example has scores **4, 1, 4, 4, 4, 4**. Their sum is 21, so the personal average is **21 / 6 = 3.50** when displayed. Its level is Practitioner. The earlier separate local example averaged 3.33; these are different synthetic submissions, not a changed score after completing an activity.

Multiple-choice scores come from the questionnaire. Gemini scored the written answer. The low policy answer selected a policy-learning activity. The written response also explicitly stated policy uncertainty, so that risk was consistent with the questionnaire.

Department averages give each completed person equal weight. More assigned questions must not give someone more influence.

**Check yourself:** One person averages 2 over six questions; another averages 4 over eight questions. Their department average is 3. Why would averaging all fourteen rows give the wrong weighting?

## 5. The plan makes the result useful without inventing improvement

`services/actions.py` uses a small activity catalog and deterministic rules. Data handling, review and policy gaps take priority; a reviewed practice workflow is the fallback. Each saved activity has a target date and completion state. The personal API checks ownership before changing either.

The rules are inexpensive and inspectable; they need no extra AI call. The app does not collect practice notes or proof. Completing an activity records self-reported effort, and never changes the diagnostic score.

Identical answers under the same questionnaire and scorer configuration reuse the assessment and preserve progress. Different answers create a replacement assessment and plan.

**Check yourself:** Point to the rule that selected the policy activity. Why doesn't a completed checkbox raise the score?

## 6. Privacy happens before the response leaves the API

`routes/dashboard.py` gathers completed people in the authenticated company. `services/privacy.py` decides which fields can be published.

| Situation | What the admin receives |
| --- | --- |
| Four completed people | Protected row; no score, count, level or risks |
| Five completed people | Department average and completed count can appear |
| Five flagged out of six | Risk count protected; subtraction would reveal one unflagged person |
| Five flagged and five unflagged | Exact risk count can appear |

Risk categories stay present in a fixed order; zero/all counts are protected too. The Unassigned row depends on membership rather than participation. There is no company total exposing a hidden department through subtraction.

These rules reduce disclosure. They do not prove anonymity against outside knowledge or repeated observations.

**Check yourself:** Why would hiding a number only with CSS fail? Why did the Unassigned row's first-submission behaviour matter?

## 7. Deletion also has to win against a late AI response

`routes/reports.py` deletes responses, assessments and derived activities in one transaction. The account remains. The employee can choose one company or every membership.

- A membership revision prevents a stale submission from replacing a newer one.
- A scoring lease identifies the exact attempt allowed to finish. The final update must match the assessment, scoring state and claim time. If deletion removed it, the update matches nothing and cannot recreate it.

Fresh dashboard reads exclude deleted data after the transaction commits. Open dashboards normally refresh every two seconds. Previously captured screenshots cannot be recalled.

**Check yourself:** Walk through save → start AI call → employee deletes → AI responds. Which condition stops the final write?

## 8. An outage differs from an expired session

`frontend/src/api.js` retains HTTP status on errors. At startup, `App.jsx` clears sign-in for a rejected session, but keeps it and offers Retry for a network failure or server outage. No private page appears before the session and membership load successfully.

The recovery tests first reproduced the old behaviour, which discarded a valid token during a temporary outage. They now exercise failure, retry and successful workspace loading, plus rejection of an expired session.

## Match each claim to evidence

| Claim | Evidence to open |
| --- | --- |
| Company and role boundaries | backend/tests/test_pilot_contract.py and test_api.py |
| Completion, deletion, privacy and private progress | backend/tests/test_reliability.py |
| Provider failures and competing requests | backend/tests/test_provider_and_races.py |
| Existing answers survive schema upgrades | backend/tests/test_migrations.py |
| Rehearsal preserves the configured live database | backend/tests/test_rehearsal.py |
| Hosted startup, persistent storage and private-file protection | backend/tests/test_hosted.py and test_postgres.py; public restart evidence in docs/VERIFICATION.md |
| Interface and recovery flows | frontend/src/test/flows.test.jsx and session.test.jsx |
| Actual model behaviour and limits | docs/evaluations/ and docs/VERIFICATION.md |
| Original feature and deliberate tradeoffs | README.md and docs/ARCHITECTURE.md |

## What still requires you

Explain this without reading. Perform the exercises in INTERVIEW.md. Record the actual app using DEMO.md, confirm the recording is accessible and submit it with your repository. Neither passing tests nor this guide proves that you can make and debug a change without AI; rehearsal establishes that.
