"use client";

import Link from "next/link";
import { useState } from "react";
import { formatDate, formatDateTime } from "../lib/format";
import type { StudyOverview, SubjectRow } from "../lib/workbench-data";

function StatusBadge({ status }: { status: SubjectRow["status"] }) {
  const map: Record<string, string> = {
    active: "#84d1a4",
    paused: "#fbbf24",
    archived: "#a69691",
  };
  const color = map[status] ?? map.archived;

  return (
    <span
      className="status-chip"
      style={{
        borderColor: `color-mix(in srgb, ${color} 28%, transparent)`,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        color,
      }}
    >
      <span className="status-dot" style={{ background: color, boxShadow: `0 0 10px ${color}` }} />
      {status}
    </span>
  );
}

function RiskBadge({ risk }: { risk: SubjectRow["risk"] }) {
  const map: Record<string, string> = {
    none: "#84d1a4",
    low: "#60a5fa",
    medium: "#fbbf24",
    high: "#f87171",
  };
  const color = map[risk] ?? "#a69691";

  return (
    <span
      className="token"
      style={{
        borderColor: `color-mix(in srgb, ${color} 40%, transparent)`,
        background: `color-mix(in srgb, ${color} 14%, transparent)`,
        color,
      }}
    >
      {risk}
    </span>
  );
}

export function StudyDashboard({ studyOverviewData }: { studyOverviewData: StudyOverview }) {
  const [conditionFilter, setConditionFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const subjects = studyOverviewData.subject_registry;
  const filtered = subjects.filter((subject) => {
    return (
      (conditionFilter === "all" || subject.condition === conditionFilter) &&
      (statusFilter === "all" || subject.status === statusFilter)
    );
  });

  const validation = studyOverviewData.last_validation_run
    ? formatDateTime(studyOverviewData.last_validation_run)
    : "never";

  return (
    <>
      <section className="hero">
        <div className="hero-grid">
          <div>
            <div className="eyebrow">Study dashboard</div>
            <h1>{studyOverviewData.study_id}</h1>
            <p className="lede">
              Protocol {studyOverviewData.protocol_version} · {subjects.length} registered subjects · validated {validation}.
            </p>
          </div>
          <aside className="hero-side">
            <div className="eyebrow">Study totals</div>
            <div className="token-row" style={{ marginTop: "14px" }}>
              <span className="token active-token">{studyOverviewData.subjects_active} active</span>
              <span className="token">{studyOverviewData.pending_reviews} pending review</span>
              <span className="token">{studyOverviewData.hermes_provisioning_failures} provisioning failure</span>
            </div>
          </aside>
        </div>

        <div className="summary-strip">
          {[
            { label: "Active", value: studyOverviewData.subjects_active, color: "#84d1a4" },
            { label: "Paused", value: studyOverviewData.subjects_paused, color: "#fbbf24" },
            { label: "Archived", value: studyOverviewData.subjects_archived, color: "#a69691" },
            { label: "Risk Alerts", value: studyOverviewData.active_risk_alerts, color: "#f87171" },
          ].map((stat) => (
            <div key={stat.label} className="strip-item">
              <div className="strip-label">{stat.label}</div>
              <div className="strip-value" style={{ color: stat.color }}>
                {stat.value}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="workbench-grid">
        <article className="card span-12">
          <div className="card-title">Subject Registry</div>
          <div className="control-row">
            <span className="control-label">Condition</span>
            {["all", "control", "treatment_a", "treatment_b"].map((condition) => (
              <button
                key={condition}
                className={`token token-button ${conditionFilter === condition ? "active-token" : ""}`}
                type="button"
                onClick={() => setConditionFilter(condition)}
              >
                {condition.replace(/_/g, " ")}
              </button>
            ))}
            <span className="control-label">Status</span>
            {["all", "active", "paused", "archived"].map((status) => (
              <button
                key={status}
                className={`token token-button ${statusFilter === status ? "active-token" : ""}`}
                type="button"
                onClick={() => setStatusFilter(status)}
              >
                {status}
              </button>
            ))}
          </div>

          <table className="dense-table">
            <thead>
              <tr>
                {["Subject", "Condition", "Status", "Risk", "Hermes Profile", "Last Interaction", "Review"].map((heading) => (
                  <th key={heading}>{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="status-text">
                    No live subjects found. Create one with `relic subject create` or set RELIC_HOME for the live container.
                  </td>
                </tr>
              )}
              {filtered.map((subject) => (
                <tr key={subject.subject_id}>
                  <td>
                    <Link
                      href={`/workbench/subjects/${subject.subject_id.replace("-", "_")}`}
                      style={{ color: "var(--red-soft)", textDecoration: "none", fontFamily: "var(--mono)", fontSize: "12px" }}
                    >
                      {subject.subject_id}
                    </Link>
                  </td>
                  <td className="status-text">{subject.condition}</td>
                  <td>
                    <StatusBadge status={subject.status} />
                  </td>
                  <td>
                    <RiskBadge risk={subject.risk} />
                  </td>
                  <td>
                    {subject.hermes_profile_id ? (
                      <span className="status-text" style={{ color: "#84d1a4" }}>
                        {subject.hermes_profile_id}
                      </span>
                    ) : (
                      <span className="token" style={{ color: "var(--red-soft)" }}>
                        provisioning failed
                      </span>
                    )}
                  </td>
                  <td className="status-text">
                    {subject.last_user_interaction_at
                      ? formatDate(subject.last_user_interaction_at)
                      : "--"}
                  </td>
                  <td>
                    {subject.pending_review ? (
                      <span className="token active-token">queued</span>
                    ) : (
                      <span className="status-text">clear</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      </section>

      <div className="footer">Study dashboard · {studyOverviewData.study_id}</div>
    </>
  );
}
