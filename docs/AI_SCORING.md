# AI scoring and configuration

The default is clearly labelled **demo scoring**. Written answers receive a fixed sample score of 3, with an explanation saying it is a fixture. Seeded results are synthetic. Neither is presented as a real evaluation.

For live scoring, edit the private **backend/.env** locally, keeping its generated SECRET_KEY:

~~~dotenv
AI_MODE=live
LLM_API_URL=https://your-provider.example/v1/chat/completions
LLM_API_KEY=your-private-key
LLM_MODEL=your-model-identifier
~~~

Use the provider’s actual OpenAI-compatible chat-completions URL. Generic providers must support temperature and max_tokens. Google Gemini uses low reasoning effort, temperature 0 and a bounded 2,048-token budget so reasoning does not consume the small response allowance. Remote endpoints require HTTPS; local HTTP model servers are permitted. Restart the backend after configuration changes. Never put credentials in the frontend, Git, a recording or a chat message.

For the tested Google configuration, get a key from [Google AI Studio](https://aistudio.google.com/apikey), set LLM_API_URL to **https://generativelanguage.googleapis.com/v1beta/openai/chat/completions**, and set LLM_MODEL to **gemini-3.5-flash-lite**. Keep LLM_API_KEY only in your private backend environment. See [Google’s compatibility guide](https://ai.google.dev/gemini-api/docs/openai). Model availability and quota depend on the project. There is no automatic switch to another model after an error.

Only question text and the written answer are sent to the model. The request does not include the employee’s name, email or organization. Free text can still contain identifying information; the UI asks employees to remove it. The system rubric and user answer are separate messages. That separation is useful, but is not a guarantee against prompt injection or semantic misclassification.

Provider timeouts, rate limits, invalid envelopes and malformed content are handled without a fabricated score or raw provider error. Pending assessments are excluded from dashboards. Employees can retry or delete them. If the model configuration changed, a retake is required to preserve honest provenance.

Every assessment stores its questionnaire snapshot/version, rubric version, scoring mode and model. Enabling live mode does not relabel old synthetic reports.

### Evaluate a configured model

~~~sh
# No network calls; explains the available synthetic cases
python scripts/evaluate.py

# Windows
.venv\Scripts\python.exe scripts/evaluate.py --live --output work/live-evaluation.json

# macOS / Linux
.venv/bin/python scripts/evaluate.py --live --output work/live-evaluation.json
~~~

Live evaluation makes ten bounded synthetic requests; provider charges may apply. The cases cover ordinary use, disclosure, negation and prompt injection. Results show schema validity, expected score ranges and exact risk matches. A failed expectation exits nonzero.

**Live Google Gemini scoring was exercised on 28 October 2026.** Gemini 3.8 Flash returned capacity errors, so the demonstrated model is **gemini-3.5-flash-lite**. The initial run revealed two extra risk labels; a second run exposed a score-boundary ambiguity. After clarifying the rubric, version **pulse-rubric-v3** matched all ten score ranges and exact risk-label sets. These are iteratively tuned, author-written development cases, not an independent accuracy benchmark or evidence of fitness for employment decisions. All three sanitized runs are retained in [verification notes](VERIFICATION.md). The provider contract and failure paths also have HTTP-mocked tests.
