import React, { useState } from "react";
import {
  Sprout,
  Check,
  Clock3,
  ArrowRight,
  CalendarDays,
  ShieldCheck,
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
export default function Plan({ onNavigate }) {
  const { data, setData, error, reload } = useRemote("/reports/me");
  const [saving, setSaving] = useState(""),
    [saveError, setSaveError] = useState("");
  if (error) return <ErrorMessage message={error} retry={reload} />;
  if (!data) return <Loading />;
  if (data.status !== "completed")
    return (
      <>
        <PageTitle
          eyebrow="YOUR ONE-WEEK PLAN"
          title="Small steps. Stronger habits."
          description="A private plan that starts with your assessment."
        />
        <Empty
          title="Your plan starts with a completed assessment."
          action="Go to my report"
          onAction={() => onNavigate("report")}
        >
          Complete your diagnostic and resolve any pending scoring to unlock
          practical activities.
        </Empty>
      </>
    );
  async function save(action, changes) {
    setSaving(action.id);
    setSaveError("");
    try {
      const updated = await api("/reports/me/actions/" + action.id, {
        method: "PATCH",
        body: JSON.stringify({
          done: action.done,
          due_date: action.due_date,
          ...changes,
        }),
      });
      setData((old) => ({
        ...old,
        actions: old.actions.map((a) => (a.id === action.id ? updated : a)),
      }));
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setSaving("");
    }
  }
  const done = data.actions.filter((a) => a.done).length;
  return (
    <>
      <PageTitle
        eyebrow="YOUR ONE-WEEK PLAN"
        title="Small steps. Stronger habits."
        description="Choose a moment this week to practise. Your progress belongs to you."
      >
        <Badge tone="green">
          <Icon icon={ShieldCheck} size={13} />
          Only you can see this
        </Badge>
      </PageTitle>
      <div className="plan-banner">
        <span className="plan-banner-icon">
          <Icon icon={Sprout} size={30} />
        </span>
        <div>
          <h2>
            {done === data.actions.length
              ? "You made time to grow."
              : "A little practice goes a long way."}
          </h2>
          <p>
            {done === data.actions.length
              ? "Take what worked into your next real-world task. Activity completion does not change your assessment score."
              : "Activities selected from your answers. Choose one to practise, then mark it complete when you're ready."}
          </p>
        </div>
        <div className="plan-count">
          <strong>
            {done}
            <span> / {data.actions.length}</span>
          </strong>
          <small>ACTIVITIES COMPLETE</small>
        </div>
      </div>
      {saveError && <ErrorMessage message={saveError} />}
      <div className="action-list">
        {data.actions.map((action, i) => (
          <article
            className={"panel action-card " + (action.done ? "is-done" : "")}
            key={action.id}
          >
            <div className="action-number">
              {action.done ? (
                <Icon icon={Check} size={22} />
              ) : (
                String(i + 1).padStart(2, "0")
              )}
            </div>
            <div className="action-content">
              <div className="action-heading">
                <h2>{action.title}</h2>
                <Badge>
                  <Icon icon={Clock3} size={13} />
                  {action.minutes} min
                </Badge>
              </div>
              <p className="action-why">
                <strong>Why this activity?</strong> {action.why}
              </p>
              <p className="role-example">
                For your role, try {action.role_example}.
              </p>
              <ol className="activity-steps">
                {action.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <div className="success-box">
                <Icon icon={Check} size={17} />
                <span>
                  <strong>You'll know you're done when:</strong>{" "}
                  {action.success}
                </span>
              </div>
              <div className="action-controls">
                <label>
                  <Icon icon={CalendarDays} size={16} />
                  Target date
                  <input
                    aria-label={"Target date for " + action.title}
                    type="date"
                    value={action.due_date || ""}
                    disabled={!!saving}
                    onChange={(e) =>
                      save(action, { due_date: e.target.value || null })
                    }
                  />
                </label>
                <button
                  className={
                    "button " + (action.done ? "completed-button" : "secondary")
                  }
                  aria-pressed={action.done}
                  disabled={!!saving}
                  onClick={() => save(action, { done: !action.done })}
                >
                  <Icon icon={Check} size={17} />
                  {saving === action.id
                    ? "Saving…"
                    : action.done
                      ? "Completed · Undo"
                      : "Mark complete"}
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
      <PrivacyNote>
        Progress is self-reported and private. It never changes your assessment
        score. Retaking the assessment creates a fresh plan; deleting your data
        removes this plan too.
      </PrivacyNote>
      <button className="text-button" onClick={() => onNavigate("report")}>
        Return to my report
        <Icon icon={ArrowRight} size={16} />
      </button>
    </>
  );
}
