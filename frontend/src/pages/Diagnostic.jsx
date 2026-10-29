import React, { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, ShieldCheck, Send } from "lucide-react";
import { api } from "../api";
import {
  PageTitle,
  useRemote,
  Loading,
  ErrorMessage,
  Icon,
  Badge,
  PrivacyNote,
} from "../components";
export default function Diagnostic({ onDone, onCancel, mode }) {
  const {
    data: questions,
    error: loadError,
    reload,
  } = useRemote("/diagnostic/questions");
  const [answers, setAnswers] = useState({}),
    [step, setStep] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    const warn = (e) => {
      if (Object.keys(answers).length) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [answers]);
  if (loadError) return <ErrorMessage message={loadError} retry={reload} />;
  if (!questions) return <Loading />;
  const question = questions[step],
    reviewing = step === questions.length;
  const value = question ? answers[question.id] || "" : "";
  const valid =
    question && (question.type === "mcq" ? !!value : value.trim().length >= 10);
  const answered = Object.values(answers).filter(
    (a) => a.trim().length > 0,
  ).length;
  async function submit() {
    setBusy(true);
    setError("");
    try {
      await api("/diagnostic/submit", {
        method: "POST",
        body: JSON.stringify({
          answers: questions.map((q) => ({
            question_id: q.id,
            answer: answers[q.id] || "",
          })),
        }),
      });
      setAnswers({});
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="YOUR ASSESSMENT"
        title="A moment to reflect."
        description="Tell us how you use AI at work. Honest answers make the next steps more useful."
      />
      <div className="assessment-layout">
        <section className="panel question-panel">
          <div className="question-progress">
            <span>
              {reviewing
                ? "Ready to submit"
                : "Question " + (step + 1) + " of " + questions.length}
            </span>
            <strong>
              {Math.round((answered / questions.length) * 100)}% answered
            </strong>
          </div>
          <div
            className="progress-track"
            role="progressbar"
            aria-label="Assessment completion"
            aria-valuenow={answered}
            aria-valuemin={0}
            aria-valuemax={questions.length}
          >
            <span
              style={{ width: (answered / questions.length) * 100 + "%" }}
            />
          </div>
          {reviewing ? (
            <>
              <div className="review-intro">
                <span className="empty-icon mint">
                  <Icon icon={Check} size={27} />
                </span>
                <h2>You're ready for your next step.</h2>
                <p>
                  Review your answers before submitting. This replaces any
                  previous assessment and improvement plan in this organization.
                </p>
              </div>
              <div className="answer-review">
                {questions.map((q, i) => (
                  <button key={q.id} onClick={() => setStep(i)}>
                    <span>{i + 1}</span>
                    <div>
                      <strong>{q.text}</strong>
                      <p>{answers[q.id]}</p>
                    </div>
                    <span className="edit-label">Edit</span>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div className="question-body" key={question.id}>
              <Badge tone="purple">
                {question.id.startsWith("common-")
                  ? "Everyday AI habits"
                  : "Your role in practice"}
              </Badge>
              <fieldset>
                <legend>{question.text}</legend>
                {question.type === "mcq" ? (
                  <div className="answer-options">
                    {question.options.map((option, i) => (
                      <label
                        key={option}
                        className={
                          "answer-option " + (value === option ? "chosen" : "")
                        }
                      >
                        <input
                          type="radio"
                          name={question.id}
                          checked={value === option}
                          onChange={() =>
                            setAnswers({ ...answers, [question.id]: option })
                          }
                        />
                        <span className="option-letter">
                          {String.fromCharCode(65 + i)}
                        </span>
                        <span>{option}</span>
                        <span className="option-check">
                          {value === option && <Icon icon={Check} size={14} />}
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <>
                    <label className="sr-only" htmlFor="written-answer">
                      Your written answer
                    </label>
                    <textarea
                      id="written-answer"
                      rows={7}
                      maxLength={2000}
                      value={value}
                      onChange={(e) =>
                        setAnswers({
                          ...answers,
                          [question.id]: e.target.value,
                        })
                      }
                      placeholder="Describe the task, how you used AI, and how you checked the result. Use anonymized details only."
                    />
                    <div className="input-hint">
                      <span>
                        At least 10 characters. No names, customer details or
                        confidential information.
                      </span>
                      <span>{value.length}/2,000</span>
                    </div>
                  </>
                )}
              </fieldset>
            </div>
          )}
          <PrivacyNote>
            {mode === "mock"
              ? "Demo mode assigns a fixed sample score to written answers."
              : "Written answers are sent to the configured AI provider. Remove sensitive information before submitting."}
          </PrivacyNote>
          {error && <ErrorMessage message={error} />}
          <div className="question-controls">
            <button
              className="button quiet"
              disabled={busy}
              onClick={() => (step ? setStep(step - 1) : onCancel())}
            >
              <Icon icon={ArrowLeft} />
              {step ? "Back" : "My report"}
            </button>
            {reviewing ? (
              <button
                className="button primary"
                disabled={busy}
                onClick={submit}
              >
                {busy ? "Saving and scoring…" : "Submit assessment"}
                <Icon icon={Send} size={16} />
              </button>
            ) : (
              <button
                className="button primary"
                disabled={!valid}
                onClick={() => {
                  setStep(step + 1);
                  setError("");
                }}
              >
                {step === questions.length - 1 ? "Review answers" : "Continue"}
                <Icon icon={ArrowRight} />
              </button>
            )}
          </div>
        </section>
        <aside className="assessment-aside">
          <span className="empty-icon">
            <Icon icon={ShieldCheck} size={25} />
          </span>
          <h2>
            A useful reflection,
            <br />
            not a performance review.
          </h2>
          <p>
            There are no perfect answers. Reflect on what you actually do today.
          </p>
          <div className="aside-line" />
          <h3>Your answers stay private</h3>
          <p>
            Leadership sees group results only when enough people have completed
            the assessment.
          </p>
          <h3>One week. One small step.</h3>
          <p>
            Your report will suggest practical activities to help you build a
            stronger habit.
          </p>
          <p className="small-note">
            Drafts stay in this page only. Leaving or refreshing the page clears
            unsent answers.
          </p>
        </aside>
      </div>
    </>
  );
}
