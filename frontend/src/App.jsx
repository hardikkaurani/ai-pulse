import React, { useEffect, useState } from "react";
import {
  LayoutDashboard,
  ClipboardList,
  ChartNoAxesCombined,
  Sprout,
  ShieldCheck,
  LogOut,
  ArrowUpRight,
  Building2,
  Menu,
  X,
} from "lucide-react";
import { api, getToken, setToken } from "./api";
import { Brand, Icon, Badge, Loading, ErrorMessage } from "./components";
import Login from "./pages/Login";
import OrgPicker from "./pages/OrgPicker";
import Dashboard from "./pages/Dashboard";
import Diagnostic from "./pages/Diagnostic";
import Report from "./pages/Report";
import Plan from "./pages/Plan";
import Privacy from "./pages/Privacy";
import PublicDemoNotice from "./PublicDemoNotice";

const labels = {
  overview: "Team overview",
  report: "My report",
  diagnostic: "Assessment",
  plan: "My improvement plan",
  privacy: "Privacy & data",
};
export default function App() {
  const [session, setSession] = useState(null),
    [org, setOrg] = useState(null),
    [loading, setLoading] = useState(true);
  const [startupError, setStartupError] = useState(""),
    [startupAttempt, setStartupAttempt] = useState(0);
  const [page, setPage] = useState("report"),
    [notice, setNotice] = useState(""),
    [mobile, setMobile] = useState(false),
    [switching, setSwitching] = useState(false);
  function signout(message = "") {
    setToken(null);
    sessionStorage.removeItem("pulse-org");
    setOrg(null);
    setSession(null);
    setNotice(message);
    setStartupError("");
  }
  useEffect(() => {
    let active = true;
    setLoading(true);
    setStartupError("");
    const expired = () =>
      signout("Your session has ended. Please sign in again.");
    window.addEventListener("pulse-session-expired", expired);
    if (!getToken()) {
      setLoading(false);
      return () => window.removeEventListener("pulse-session-expired", expired);
    }
    api("/auth/me")
      .then(async (s) => {
        if (!active) return;
        const previous = s.organizations.find(
          (o) => String(o.org_id) === sessionStorage.getItem("pulse-org"),
        );
        if (previous) {
          const selected = await api("/auth/select-org", {
            method: "POST",
            body: JSON.stringify({ org_id: previous.org_id }),
          });
          if (!active) return;
          setToken(selected.token);
          setOrg(previous);
          setPage(previous.role === "admin" ? "overview" : "report");
        }
        setSession(s);
      })
      .catch((e) => {
        if (!active) return;
        if (e.status === 401 || e.status === 403) signout(e.message);
        else setStartupError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      window.removeEventListener("pulse-session-expired", expired);
    };
  }, [startupAttempt]);
  function navigate(next) {
    setPage(next);
    setMobile(false);
    setNotice("");
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  async function chooseOrg(next) {
    setSwitching(true);
    setNotice("");
    try {
      const selected = await api("/auth/select-org", {
        method: "POST",
        body: JSON.stringify({ org_id: next.org_id }),
      });
      setToken(selected.token);
      sessionStorage.setItem("pulse-org", String(next.org_id));
      setOrg(next);
      navigate(next.role === "admin" ? "overview" : "report");
    } catch (e) {
      setNotice(e.message);
    } finally {
      setSwitching(false);
    }
  }
  if (loading)
    return (
      <div className="boot">
        <Brand />
        <Loading />
      </div>
    );
  if (startupError)
    return (
      <div className="org-page">
        <header>
          <Brand />
          <button className="button quiet" onClick={() => signout()}>
            Sign out
          </button>
        </header>
        <div className="org-content">
          <h1>Reconnect to your workspace</h1>
          <p className="subtitle">
            We couldn't load your workspace. Try again when the connection is
            back.
          </p>
          <ErrorMessage
            message={startupError}
            retry={() => setStartupAttempt((attempt) => attempt + 1)}
          />
        </div>
      </div>
    );
  if (!session)
    return (
      <Login
        notice={notice}
        onDone={(s) => {
          setSession(s);
          setNotice("");
        }}
      />
    );
  if (!org)
    return (
      <OrgPicker
        session={session}
        onPick={chooseOrg}
        busy={switching}
        error={notice}
        onLogout={() => signout()}
      />
    );
  const links = [
    ...(org.role === "admin" ? [["overview", LayoutDashboard]] : []),
    ["report", ChartNoAxesCombined],
    ["diagnostic", ClipboardList],
    ["plan", Sprout],
    ["privacy", ShieldCheck],
  ];
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className={"sidebar " + (mobile ? "mobile-open" : "")}>
        <div className="sidebar-brand">
          <Brand light />
          <button
            className="icon-button mobile-only"
            aria-label="Close navigation"
            onClick={() => setMobile(false)}
          >
            <Icon icon={X} />
          </button>
        </div>
        <p className="nav-label">YOUR WORKSPACE</p>
        <nav aria-label="Main navigation">
          {links.map(([key, icon]) => (
            <button
              key={key}
              className={"nav-item " + (page === key ? "active" : "")}
              aria-current={page === key ? "page" : undefined}
              onClick={() => navigate(key)}
            >
              <Icon icon={icon} />
              {labels[key]}
              {key === "plan" && <span className="new-tag">NEW</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="trust-card">
            <Icon icon={ShieldCheck} size={21} />
            <strong>Private by design</strong>
            <p>
              Your answers are yours. Leadership sees protected group results.
            </p>
            <button onClick={() => navigate("privacy")}>
              How your data is used <Icon icon={ArrowUpRight} size={14} />
            </button>
          </div>
          <div className="user-row">
            <span className="avatar">
              {session.name
                .split(" ")
                .map((n) => n[0])
                .slice(0, 2)
                .join("")}
            </span>
            <span>
              <strong>{session.name}</strong>
              <small>
                {org.role === "admin" ? "Organization admin" : "Employee"}
              </small>
            </span>
            <button
              className="icon-button"
              title="Sign out"
              aria-label="Sign out"
              onClick={() => signout()}
            >
              <Icon icon={LogOut} size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-only"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <Icon icon={Menu} />
            </button>
            <Icon icon={Building2} />
            <label className="sr-only" htmlFor="organization">
              Current organization
            </label>
            <select
              id="organization"
              value={org.org_id}
              disabled={switching}
              onChange={(e) =>
                chooseOrg(
                  session.organizations.find(
                    (o) => o.org_id === Number(e.target.value),
                  ),
                )
              }
            >
              {session.organizations.map((o) => (
                <option key={o.org_id} value={o.org_id}>
                  {o.org_name}
                </option>
              ))}
            </select>
          </div>
          <div className="topbar-right">
            <span className="status-dot" />
            Workspace active
            <Badge tone={session.ai_mode === "mock" ? "amber" : "green"}>
              {session.ai_mode === "mock" ? "Demo scoring" : "Live AI"}
            </Badge>
          </div>
        </header>
        <main id="main" className="main" key={org.org_id}>
          <PublicDemoNotice />
          {notice && (
            <div role="status" className="notice">
              {notice}
            </div>
          )}
          {switching ? (
            <Loading />
          ) : (
            <>
              {page === "overview" && org.role === "admin" && <Dashboard />}
              {page === "report" && <Report onNavigate={navigate} />}
              {page === "diagnostic" && (
                <Diagnostic
                  onDone={() => navigate("report")}
                  onCancel={() => navigate("report")}
                  mode={session.ai_mode}
                />
              )}
              {page === "plan" && <Plan onNavigate={navigate} />}
              {page === "privacy" && (
                <Privacy
                  onDeleted={() => {
                    setPage("report");
                    setNotice(
                      "Your diagnostic data was deleted. You can start again whenever you're ready.",
                    );
                  }}
                />
              )}
            </>
          )}
        </main>
        <footer className="workspace-footer">
          <span>
            AI Pulse <span className="footer-separator">/</span> A clearer path
            to responsible AI.
          </span>
          <span>Client pilot · v1.0</span>
        </footer>
      </div>
    </div>
  );
}
