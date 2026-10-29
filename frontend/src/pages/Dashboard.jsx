import React, { useEffect, useState, useCallback } from "react";
import { api } from "../api.js";

export default function Dashboard({ org, onNavigate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");

    try {
      const res = await api(`/dashboard?org_id=${org.org_id}`);
      setData(res);
    } catch (err) {
      setError(err.message || "Failed to load dashboard data. Please verify your permissions.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [org]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  function formatRiskLabel(key) {
    if (!key) return "";
    return key
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
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

  if (loading) {
    return (
      <div className="card loading-card">
        <div className="spinner" />
        <p>Loading leadership dashboard for {org.org_name}…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card error-card">
        <h3>Unable to load dashboard</h3>
        <p className="error">{error}</p>
        <button onClick={() => loadDashboard()} className="btn-secondary">
          Try Again
        </button>
      </div>
    );
  }

  const departments = data?.departments || [];
  const topRisks = data?.top_risks || [];
  const hasDepartments = departments.length > 0;

  // Aggregate high-level stats strictly from backend response
  const totalAssessedEmployees = departments.reduce((acc, d) => acc + (d.responded || 0), 0);
  const totalEmployeesInAssessedDepts = departments.reduce((acc, d) => acc + (d.employees || 0), 0);
  const overallAverage = hasDepartments && totalAssessedEmployees > 0
    ? (departments.reduce((acc, d) => acc + (d.average_score * d.responded), 0) / totalAssessedEmployees).toFixed(2)
    : null;

  return (
    <div className="dashboard-container">
      {/* Top Header */}
      <div className="dashboard-header card">
        <div className="dashboard-title-area">
          <div className="dashboard-pill">Executive Leadership View</div>
          <h2>{data?.organization || org.org_name} — AI Maturity Dashboard</h2>
          <p className="muted">
            Aggregated diagnostics, AI maturity levels, and privacy-filtered risk posture across qualifying departments.
          </p>
        </div>
        <div className="dashboard-header-actions">
          <button
            onClick={() => loadDashboard(true)}
            disabled={refreshing}
            className="btn-secondary refresh-btn"
            title="Refresh dashboard data"
          >
            {refreshing ? "Refreshing…" : "↻ Refresh"}
          </button>
          {onNavigate && (
            <button
              onClick={() => onNavigate("insights")}
              className="btn-primary"
              title="View AI governance recommendations"
            >
              ✨ AI Insights
            </button>
          )}
          {onNavigate && (
            <button onClick={() => onNavigate("diagnostic")} className="btn-outline">
              Take Diagnostic
            </button>
          )}
        </div>
      </div>

      {/* Privacy Guarantee Banner */}
      <div className="privacy-banner">
        <div className="privacy-banner-icon">🔒</div>
        <div className="privacy-banner-text">
          <strong>Small-Group Privacy Protection Enforced</strong>
          <p>
            To prevent de-anonymization, departments with fewer than 5 completed assessments are suppressed from individual display.
            Qualifying small teams are aggregated into &ldquo;Other teams&rdquo; when total cohort size reaches 5 or more.
          </p>
        </div>
      </div>

      {/* KPI Summary Cards */}
      <div className="stats-grid">
        <div className="card stat-card">
          <div className="stat-label">Assessed Departments</div>
          <div className="stat-value">{departments.length}</div>
          <div className="stat-subtext">Meeting &ge; 5 response threshold</div>
        </div>

        <div className="card stat-card">
          <div className="stat-label">Assessed Headcount</div>
          <div className="stat-value">{totalAssessedEmployees}</div>
          <div className="stat-subtext">
            {totalEmployeesInAssessedDepts > 0
              ? `Out of ${totalEmployeesInAssessedDepts} team members (${Math.round((totalAssessedEmployees / totalEmployeesInAssessedDepts) * 100)}%)`
              : "Completed assessments"}
          </div>
        </div>

        <div className="card stat-card">
          <div className="stat-label">Organization AI Score</div>
          <div className="stat-value">
            {overallAverage ? `${overallAverage} / 5.0` : "N/A"}
          </div>
          <div className="stat-subtext">Weighted by department respondents</div>
        </div>

        <div className="card stat-card">
          <div className="stat-label">Active Risk Categories</div>
          <div className="stat-value">{topRisks.length}</div>
          <div className="stat-subtext">Isolated from qualifying cohorts</div>
        </div>
      </div>

      {/* Department Breakdown Section */}
      <div className="card section-card">
        <div className="section-header">
          <h3>Department AI Readiness</h3>
          <span className="muted text-sm">{departments.length} department{departments.length === 1 ? "" : "s"} reported</span>
        </div>

        {hasDepartments ? (
          <div className="dept-table-wrapper">
            <table className="dept-table">
              <thead>
                <tr>
                  <th>Department</th>
                  <th>Maturity Level</th>
                  <th>Average Score</th>
                  <th>Headcount &amp; Participation</th>
                  <th>Governance</th>
                </tr>
              </thead>
              <tbody>
                {departments.map((dept) => {
                  const pct = dept.employees > 0 ? Math.round((dept.responded / dept.employees) * 100) : 0;
                  const scoreWidth = Math.min(100, Math.max(0, (dept.average_score / 5.0) * 100));

                  return (
                    <tr key={dept.department} className={dept.department === "Other teams" ? "row-other-teams" : ""}>
                      <td className="dept-name-cell">
                        <strong>{dept.department}</strong>
                        {dept.department === "Other teams" && (
                          <span className="other-badge">Privacy Aggregate</span>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${getLevelBadgeClass(dept.level)}`}>
                          {dept.level}
                        </span>
                      </td>
                      <td className="score-cell">
                        <div className="score-number">{dept.average_score.toFixed(2)} <span className="muted">/ 5.00</span></div>
                        <div className="score-bar-bg">
                          <div
                            className={`score-bar-fill ${getLevelBadgeClass(dept.level)}`}
                            style={{ width: `${scoreWidth}%` }}
                          />
                        </div>
                      </td>
                      <td className="headcount-cell">
                        <div><strong>{dept.responded}</strong> / {dept.employees} employees</div>
                        <div className="muted text-sm">{pct}% completion</div>
                      </td>
                      <td>
                        {onNavigate && (
                          <button
                            onClick={() => onNavigate("insights", dept)}
                            className="btn-outline btn-sm"
                            title={`View AI governance insights for ${dept.department}`}
                          >
                            Insights →
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-state-icon">📊</div>
            <h4>No Departments Assessed Yet</h4>
            <p className="muted">
              Individual and department scores remain strictly confidential until at least 5 qualifying employees in a department submit their assessments.
            </p>
          </div>
        )}
      </div>

      {/* Top Risks Section */}
      <div className="card section-card">
        <div className="section-header">
          <h3>Top Identified Risks</h3>
          <span className="muted text-sm">Derived exclusively from qualifying departments</span>
        </div>

        {topRisks.length > 0 ? (
          <div className="risks-list">
            {topRisks.map(([riskKey, count]) => (
              <div key={riskKey} className="risk-item">
                <div className="risk-item-info">
                  <span className="risk-warning-icon">⚠️</span>
                  <div>
                    <span className="risk-title">{formatRiskLabel(riskKey)}</span>
                    <span className="risk-code"><code>{riskKey}</code></span>
                  </div>
                </div>
                <div className="risk-frequency-badge">
                  Flagged in <strong>{count}</strong> {count === 1 ? "department" : "departments"}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-state-icon">✅</div>
            <h4>No Critical Risks Identified</h4>
            <p className="muted">
              {hasDepartments
                ? "No high-severity risks were flagged across assessed departments."
                : "Risk data will appear once qualifying departments are assessed."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
