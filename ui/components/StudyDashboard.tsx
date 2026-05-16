"use client";

import Link from "next/link";
import { useState } from "react";
import { formatDate, formatDateTime } from "../lib/format";
import type { StudyOverview, SubjectRow } from "../lib/workbench-data";

function StatusMarker({ status }: { status: SubjectRow["status"] }) {
  return <span className="state-marker" data-state={status}>{status}</span>;
}

function RiskBadge({ risk }: { risk: SubjectRow["risk"] }) {
  return <span className="risk-badge" data-risk={risk}>{risk}</span>;
}

function HermesCell({ profileId }: { profileId: string | null | undefined }) {
  if (!profileId) {
    return <span className="stream-chip" data-stream="blocked">provisioning failed</span>;
  }
  return (
    <span className="mono" style={{ fontSize: "11.5px", fontVariantNumeric: "tabular-nums" }}>
      {profileId}
    </span>
  );
}

function ReviewCell({ pending }: { pending: boolean }) {
  if (pending) return <span className="stream-chip" data-stream="pending">queued</span>;
  return <span className="text-dim">—</span>;
}

/* ─────────────────────────────────────────────────────────────────────────── */

export function StudyDashboard({ studyOverviewData }: { studyOverviewData: StudyOverview }) {
  const [conditionFilter, setConditionFilter] = useState("all");
  const [statusFilter, setStatusFilter]       = useState("all");

  const subjects   = studyOverviewData.subject_registry;
  const conditions = ["all", ...Array.from(new Set(subjects.map((s) => s.condition)))];
  const statuses   = ["all", "active", "paused", "archived"];

  const filtered = subjects.filter(
    (s) =>
      (conditionFilter === "all" || s.condition === conditionFilter) &&
      (statusFilter === "all" || s.status === statusFilter),
  );

  const validation = studyOverviewData.last_validation_run
    ? formatDateTime(studyOverviewData.last_validation_run)
    : "never";

  return (
    <>
      {/* Page header */}
      <header className="page-header">
        <div className="page-eyebrow">Study Monitoring</div>
        <h1 className="page-title">{studyOverviewData.study_id}</h1>
        <div className="page-meta">
          <span>Protocol {studyOverviewData.protocol_version}</span>
          <span className="mono" style={{ fontSize: "10px", opacity: 0.5 }}>|</span>
          <span>{subjects.length} Subjects Registered</span>
          <span className="mono" style={{ fontSize: "10px", opacity: 0.5 }}>|</span>
          <span>Validated {validation}</span>
        </div>
      </header>

      {/* Stat bar */}
      <div className="stat-bar" role="region" aria-label="Study Metrics">
        {[
          { key: "Active Subjects", val: studyOverviewData.subjects_active,    state: studyOverviewData.subjects_active    > 0 ? "ok"   : undefined },
          { key: "Paused Subjects", val: studyOverviewData.subjects_paused,    state: studyOverviewData.subjects_paused    > 0 ? "warn" : undefined },
          { key: "Archived",        val: studyOverviewData.subjects_archived,  state: undefined },
          { key: "Active Risks",    val: studyOverviewData.active_risk_alerts, state: studyOverviewData.active_risk_alerts > 0 ? "fault": undefined },
          { key: "Pending Review",  val: studyOverviewData.pending_reviews,    state: studyOverviewData.pending_reviews    > 0 ? "warn" : undefined },
        ].map((item) => (
          <div key={item.key} className="stat-item">
            <div className="stat-key">{item.key}</div>
            <div
              className="stat-val"
              data-ok={item.state === "ok" || undefined}
              data-warn={item.state === "warn" || undefined}
              data-fault={item.state === "fault" || undefined}
            >
              {item.val}
            </div>
          </div>
        ))}
      </div>

      {/* Subject registry */}
      <div className="wgrid">
        <article className="card col-12">
          <h2 className="card-label">Subject Registry</h2>

          {/* Filter bar */}
          <div className="filter-bar" role="group" aria-label="Filter registry">
            <span className="filter-label">Condition</span>
            {conditions.map((c) => (
              <button
                key={c}
                type="button"
                className={`filter-btn ${conditionFilter === c ? "active" : ""}`}
                onClick={() => setConditionFilter(c)}
              >
                {c.replace(/_/g, " ")}
              </button>
            ))}

            <div style={{ flex: 1 }} />

            <span className="filter-label">Status</span>
            {statuses.map((s) => (
              <button
                key={s}
                type="button"
                className={`filter-btn ${statusFilter === s ? "active" : ""}`}
                onClick={() => setStatusFilter(s)}
              >
                {s}
              </button>
            ))}
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Subject ID</th>
                <th scope="col">Condition</th>
                <th scope="col">Status</th>
                <th scope="col">Risk</th>
                <th scope="col">Hermes Profile</th>
                <th scope="col">Interaction</th>
                <th scope="col">Review</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-state">
                    No subjects match the current filters.
                  </td>
                </tr>
              ) : (
                filtered.map((subject) => (
                  <tr key={subject.subject_id}>
                    <td>
                      <Link
                        href={`/workbench/subjects/${subject.subject_id.replace("-", "_")}`}
                        className="subject-link"
                      >
                        {subject.subject_id}
                      </Link>
                    </td>
                    <td>{subject.condition.replace(/_/g, " ")}</td>
                    <td><StatusMarker status={subject.status} /></td>
                    <td><RiskBadge risk={subject.risk} /></td>
                    <td><HermesCell profileId={subject.hermes_profile_id} /></td>
                    <td className="mono" style={{ fontSize: "11px" }}>
                      {subject.last_user_interaction_at ? formatDate(subject.last_user_interaction_at) : "—"}
                    </td>
                    <td><ReviewCell pending={subject.pending_review} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </article>
      </div>

      <footer className="page-footer">
        {studyOverviewData.study_id} · {subjects.length} subjects
      </footer>
    </>
  );
}
