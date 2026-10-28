import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Report({ onRetake, onViewDashboard }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchReport();
  }, []);

  async function fetchReport() {
    setLoading(true);
    setError("");
    try {
      const data = await api("/reports/me");
      setReport(data);
    } catch (err) {
      setError(err.message || "Failed to load diagnostic report");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setIsDeleting(true);
    setError("");
    try {
      const res = await api("/reports/me", { method: "DELETE" });
      setMessage(res.message || "Your diagnostic data and report have been permanently deleted.");
      setShowConfirm(false);
      // Refresh report data from server to reflect immediate deletion
      await fetchReport();
    } catch (err) {
      setError(err.message || "Failed to delete diagnostic data");
    } finally {
      setIsDeleting(false);
    }
  }

  function getLevelBadgeClass(level) {
    switch (level?.toLowerCase()) {
      case "leader":
        return "badge-leader";
      case "practitioner":
        return "badge-practitioner";
      case "exploring":
        return "badge-exploring";
      case "beginner":
      default:
        return "badge-beginner";
    }
  }

  function formatRiskLabel(key) {
    if (!key) return "";
    return key
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }

  if (loading && !report) {
    return (
      <div className="card loading-card">
        <div className="spinner" />
        <p>Loading your AI diagnostic report…</p>
      </div>
    );
  }

  const hasData = report && report.answered > 0;

  return (
    <div className="report-container">
      {message && <div className="notice-success">✅ {message}</div>}
      {error && <div className="notice-error">❌ {error}</div>}

      {hasData ? (
        <>
          {/* Main Executive Summary Card */}
          <div className="card report-header-card">
            <div className="report-title-row">
              <div>
                <span className="text-sm muted">Confidential Employee Diagnostic</span>
                <h2>{report.name}</h2>
                <p className="org-subtext">🏢 <strong>Organization:</strong> {report.organization}</p>
              </div>
              <div className="report-score-box">
                <span className={`badge ${getLevelBadgeClass(report.level)}`}>
                  {report.level}
                </span>
                <div className="score-big">{report.average_score.toFixed(2)}</div>
                <span className="muted text-sm">out of 5.00 ({report.answered} questions)</span>
              </div>
            </div>
          </div>

          {/* Identified Risks Card */}
          <div className="card section-card">
            <div className="section-header">
              <h3>Identified Practice Risks</h3>
              <span className="muted text-sm">Detected from your workflow descriptions</span>
            </div>

            {report.risks && report.risks.length > 0 ? (
              <div className="risks-list">
                {report.risks.map((r) => (
                  <div key={r} className="risk-item">
                    <div className="risk-item-info">
                      <span className="risk-warning-icon">⚠️</span>
                      <div>
                        <span className="risk-title">{formatRiskLabel(r)}</span>
                        <span className="risk-code"><code>{r}</code></span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">✅</div>
                <h4>Zero Practice Risks Detected</h4>
                <p className="muted">Your responses adhere to secure AI tooling and policy practices.</p>
              </div>
            )}
          </div>

          {/* Recommended Next Steps Card */}
          <div className="card section-card">
            <div className="section-header">
              <h3>Recommended Next Steps</h3>
              <span className="muted text-sm">Targeted actions to elevate your AI maturity</span>
            </div>

            {report.next_steps && report.next_steps.length > 0 ? (
              <ul className="next-steps-list">
                {report.next_steps.map((step, idx) => (
                  <li key={idx} className="next-step-item">
                    <span className="step-number">{idx + 1}</span>
                    <span className="step-text">{step}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No specific next steps required at this time.</p>
            )}
          </div>

          {/* Employee Right to Delete Card */}
          <div className="card section-card privacy-card">
            <div className="privacy-card-header">
              <span className="privacy-icon">🛡️</span>
              <div>
                <h3>Employee Right to Delete</h3>
                <p className="muted text-sm">
                  You maintain full sovereignty over your diagnostic data. Deleting your data immediately clears all your answers,
                  erases your personal evaluation, and recalculates all company dashboards without your responses.
                </p>
              </div>
            </div>

            {!showConfirm ? (
              <div className="delete-action-row">
                <button
                  type="button"
                  className="btn-danger"
                  onClick={() => setShowConfirm(true)}
                >
                  Delete My Diagnostic Data
                </button>
                {onViewDashboard && (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={onViewDashboard}
                  >
                    View Leadership Dashboard
                  </button>
                )}
              </div>
            ) : (
              <div className="confirm-box" role="alert">
                <div className="confirm-icon">⚠️</div>
                <div className="confirm-body">
                  <h4>Permanently delete all your diagnostic responses?</h4>
                  <p>
                    This will immediately purge all answers and evaluation reports for <strong>{report.organization}</strong>.
                    This action is permanent and cannot be undone.
                  </p>
                  <div className="confirm-actions">
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={handleDelete}
                      disabled={isDeleting}
                    >
                      {isDeleting ? "Deleting Permanently…" : "Yes, Delete Everything"}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setShowConfirm(false)}
                      disabled={isDeleting}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        /* Empty / Not Assessed State */
        <div className="card empty-report-card">
          <div className="empty-state-icon">📋</div>
          <h2>Diagnostic Report: Not Assessed</h2>
          <p className="muted">
            You do not currently have any active diagnostic answers or reports in <strong>{report?.organization || "this organization"}</strong>.
          </p>
          <div className="empty-actions">
            {onRetake && (
              <button className="btn-primary" onClick={onRetake}>
                Take Diagnostic Assessment →
              </button>
            )}
            {onViewDashboard && (
              <button className="btn-secondary" onClick={onViewDashboard}>
                View Leadership Dashboard
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
