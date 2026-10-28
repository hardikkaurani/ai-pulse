import React, { useState } from "react";
import { api, setToken } from "../api.js";

export default function OrgPicker({ orgs = [], userName, onPick, onLogout }) {
  const [selectingId, setSelectingId] = useState(null);
  const [error, setError] = useState("");

  async function pick(o) {
    setSelectingId(o.org_id);
    setError("");

    try {
      const selectResult = await api("/auth/select-org", {
        method: "POST",
        body: JSON.stringify({ org_id: o.org_id }),
      });
      setToken(selectResult.token);
      onPick(o);
    } catch (err) {
      setError(err.message || "Failed to switch organization. Please try again.");
      setSelectingId(null);
    }
  }

  const validOrgs = Array.isArray(orgs) ? orgs : [];

  return (
    <div className="org-picker-wrap">
      <div className="card org-picker-card">
        <div className="org-picker-header">
          <div className="org-logo">🏢</div>
          <h2>Select an Organization</h2>
          <p className="muted">
            {userName ? `Welcome, ${userName}. ` : ""}Choose the workspace you want to access:
          </p>
        </div>

        {error && (
          <div className="notice-error" role="alert">
            {error}
          </div>
        )}

        {validOrgs.length > 0 ? (
          <div className="org-list">
            {validOrgs.map((o) => {
              const isSelecting = selectingId === o.org_id;
              const isAdmin = o.role?.toLowerCase() === "admin";

              return (
                <div key={o.org_id} className="org-item-card">
                  <div className="org-item-meta">
                    <span className="org-item-name">{o.org_name}</span>
                    <span className={`badge ${isAdmin ? "badge-admin" : "badge-member"}`}>
                      {isAdmin ? "🛡️ Administrator" : "👤 Team Member"}
                    </span>
                  </div>
                  <button
                    onClick={() => pick(o)}
                    disabled={selectingId !== null}
                    className="btn-primary"
                  >
                    {isSelecting ? "Connecting…" : "Launch Workspace →"}
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <p className="muted">You are not currently assigned to any active organizations.</p>
          </div>
        )}

        {onLogout && (
          <div className="org-picker-footer">
            <button onClick={onLogout} className="btn-secondary text-sm">
              Sign In with Different Account
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
