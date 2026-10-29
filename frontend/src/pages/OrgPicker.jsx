import React from "react";
import { ArrowRight, Building2, LogOut } from "lucide-react";
import { Brand, Icon, Badge, ErrorMessage } from "../components";
import PublicDemoNotice from "../PublicDemoNotice";
export default function OrgPicker({ session, onPick, busy, error, onLogout }) {
  return (
    <div className="org-page">
      <header>
        <Brand />
        <button className="button quiet" onClick={onLogout}>
          <Icon icon={LogOut} />
          Sign out
        </button>
      </header>
      <div className="org-content">
        <PublicDemoNotice />
        <p className="eyebrow">ONE ACCOUNT. SEPARATE WORKSPACES.</p>
        <h1>Where are we working today?</h1>
        <p className="subtitle">
          Welcome, {session.name.split(" ")[0]}. Your role and data stay within
          the organization you choose.
        </p>
        {error && <ErrorMessage message={error} />}
        <div className="org-grid">
          {session.organizations.map((org) => (
            <button
              className="org-card panel"
              key={org.org_id}
              disabled={busy}
              onClick={() => onPick(org)}
            >
              <span className="org-icon">
                <Icon icon={Building2} size={25} />
              </span>
              <Badge tone={org.role === "admin" ? "purple" : "green"}>
                {org.role === "admin" ? "Admin" : "Employee"}
              </Badge>
              <h2>{org.org_name}</h2>
              <p>
                {org.role === "admin"
                  ? "Explore protected team insights"
                  : "Your assessment and improvement plan"}
              </p>
              <span className="org-cta">
                {busy ? "Opening workspace…" : "Open workspace"}
                <Icon icon={ArrowRight} />
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
