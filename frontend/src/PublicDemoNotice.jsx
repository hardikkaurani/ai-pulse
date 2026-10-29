import React from "react";

export default function PublicDemoNotice() {
  if (import.meta.env.VITE_PUBLIC_DEMO !== "true") return null;
  return (
    <aside className="public-demo-notice" aria-label="Public demo notice">
      <strong>Public reviewer demo — use fictional answers only.</strong>
      <p>
        These accounts are shared. Other visitors using the same account can
        view, change or delete its saved answers and plan. When Live AI is used,
        written answers go to Google for scoring.
      </p>
    </aside>
  );
}
