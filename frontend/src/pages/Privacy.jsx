import React, { useState } from "react";
import { ShieldCheck, LockKeyhole, Building2, Trash2 } from "lucide-react";
import { PageTitle, Icon, Badge, DeleteDialog } from "../components";
export default function Privacy({ onDeleted }) {
  const [open, setOpen] = useState(false),
    [scope, setScope] = useState("current");
  return (
    <>
      <PageTitle
        eyebrow="PRIVACY & DATA"
        title="Your data. Your decision."
        description="Understand what is saved, who can see it, and how to remove it."
      />
      <div className="privacy-grid">
        <section className="panel privacy-card">
          <span className="metric-icon mint">
            <Icon icon={LockKeyhole} size={23} />
          </span>
          <h2>What stays with you</h2>
          <p>
            Your individual answers, personal report and one-week improvement
            plan are visible only to your account.
          </p>
          <p>
            We store the current assessment in each organization. Retaking
            replaces the previous assessment and plan.
          </p>
        </section>
        <section className="panel privacy-card">
          <span className="metric-icon lavender">
            <Icon icon={Building2} size={23} />
          </span>
          <h2>What leadership sees</h2>
          <p>
            Group results appear only for departments with at least five
            completed assessments. Exact risk counts require at least five
            people with the signal and five without it. Other counts are
            protected.
          </p>
          <p>
            There are no individual answer views or company-wide totals on the
            leadership dashboard.
          </p>
        </section>
      </div>
      <section className="panel data-details">
        <div className="panel-heading">
          <h2>Clear boundaries, honest limits</h2>
          <Icon icon={ShieldCheck} />
        </div>
        <ul>
          <li>
            In live mode, written answers go to the configured AI provider.
            Avoid personal or confidential information. Provider retention
            depends on that provider's agreement.
          </li>
          <li>
            Deleting data removes it from this application's database and future
            dashboard responses immediately. Open dashboard views refresh every
            two seconds.
          </li>
          <li>
            The app cannot erase screenshots or exports saved outside it. A
            five-person threshold alone cannot prevent every inference from
            observations over time.
          </li>
          <li>
            The pilot has no automated backup system. A production operator must
            define backup deletion and provider retention policies before using
            real employee data.
          </li>
        </ul>
      </section>
      <section className="panel deletion-panel">
        <div className="panel-heading">
          <div>
            <h2>Delete my diagnostic data</h2>
            <p>
              Remove only your own answers, report and improvement plan. Your
              account remains. Other employees' data stays unchanged, including
              when you are an organization admin.
            </p>
          </div>
          <span className="metric-icon blush">
            <Icon icon={Trash2} />
          </span>
        </div>
        <fieldset>
          <legend>Choose which of your assessments to delete</legend>
          <label className="scope-option">
            <input
              type="radio"
              name="scope"
              checked={scope === "current"}
              onChange={() => setScope("current")}
            />
            <span>
              <strong>My data in this organization</strong>
              <small>
                Delete only your diagnostic here. Your data in other
                organizations remains.
              </small>
            </span>
          </label>
          <label className="scope-option">
            <input
              type="radio"
              name="scope"
              checked={scope === "all"}
              onChange={() => setScope("all")}
            />
            <span>
              <strong>My data across all my organizations</strong>
              <small>
                Remove every assessment and plan belonging to your account.
              </small>
            </span>
          </label>
        </fieldset>
        <button className="button danger-outline" onClick={() => setOpen(true)}>
          <Icon icon={Trash2} size={16} />
          Delete my diagnostic data
        </button>
      </section>
      <DeleteDialog
        open={open}
        onClose={() => setOpen(false)}
        scope={scope}
        onDeleted={onDeleted}
      />
    </>
  );
}
