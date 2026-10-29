# A recording under five minutes

Record the actual running app with your own explanation. Rehearse once first; the interview will test your understanding without AI. This guide is not a completed screen recording.

## Prepare

Run setup and start the app. Use only synthetic demo accounts. Keep passwords, provider keys and backend/.env out of the recording.

For the privacy boundary demonstration, use a fresh demo database: Support starts with exactly five completed people. The test suite always creates that fixture independently, even if your local demo has changed.

After normal setup has installed dependencies, start a fresh rehearsal with:

~~~sh
python scripts/rehearse.py
~~~

Open **http://127.0.0.1:5174**. The rehearsal API is on port 8001. Each launch creates a new database under ignored work/rehearsals/, with its own temporary signing key, fixed demo scoring and exactly five completed Support employees. It does not edit backend/.env, copy the Google key or replace your normal database. The normal live app can stay open on port 5173. Stop a previous rehearsal before launching another; occupied ports are refused. Existing rehearsal databases are retained, not reset.

Use the rehearsal for the deletion sequence. Use the normal app for the live AI segment and label the two modes accurately. A rehearsal is a synthetic fixture, not a live AI evaluation.

For a live-scoring segment, configure your private Google key, enable live mode and submit an assessment with the fresh new@northwind.test account. Seeded employee reports remain labelled synthetic until retaken; do not present those as live results.

Keep one browser window signed in as Asha and a separate private window as Priya. Use the same localhost address throughout. Run the tests before recording and keep their completed output ready.

## Suggested sequence

| Time | Show | Explain in your own words |
| --- | --- | --- |
| 0:00–0:30 | README and app | You inherited the code, prioritised trust, then added a useful employee feature. This is a synthetic-data pilot. |
| 0:30–1:10 | Asha’s dashboard | Engineering and Support are visible. HR and Sales have no numbers. The backend suppresses fields, and there is no company total for subtraction. |
| 1:10–1:45 | Ravi switches companies | His role changes with the selected organization. The API enforces membership and role; hiding links is not the security boundary. |
| 1:45–2:35 | Priya’s report and plan | Open an answer explanation, then show why an activity was selected, its steps, target date and completion. Completing it does not change the score. |
| 2:35–3:20 | Priya deletes current-company diagnostic; Asha’s dashboard | Type DELETE, confirm, and show Support becoming protected when five completed people become four. Account remains; report and plan disappear. |
| 3:20–4:05 | Completed test output and one focused test | Show tests for cross-company denial, deletion boundary and invalid model output. Explain pending state and safe retry. |
| 4:05–4:40 | README limits and AI assistance | Show the Gemini evidence: ten development cases and eight fresh fixed-prompt cases. Explain why neither is an independent accuracy benchmark. Describe one AI mistake caught by a test and the deployment work deliberately deferred. |

Do not spend the recording installing packages or reading every file. Show a few important behaviours with clear evidence.

## Useful focused test commands

From the backend folder:

~~~powershell
..\.venv\Scripts\python.exe -m pytest -q tests/test_pilot_contract.py
..\.venv\Scripts\python.exe -m pytest -q tests/test_reliability.py -k "five_to_four or model_failure or delete_while"
~~~

On macOS/Linux, use ../.venv/bin/python.

## Before submitting

- Open the repository link while signed out and confirm the README, source and original history are visible.
- Keep the recording below five minutes and make sure the reviewer can open it.
- Speak accurately about the model mode shown on screen.
- Practise explaining and modifying the core code without AI.
- Submit the repository and recording yourself through the assessment form. The deadline in the candidate brief is **29 October 2026, 11:59 AM IST**, with one submission per person.
