import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const PRIORITY_BADGES = {
  high: { label: "High Priority", class: "badge-danger" },
  medium: { label: "Medium Priority", class: "badge-warning" },
  low: { label: "Low Priority", class: "badge-neutral" },
};

export default function Insights({ org, department, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDeptId, setSelectedDeptId] = useState(department?.id != null ? String(department.id) : "");

  useEffect(() => {
    loadInsights(selectedDeptId);
  }, [selectedDeptId, org]);

  async function loadInsights(deptId) {
    setLoading(true);
    setError(null);
    try {
      const query = deptId ? `?department_id=${encodeURIComponent(deptId)}` : "";
      const result = await api(`/insights${query}`);
      setData(result);
    } catch (err) {
      setError(err.message || "Failed to load department insights.");
    } finally {
      setLoading(false);
    }
  }

  function renderSourceBadge(source) {
    if (source === "ai") {
      return <span className="source-badge source-ai">✨ Live AI Advisory Model</span>;
    }
    if (source === "mock") {
      return <span className="source-badge source-mock">🧪 Mock Simulation Mode</span>;
    }
    return <span className="source-badge source-rules">📐 Deterministic Governance Engine</span>;
  }

  if (loading) {
    return (
      <div className="card loading-card">
        <div className="spinner" />
        <p>Synthesizing privacy-safe risk patterns and recommendations…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card error-card">
        <div className="card-header-flex">
          <h2>Department Governance Insights</h2>
          {onBack && (
            <button onClick={onBack} className="btn-secondary">
              ← Back to Dashboard
            </button>
          )}
        </div>
        <div className="notice-error" style={{ marginTop: "16px" }}>
          ❌ {error}
        </div>
        <button onClick={() => loadInsights(selectedDeptId)} className="btn-primary" style={{ marginTop: "16px" }}>
          Retry
        </button>
      </div>
    );
  }

  const insightsList = data?.insights || [];
  const deptDisplayName = data?.department || department?.department;

  // Group insights by department
  const grouped = {};
  for (const item of insightsList) {
    const dept = item.department || "General";
    if (!grouped[dept]) grouped[dept] = [];
    grouped[dept].push(item);
  }
  const departmentNames = Object.keys(grouped);

  return (
    <div className="insights-container">
      {/* Header Card */}
      <div className="card executive-header-card">
        <div className="card-header-flex">
          <div>
            <div className="kicker">PRIVACY-PRESERVING AI ADVISORY</div>
            <h1 className="dashboard-title">
              {data?.organization} — {deptDisplayName ? `${deptDisplayName} Insights` : "Governance Insights"}
            </h1>
            <p className="dashboard-subtitle">
              Actionable operational guidance generated from aggregated department risk patterns. Individual responses and identities are never processed or exposed.
            </p>
          </div>
          {onBack && (
            <button onClick={onBack} className="btn-secondary">
              ← Back to Dashboard
            </button>
          )}
        </div>

        <div className="insights-meta-bar">
          <div className="meta-item">
            <span className="meta-label">Engine:</span>
            {renderSourceBadge(data?.source)}
          </div>
          <div className="meta-item">
            <span className="meta-label">Privacy Guarantee:</span>
            <span className="privacy-pill">🛡️ Small-Group Suppression (k ≥ 5)</span>
          </div>
        </div>
      </div>

      {/* Department Context Card if viewing single department */}
      {department && (
        <div className="card dept-context-card">
          <div className="dept-context-grid">
            <div className="dept-context-item">
              <span className="context-label">Department</span>
              <span className="context-val">{department.department}</span>
            </div>
            <div className="dept-context-item">
              <span className="context-label">Headcount</span>
              <span className="context-val">{department.employees}</span>
            </div>
            <div className="dept-context-item">
              <span className="context-label">Completed Assessments</span>
              <span className="context-val">{department.responded}</span>
            </div>
            <div className="dept-context-item">
              <span className="context-label">Average Score</span>
              <span className="context-val">{department.average_score ?? "—"}</span>
            </div>
            <div className="dept-context-item">
              <span className="context-label">Maturity Level</span>
              <span className="context-val font-semibold">{department.level}</span>
            </div>
          </div>
        </div>
      )}

      {/* Main Insights Content */}
      {departmentNames.length === 0 ? (
        <div className="card empty-insights-card">
          <div className="empty-state-icon">🛡️</div>
          <h3>No Eligible Department Insights</h3>
          <p className="muted">
            Under our small-group privacy policy, actionable department insights are only synthesized for departments with at least 5 completed assessments.
          </p>
          {data?.hidden_small_groups && (
            <p className="privacy-notice">
              One or more departments are currently hidden to prevent individual employee re-identification.
            </p>
          )}
        </div>
      ) : (
        <div className="insights-groups">
          {departmentNames.map((deptName) => (
            <div key={deptName} className="dept-insights-section">
              <h2 className="dept-section-title">{deptName}</h2>
              <div className="insights-cards-grid">
                {grouped[deptName].map((item, idx) => {
                  const badge = PRIORITY_BADGES[item.priority] || PRIORITY_BADGES.medium;
                  return (
                    <div key={idx} className={`card insight-card priority-border-${item.priority}`}>
                      <div className="insight-card-header">
                        <span className={`badge ${badge.class}`}>{badge.label}</span>
                        <span className="insight-dept-tag">{item.department}</span>
                      </div>

                      <div className="insight-block">
                        <span className="insight-block-label">Observed Pattern</span>
                        <p className="insight-pattern-text">{item.observed_pattern}</p>
                      </div>

                      <div className="insight-block highlight-action-block">
                        <span className="insight-block-label action-label">Recommended Action</span>
                        <p className="insight-action-text">{item.recommended_action}</p>
                      </div>

                      <div className="insight-block">
                        <span className="insight-block-label">Rationale</span>
                        <p className="insight-reason-text">{item.reason}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Privacy Footer Note */}
      {data?.hidden_small_groups && (
        <div className="card privacy-footer-card">
          <p className="privacy-footer-text">
            ℹ️ <strong>Privacy Protection Active:</strong> Departments with fewer than 5 completed diagnostics have been excluded from recommendations to maintain anonymity.
          </p>
        </div>
      )}
    </div>
  );
}
