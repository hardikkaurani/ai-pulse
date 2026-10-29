import React, { useState } from "react";
import {
  ArrowRight,
  ShieldCheck,
  Sprout,
  ChartNoAxesCombined,
  Check,
} from "lucide-react";
import { api, setToken } from "../api";
import { Brand, Icon, ErrorMessage, Badge } from "../components";
import PublicDemoNotice from "../PublicDemoNotice";
export default function Login({ onDone, notice }) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const s = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(s.token);
      onDone(s);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function demo(value) {
    setEmail(value);
    setPassword("pulse123");
    setError("");
  }
  return (
    <div className="login-layout">
      <section className="login-story">
        <Brand light />
        <div className="story-content">
          <p className="eyebrow">UNDERSTAND. PRACTISE. PROGRESS.</p>
          <h1>
            Better AI habits.
            <br />
            <span>Stronger teams.</span>
          </h1>
          <p className="story-copy">
            Understand how you use AI today. Find a practical next step. Build
            confidence, one week at a time.
          </p>
          <div className="story-visual" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="visual-card">
              <span className="visual-card-icon">
                <Icon icon={Sprout} size={26} />
              </span>
              <span>
                <small>YOUR NEXT SMALL STEP</small>
                <strong>Build your three-check habit</strong>
                <em>
                  <Icon icon={Check} size={14} /> A little practice. A lasting
                  change.
                </em>
              </span>
            </div>
          </div>
          <div className="story-benefits">
            <span>
              <Icon icon={ShieldCheck} />
              Private answers
            </span>
            <span>
              <Icon icon={ChartNoAxesCombined} />
              Clear insights
            </span>
            <span>
              <Icon icon={Sprout} />
              Practical growth
            </span>
          </div>
        </div>
        <p className="story-footer">
          Built for people. Designed for responsible AI.
        </p>
      </section>
      <section className="login-form-area">
        <div className="login-form-wrap">
          <PublicDemoNotice />
          <Badge tone="green">AI MATURITY WORKSPACE</Badge>
          <h2>Welcome to AI Pulse</h2>
          <p className="subtitle">Sign in to your organization's workspace.</p>
          {notice && (
            <div className="notice" role="status">
              {notice}
            </div>
          )}
          <form onSubmit={submit}>
            <label>
              Email address
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                maxLength={200}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                maxLength={256}
              />
            </label>
            {error && <ErrorMessage message={error} />}
            <button className="button primary wide" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
              <Icon icon={ArrowRight} />
            </button>
          </form>
          <div className="demo-box">
            <p className="eyebrow">EXPLORE THE SYNTHETIC DEMO</p>
            <p>Choose a perspective. No real employee data.</p>
            <div className="demo-options">
              <button onClick={() => demo("asha@northwind.test")}>
                <span className="demo-initial">A</span>
                <span>
                  <strong>Leadership</strong>
                  <small>Asha · Northwind</small>
                </span>
                <Icon icon={ArrowRight} size={16} />
              </button>
              <button onClick={() => demo("priya@northwind.test")}>
                <span className="demo-initial mint">P</span>
                <span>
                  <strong>Employee</strong>
                  <small>Priya · Support</small>
                </span>
                <Icon icon={ArrowRight} size={16} />
              </button>
            </div>
            <button
              className="text-button demo-consultant"
              onClick={() => demo("ravi@consult.test")}
            >
              Try the multi-company consultant
            </button>
          </div>
          <p className="login-footnote">
            <Icon icon={ShieldCheck} size={15} />
            Your answers are private. Company dashboards protect small groups.
          </p>
        </div>
      </section>
    </div>
  );
}
