import React, { useState } from "react";
import Login from "./pages/Login.jsx";
import OrgPicker from "./pages/OrgPicker.jsx";
import Diagnostic from "./pages/Diagnostic.jsx";
import Report from "./pages/Report.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import { clearToken } from "./api.js";

export default function App() {
  const [step, setStep] = useState("login");
  const [session, setSession] = useState(null);
  const [org, setOrg] = useState(null);

  function handleLogout() {
    clearToken();
    setSession(null);
    setOrg(null);
    setStep("login");
  }

  function handleSwitchOrg() {
    setOrg(null);
    setStep("org");
  }

  const isWide = step === "dashboard";

  return (
    <div className="app-shell">
      {/* Top Application Navbar */}
      <header className="app-navbar">
        <div className="nav-inner">
          <div
            className="nav-brand"
            role="button"
            tabIndex={0}
            onClick={() => session && org && setStep(org.role === "admin" ? "dashboard" : "report")}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && session && org) {
                setStep(org.role === "admin" ? "dashboard" : "report");
              }
            }}
          >
            <span className="brand-icon">⚡</span>
            <div className="brand-title">
              <span className="brand-name">AI Pulse</span>
              <span className="brand-tag">Enterprise Readiness</span>
            </div>
          </div>

          {session && (
            <div className="nav-controls">
              {org && (
                <nav className="nav-links">
                  {org.role === "admin" && (
                    <button
                      className={`nav-link-btn ${step === "dashboard" ? "active" : ""}`}
                      onClick={() => setStep("dashboard")}
                    >
                      Leadership Dashboard
                    </button>
                  )}
                  <button
                    className={`nav-link-btn ${step === "diagnostic" ? "active" : ""}`}
                    onClick={() => setStep("diagnostic")}
                  >
                    Take Diagnostic
                  </button>
                  <button
                    className={`nav-link-btn ${step === "report" ? "active" : ""}`}
                    onClick={() => setStep("report")}
                  >
                    My Report
                  </button>
                </nav>
              )}

              <div className="nav-user-meta">
                <span className="user-name-pill" title={session.name || "Logged in"}>
                  👤 {session.name || "User"}
                </span>
                {org && (
                  <span className="org-badge-pill" title={`Organization: ${org.org_name}`}>
                    🏢 {org.org_name} <span className="role-sub">({org.role})</span>
                  </span>
                )}
                {org && session.organizations?.length > 1 && (
                  <button className="nav-btn-secondary" onClick={handleSwitchOrg} title="Switch active organization">
                    Switch Org
                  </button>
                )}
                <button className="nav-btn-ghost" onClick={handleLogout} title="Log out of AI Pulse">
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className={`app-main ${isWide ? "wrap-wide" : "wrap-standard"}`}>
        {step === "login" && (
          <Login
            onDone={(s) => {
              setSession(s);
              setStep("org");
            }}
          />
        )}

        {step === "org" && session && (
          <OrgPicker
            orgs={session.organizations || []}
            userName={session.name}
            onPick={(o) => {
              setOrg(o);
              setStep(o.role === "admin" ? "dashboard" : "diagnostic");
            }}
            onLogout={handleLogout}
          />
        )}

        {step === "diagnostic" && (
          <Diagnostic
            onDone={() => setStep("report")}
            onCancel={org?.role === "admin" ? () => setStep("dashboard") : null}
          />
        )}

        {step === "report" && (
          <Report
            onRetake={() => setStep("diagnostic")}
            onViewDashboard={org?.role === "admin" ? () => setStep("dashboard") : null}
          />
        )}

        {step === "dashboard" && org && (
          <Dashboard
            org={org}
            onNavigate={(target) => setStep(target)}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <div className="footer-inner">
          <span>AI Pulse Assessment Platform</span>
          <span className="footer-dot">•</span>
          <span>Privacy-Preserving Analytics (k &ge; 5)</span>
          <span className="footer-dot">•</span>
          <span>Role-Based Access Control</span>
        </div>
      </footer>
    </div>
  );
}
