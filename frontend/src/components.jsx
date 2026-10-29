import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  Check,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";
import { api } from "./api";

export const Icon = ({ icon: Component, size = 18, ...props }) => (
  <Component size={size} strokeWidth={1.8} aria-hidden="true" {...props} />
);
export function Brand({ light = false }) {
  return (
    <div className={"brand " + (light ? "brand-light" : "")}>
      <span className="brand-mark">
        <Icon icon={Activity} size={23} />
      </span>
      <span>
        AI Pulse<span className="brand-by">by Elevante AI</span>
      </span>
    </div>
  );
}
export function Badge({ children, tone = "neutral" }) {
  return <span className={"badge " + tone}>{children}</span>;
}
export function ErrorMessage({ message, retry }) {
  return (
    <div className="notice error" role="alert">
      <Icon icon={AlertCircle} />
      <div>
        <strong>Something needs your attention</strong>
        <p>{message}</p>
        {retry && (
          <button className="text-button" onClick={retry}>
            Try again <Icon icon={RefreshCw} size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <span className="spinner" /> Getting your workspace ready…
    </div>
  );
}
export function Empty({ title, children, action, onAction }) {
  return (
    <div className="empty panel">
      <span className="empty-icon">
        <Icon icon={Activity} size={28} />
      </span>
      <h2>{title}</h2>
      <p>{children}</p>
      {action && (
        <button className="button primary" onClick={onAction}>
          {action}
          <Icon icon={ArrowRight} />
        </button>
      )}
    </div>
  );
}
export function PageTitle({ eyebrow, title, description, children }) {
  return (
    <div className="page-title">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="subtitle">{description}</p>
      </div>
      {children}
    </div>
  );
}
export function PrivacyNote({ children }) {
  return (
    <div className="privacy-note">
      <Icon icon={ShieldCheck} size={17} />
      <span>{children}</span>
    </div>
  );
}
export function useRemote(path, interval = 0) {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [version, setVersion] = useState(0);
  const reload = () => setVersion((v) => v + 1);
  useEffect(() => {
    let active = true,
      running = false;
    const update = async () => {
      if (running) return;
      running = true;
      try {
        const next = await api(path);
        if (active) {
          setData(next);
          setError("");
        }
      } catch (e) {
        if (active) {
          setError(e.message);
          setData(null);
        }
      } finally {
        running = false;
      }
    };
    update();
    const timer = interval
      ? setInterval(() => {
          if (document.visibilityState === "visible") update();
        }, interval)
      : null;
    const focus = () => update();
    window.addEventListener("focus", focus);
    return () => {
      active = false;
      if (timer) clearInterval(timer);
      window.removeEventListener("focus", focus);
    };
  }, [path, interval, version]);
  return { data, setData, error, reload };
}
export function DeleteDialog({ open, onClose, scope, onDeleted }) {
  const ref = useRef(null);
  const [confirmation, setConfirmation] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setConfirmation("");
      setError("");
      ref.current.showModal();
    } else if (ref.current.open) ref.current.close();
  }, [open]);
  async function remove(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/reports/me?scope=" + scope, { method: "DELETE" });
      onDeleted();
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <dialog
      ref={ref}
      aria-labelledby="delete-dialog-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
      className="delete-dialog"
    >
      <form onSubmit={remove}>
        <span className="empty-icon danger">
          <Icon icon={LockKeyhole} size={26} />
        </span>
        <h2 id="delete-dialog-title">Delete your diagnostic data?</h2>
        <p>
          This permanently removes your answers, report and improvement plan{" "}
          {scope === "all"
            ? "across all your organizations"
            : "in this organization"}
          . Your account remains, and you can take a new assessment.
        </p>
        <p>
          This affects only your own diagnostic data, even if you are an admin.
          Other employees' assessments stay unchanged.
        </p>
        <p>
          Future dashboard results will exclude this assessment. We cannot erase
          screenshots someone previously saved.
        </p>
        <label>
          Type DELETE to confirm
          <input
            autoFocus
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            autoComplete="off"
          />
        </label>
        {error && <ErrorMessage message={error} />}
        <div className="button-row">
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={onClose}
          >
            Keep my data
          </button>
          <button
            className="button destructive"
            disabled={busy || confirmation !== "DELETE"}
          >
            {busy ? "Deleting…" : "Delete my data"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
