import React, { useState } from "react";
import {
  ShieldCheck,
  LockKeyhole,
  Users,
  ArrowUpRight,
  RefreshCw,
  Info,
  ChevronRight,
} from "lucide-react";
import {
  useRemote,
  PageTitle,
  Loading,
  ErrorMessage,
  Icon,
  Badge,
  PrivacyNote,
} from "../components";
export default function Dashboard() {
  const { data, error, reload } = useRemote("/dashboard", 2000);
  const [selected, setSelected] = useState(null);
  if (error) return <ErrorMessage message={error} retry={reload} />;
  if (!data) return <Loading />;
  const visible = data.departments.filter((d) => !d.protected);
  const focus = visible.find((d) => d.department === selected) || visible[0];
  return (
    <>
      <PageTitle
        eyebrow="LEADERSHIP / OVERVIEW"
        title="Your teams. A clearer picture."
        description="Understand AI habits across your organization, with employee privacy built in."
      >
        <button className="button secondary" onClick={reload}>
          <Icon icon={RefreshCw} size={16} />
          Refresh
        </button>
      </PageTitle>
      {(data.ai_mode === "mock" || data.contains_demo_data) && (
        <div className="demo-banner">
          <span className="demo-dot" />
          <strong>Demo data is included.</strong>
          <span>
            Some scores are synthetic or use a fixed fixture. They do not
            measure real employee capability.
          </span>
        </div>
      )}
      <div className="metric-grid">
        <div className="metric-card">
          <div className="metric-top">
            <span>Teams with visible results</span>
            <span className="metric-icon lavender">
              <Icon icon={Users} />
            </span>
          </div>
          <div className="metric-value">
            {visible.length}
            <small> / {data.departments.length}</small>
          </div>
          <p>Only groups meeting the privacy threshold</p>
        </div>
        <div className="metric-card">
          <div className="metric-top">
            <span>Minimum group size</span>
            <span className="metric-icon mint">
              <Icon icon={ShieldCheck} />
            </span>
          </div>
          <div className="metric-value">
            5<small> people</small>
          </div>
          <p>Completed assessments, counted once each</p>
        </div>
        <div className="metric-card privacy-metric">
          <div className="metric-top">
            <span>Employee privacy</span>
            <Icon icon={LockKeyhole} />
          </div>
          <h2>
            Individual answers
            <br /> stay individual.
          </h2>
          <p>Leadership receives protected group results.</p>
        </div>
      </div>
      <div className="dashboard-grid">
        <section className="panel teams-panel">
          <div className="panel-heading">
            <div>
              <h2>AI maturity by team</h2>
              <p>Average of each participant's completed assessment</p>
            </div>
            <Badge>1–5 scale</Badge>
          </div>
          <div className="team-columns">
            <span>DEPARTMENT</span>
            <span>MATURITY</span>
            <span>COMPLETED</span>
          </div>
          {data.departments.map((team) => (
            <div
              key={team.department}
              className={"team-row " + (team.protected ? "protected-row" : "")}
            >
              <div className="team-name">
                <span
                  className={"team-avatar " + (team.protected ? "muted" : "")}
                >
                  {team.department.slice(0, 2).toUpperCase()}
                </span>
                <div>
                  <strong>{team.department}</strong>
                  {team.protected ? (
                    <small>
                      <Icon icon={LockKeyhole} size={11} />
                      Results protected
                    </small>
                  ) : (
                    <button
                      className="text-button"
                      onClick={() => setSelected(team.department)}
                    >
                      View risk signals
                      <Icon icon={ChevronRight} size={12} />
                    </button>
                  )}
                </div>
              </div>
              <div className="team-score">
                {team.protected ? (
                  <span className="protected-track">
                    <Icon icon={LockKeyhole} size={13} />
                    <span>Not enough completed assessments</span>
                  </span>
                ) : (
                  <>
                    <div className="score-label">
                      <strong>
                        {team.average_score.toFixed(2)}
                        <small> / 5</small>
                      </strong>
                      <span>{team.level}</span>
                    </div>
                    <div className="score-track">
                      <span
                        style={{ width: (team.average_score / 5) * 100 + "%" }}
                      />
                    </div>
                  </>
                )}
              </div>
              <span className="participant-count">
                {team.protected ? "—" : team.responded}
              </span>
            </div>
          ))}
          <PrivacyNote>
            Small-group scores, counts and risks are withheld. No company-wide
            total is shown, so hidden results cannot be obtained by subtracting
            visible teams.
          </PrivacyNote>
        </section>
        <section className="panel risk-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">A CONVERSATION STARTER</p>
              <h2>Risk signals</h2>
            </div>
            <Icon icon={Info} />
          </div>
          {focus ? (
            <>
              <label className="sr-only" htmlFor="risk-team">
                Team for risk signals
              </label>
              <select
                id="risk-team"
                value={focus.department}
                onChange={(e) => setSelected(e.target.value)}
              >
                {visible.map((d) => (
                  <option key={d.department}>{d.department}</option>
                ))}
              </select>
              <p className="risk-intro">
                Signals from written answers. Use them to guide support and
                training.
              </p>
              <div className="risk-list">
                {focus.risks.map((r) => (
                  <div className="risk-item" key={r.key}>
                    <span>{r.label}</span>
                    <Badge tone={r.people === null ? "neutral" : "amber"}>
                      {r.people === null ? "Protected" : `${r.people} people`}
                    </Badge>
                  </div>
                ))}
              </div>
              <p className="small-note">
                <Icon icon={LockKeyhole} size={14} />
                Exact counts require at least five people with the signal and
                five without it. Protected does not mean no risk exists.
              </p>
            </>
          ) : (
            <div className="risk-empty">
              <Icon icon={ShieldCheck} size={35} />
              <h3>Privacy comes first</h3>
              <p>
                Team results require five completed assessments. Exact risk
                counts also protect people without each signal.
              </p>
            </div>
          )}
        </section>
      </div>
      <div className="insight-strip">
        <span className="insight-icon">
          <Icon icon={ArrowUpRight} size={24} />
        </span>
        <div>
          <h3>Use these results to start a conversation.</h3>
          <p>
            A self-reported diagnostic is a starting point for learning, not a
            measure of individual job performance.
          </p>
        </div>
      </div>
      <div className="refresh-note">
        <span className="status-dot" />
        Active views refresh every 2 seconds. Updated{" "}
        {new Date(
          data.updated_at +
            (data.updated_at.endsWith("Z") || data.updated_at.includes("+")
              ? ""
              : "Z"),
        ).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        .
      </div>
    </>
  );
}
