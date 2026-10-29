import React, { useState } from "react";
import {
  ArrowRight,
  ClipboardList,
  ShieldCheck,
  Sprout,
  ChevronDown,
  RefreshCw,
  Clock3,
} from "lucide-react";
import { api } from "../api";
import {
  useRemote,
  PageTitle,
  Loading,
  ErrorMessage,
  Empty,
  Icon,
  Badge,
  PrivacyNote,
} from "../components";
export default function Report({ onNavigate }) {
  const { data, error, reload } = useRemote("/reports/me", 2000);
  const [busy, setBusy] = useState(false),
    [retryError, setRetryError] = useState("");
  if (error) return <ErrorMessage message={error} retry={reload} />;
  if (!data) return <Loading />;
  async function retry() {
    setBusy(true);
    setRetryError("");
    try {
      await api("/diagnostic/retry", { method: "POST" });
      reload();
    } catch (e) {
      setRetryError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (data.status === "not_started")
    return (
      <>
        <PageTitle
          eyebrow="YOUR PERSONAL REPORT"
          title="Your next chapter starts here."
          description="A short assessment. A clearer understanding. A practical way forward."
        />
        <Empty
          title="Make space for a little reflection."
          action="Start my assessment"
          onAction={() => onNavigate("diagnostic")}
        >
          Answer a few questions about your AI habits to get a personal report
          and a private one-week improvement plan.
        </Empty>
        {data.legacy_answers > 0 && (
          <div className="notice">
            Older answers are preserved, but their completeness cannot be
            verified. Take a full assessment to replace them, or delete them in
            Privacy & data.
          </div>
        )}
      </>
    );
  if (data.status !== "completed")
    return (
      <>
        <PageTitle
          eyebrow="YOUR PERSONAL REPORT"
          title="Your answers are saved."
          description="We won't invent a score when the AI assessment is unavailable."
        />
        <div className="panel pending-panel">
          <span className="empty-icon">
            <Icon icon={Clock3} size={28} />
          </span>
          <h2>
            {data.status === "scoring"
              ? "Scoring is in progress"
              : "Waiting for a valid AI result"}
          </h2>
          <p>
            Your report and group contribution will be ready after all required
            answers have valid scores. Your written answers are safely saved.
          </p>
          <p className="small-note">
            If a scoring request was interrupted, wait a minute before retrying.
          </p>
          {retryError && <ErrorMessage message={retryError} />}
          <div className="button-row">
            <button className="button primary" disabled={busy} onClick={retry}>
              <Icon icon={RefreshCw} />
              {busy ? "Retrying…" : "Retry scoring"}
            </button>
            <button
              className="button secondary"
              onClick={() => onNavigate("diagnostic")}
            >
              Retake assessment
            </button>
            <button
              className="button quiet"
              onClick={() => onNavigate("privacy")}
            >
              Manage my data
            </button>
          </div>
        </div>
      </>
    );
  const completed = data.actions.filter((a) => a.done).length;
  return (
    <>
      <PageTitle
        eyebrow="YOUR PERSONAL REPORT"
        title={"A clearer starting point, " + data.name.split(" ")[0] + "."}
        description="Reflect on today's habits, then choose one small step for the week ahead."
      >
        <button
          className="button secondary"
          onClick={() => onNavigate("diagnostic")}
        >
          <Icon icon={ClipboardList} size={16} />
          Retake assessment
        </button>
      </PageTitle>
      {data.ai_mode === "mock" && (
        <div className="demo-banner">
          <span className="demo-dot" />
          <strong>Sample results.</strong>
          <span>
            This report includes synthetic or fixed demo scores, not a live AI
            evaluation.
          </span>
        </div>
      )}
      <div className="report-grid">
        <section className="panel report-summary">
          <div>
            <p className="eyebrow">YOUR CURRENT MATURITY</p>
            <h2>{data.level}</h2>
            <p>
              You have a starting point. The useful question now is which habit
              to strengthen next.
            </p>
            <Badge tone="green">{data.answered} questions completed</Badge>
          </div>
          <div
            className="score-ring"
            style={{ "--score-angle": (data.average_score / 5) * 360 + "deg" }}
          >
            <div>
              <strong>{data.average_score.toFixed(2)}</strong>
              <span>OUT OF 5</span>
            </div>
          </div>
        </section>
        <section className="panel plan-teaser">
          <span className="metric-icon mint">
            <Icon icon={Sprout} size={22} />
          </span>
          <h2>Turn insight into a habit.</h2>
          <p>
            Your private one-week plan has {data.actions.length} practical{" "}
            {data.actions.length === 1 ? "activity" : "activities"} to try.
          </p>
          <div className="mini-progress">
            <span
              style={{
                width:
                  (data.actions.length
                    ? (completed / data.actions.length) * 100
                    : 0) + "%",
              }}
            />
          </div>
          <small>
            {completed} of {data.actions.length} completed
          </small>
          <button className="button primary" onClick={() => onNavigate("plan")}>
            Open my improvement plan
            <Icon icon={ArrowRight} />
          </button>
        </section>
      </div>
      <section className="panel report-risks">
        <div className="panel-heading">
          <div>
            <h2>Your risk signals</h2>
            <p>Patterns identified in your written answers</p>
          </div>
          <Icon icon={ShieldCheck} />
        </div>
        {data.risks.length ? (
          <div className="risk-chips">
            {data.risks.map((r) => (
              <Badge key={r.key} tone="amber">
                {r.label}
              </Badge>
            ))}
          </div>
        ) : (
          <p>
            No risk labels were returned for these answers. This does not
            establish that your AI use is risk-free.
          </p>
        )}
      </section>
      <section className="panel evidence-panel">
        <div className="panel-heading">
          <div>
            <h2>Understand your result</h2>
            <p>See each answer, its score, and the explanation behind it.</p>
          </div>
          <Badge>
            {data.ai_mode === "mock" ? "Demo fixture" : "AI + questionnaire"}
          </Badge>
        </div>
        {data.answers.map((a, i) => (
          <details key={a.question_id} className="answer-detail">
            <summary>
              <span className="answer-number">
                {String(i + 1).padStart(2, "0")}
              </span>
              <strong>{a.question}</strong>
              <Badge tone={a.type === "open" ? "purple" : "neutral"}>
                {a.score} / 5
              </Badge>
              <Icon icon={ChevronDown} size={16} />
            </summary>
            <div className="answer-detail-body">
              <p className="eyebrow">YOUR ANSWER</p>
              <p>{a.answer}</p>
              <p className="eyebrow">
                {a.type === "open"
                  ? "SCORING EXPLANATION"
                  : "QUESTIONNAIRE RUBRIC"}
              </p>
              <p>{a.reason}</p>
            </div>
          </details>
        ))}
        <div className="method-note">
          <h3>How the score works</h3>
          <p>
            {data.scoring_note} Beginner: below 2; Exploring: 2 to below 3;
            Practitioner: 3 to below 4; Leader: 4 or above. Displayed averages
            are rounded to two decimals.
          </p>
          <p className="small-note">
            Questionnaire {data.question_version} · Rubric {data.prompt_version}{" "}
            · {data.model}
          </p>
        </div>
      </section>
      <PrivacyNote>
        This report is visible only to you. Your organization receives protected
        group results, never this answer-by-answer view.
      </PrivacyNote>
    </>
  );
}
