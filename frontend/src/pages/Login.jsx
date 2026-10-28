import React, { useState } from "react";
import { api, setToken } from "../api.js";

export default function Login({ onDone }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const authData = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });
      setToken(authData.token);
      onDone(authData);
    } catch (err) {
      setError(err.message || "Invalid email or password. Please verify your credentials.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-card-wrap">
      <form className="card auth-card" onSubmit={submit}>
        <div className="auth-header">
          <div className="auth-logo">⚡</div>
          <h2>Sign in to AI Pulse</h2>
          <p className="muted">Enter your organizational credentials to continue</p>
        </div>

        {error && (
          <div className="notice-error" role="alert">
            {error}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="login-email">Work Email</label>
          <input
            id="login-email"
            type="email"
            className="text-input"
            placeholder="e.g. alex@northwind.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
            autoFocus
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="login-password">Password</label>
          <input
            id="login-password"
            type="password"
            className="text-input"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            required
          />
        </div>

        <button
          type="submit"
          className="btn-primary btn-block"
          disabled={submitting}
        >
          {submitting ? "Signing in…" : "Sign In"}
        </button>
      </form>
    </div>
  );
}
