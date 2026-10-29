import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Diagnostic({ onDone, onCancel }) {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    fetchQuestions();
  }, []);

  async function fetchQuestions() {
    setLoading(true);
    setError("");
    try {
      const data = await api("/diagnostic/questions");
      setQuestions(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Failed to load diagnostic questions. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleAnswerChange(qid, value) {
    setAnswers((prev) => ({ ...prev, [qid]: value }));
    if (validationError) setValidationError("");
  }

  async function submit(e) {
    e.preventDefault();
    setValidationError("");
    setError("");

    // Validate that all questions have non-empty answers
    const unanswered = questions.filter((q) => {
      const val = answers[q.id];
      return val === undefined || val === null || String(val).trim() === "";
    });

    if (unanswered.length > 0) {
      setValidationError(
        `Please answer all questions before submitting. (${questions.length - unanswered.length} of ${questions.length} completed)`
      );
      return;
    }

    const tooShortOpen = questions.find((q) => {
      if (q.type === "open") {
        const val = String(answers[q.id] || "").trim();
        return val.length < 10;
      }
      return false;
    });

    if (tooShortOpen) {
      setValidationError(
        "Free-text answers must be at least 10 characters long to provide meaningful context."
      );
      return;
    }

    setSubmitting(true);
    try {
      const payload = Object.entries(answers).map(([question_id, answer]) => ({
        question_id,
        answer: String(answer).trim(),
      }));

      await api("/diagnostic/submit", {
        method: "POST",
        body: JSON.stringify({ answers: payload }),
      });

      onDone();
    } catch (err) {
      setError(err.message || "Failed to submit diagnostic assessment. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="card loading-card">
        <div className="spinner" />
        <p>Loading personalized AI diagnostic questions…</p>
      </div>
    );
  }

  if (error && questions.length === 0) {
    return (
      <div className="card error-card">
        <h3>Unable to load diagnostic</h3>
        <p className="error">{error}</p>
        <button onClick={fetchQuestions} className="btn-secondary">
          Try Again
        </button>
      </div>
    );
  }

  const answeredCount = Object.values(answers).filter((v) => v !== undefined && String(v).trim() !== "").length;
  const progressPct = questions.length > 0 ? Math.round((answeredCount / questions.length) * 100) : 0;

  return (
    <div className="diagnostic-wrap">
      <div className="card diagnostic-header-card">
        <div className="diagnostic-title-area">
          <h2>AI Diagnostic Assessment</h2>
          <p className="muted">
            Evaluate your day-to-day AI adoption, tooling maturity, and data handling practices.
            Your answers are confidential and protected by small-group privacy guarantees.
          </p>
        </div>

        {/* Progress Tracker */}
        <div className="progress-container">
          <div className="progress-label">
            <span>Progress: {answeredCount} of {questions.length} answered</span>
            <span className="font-semibold">{progressPct}%</span>
          </div>
          <div className="progress-bar-bg">
            <div className="progress-bar-fill" style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      </div>

      {validationError && (
        <div className="notice-warning">
          ⚠️ {validationError}
        </div>
      )}

      {error && (
        <div className="notice-error">
          ❌ {error}
        </div>
      )}

      <form onSubmit={submit}>
        {questions.map((q, idx) => {
          const isAnswered = answers[q.id] !== undefined && String(answers[q.id]).trim() !== "";
          const options = Array.isArray(q.options) ? q.options : [];

          return (
            <div key={q.id} className={`card question-card ${isAnswered ? "question-answered" : ""}`}>
              <div className="question-header">
                <span className="question-number-badge">Question {idx + 1} of {questions.length}</span>
                {isAnswered && <span className="answered-check">✓ Answered</span>}
              </div>

              <p className="question-text">{q.text}</p>

              <div className="input-field-group">
                {q.type === "mcq" ? (
                  <select
                    className="select-input"
                    value={answers[q.id] || ""}
                    onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                    disabled={submitting}
                  >
                    <option value="" disabled>Select the most fitting option…</option>
                    {options.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : (
                  <textarea
                    className="textarea-input"
                    rows={4}
                    placeholder="Describe your workflow, tools, or specific practices in detail…"
                    value={answers[q.id] || ""}
                    onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                    disabled={submitting}
                  />
                )}
              </div>
            </div>
          );
        })}

        <div className="card diagnostic-actions-card">
          <div className="actions-info">
            {answeredCount < questions.length ? (
              <span className="muted text-sm">
                {questions.length - answeredCount} questions remaining
              </span>
            ) : (
              <span className="text-success text-sm font-semibold">
                ✓ All questions completed. Ready to submit!
              </span>
            )}
          </div>
          <div className="actions-buttons">
            {onCancel && (
              <button
                type="button"
                className="btn-secondary"
                onClick={onCancel}
                disabled={submitting}
              >
                Back to Dashboard
              </button>
            )}
            <button
              type="submit"
              className="btn-primary"
              disabled={submitting}
            >
              {submitting ? "Analyzing & Generating Report…" : "Submit Diagnostic Assessment"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
