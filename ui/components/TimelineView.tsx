"use client";

import { useState } from "react";
import { formatDateTime } from "../lib/format";
import type { EventStream } from "../lib/workbench-data";

const ONTOLOGY_COLORS: Record<string, string> = {
  user_evidence: "#60a5fa",
  diegetic_event: "#c084fc",
  expressive_media: "#fb923c",
  inference: "#84d1a4",
  active_elicitation: "#facc15",
  proactive_support: "#818cf8",
  empirical_user_interaction: "#22d3ee",
  correction: "#f87171",
};

export function TimelineView({ subjectId, eventStreamData }: { subjectId: string; eventStreamData: EventStream }) {
  const [filter, setFilter] = useState("all");
  const events = eventStreamData.events;
  const classes = Array.from(new Set(events.map((event) => event.ontological_class)));
  const filtered = filter === "all" ? events : events.filter((event) => event.ontological_class === filter);

  return (
    <>
      <header className="page-header">
        <div className="page-eyebrow">Subject History · {subjectId}</div>
        <h1 className="page-title">Event Stream</h1>
        <div className="page-meta">
          <span>{events.length} Events Total</span>
          <span className="mono" style={{ opacity: 0.5 }}>|</span>
          <span style={{ color: "var(--ok)" }}>{events.filter((e) => e.decision === "delivered").length} Delivered</span>
          <span className="mono" style={{ opacity: 0.5 }}>|</span>
          <span style={{ color: "var(--block)" }}>{events.filter((e) => e.decision === "blocked").length} Blocked</span>
        </div>
      </header>

      <div className="wgrid">
        <article className="card col-12">
          <h2 className="card-label">Filter & Legend</h2>
          <div className="filter-bar">
            <span className="filter-label">Class</span>
            <button
              onClick={() => setFilter("all")}
              className={`filter-btn ${filter === "all" ? "active" : ""}`}
            >
              all
            </button>
            {classes.map((cls) => (
              <button
                key={cls}
                onClick={() => setFilter(cls)}
                className={`filter-btn ${filter === cls ? "active" : ""}`}
              >
                {cls.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </article>

        <article className="card col-12">
          <h2 className="card-label">EVENTS ({filtered.length})</h2>
          {filtered.length === 0 && <p className="empty-state">No events match the selected filter.</p>}
          <div className="data-list">
            {filtered.map((event) => (
              <div key={event.event_id} className="facet-row">
                <div className="facet-header" style={{ marginBottom: "8px" }}>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <span className="stream-chip" data-stream={event.ontological_class.includes("inference") ? "inference" : event.decision === "blocked" ? "blocked" : "evidence"}>
                      {event.ontological_class.replace(/_/g, " ")}
                    </span>
                    <span className="tag">{event.initiator}</span>
                    <span className="tag">{event.event_class}</span>
                  </div>
                  <time className="mono text-dim" style={{ fontSize: "11px" }}>
                    {formatDateTime(event.timestamp)}
                  </time>
                </div>
                <p className="prose" style={{ marginBottom: "12px" }}>
                  {event.content_preview || "[blocked by policy]"}
                </p>
                <div className="tag-row">
                  <span className="text-dim mono" style={{ fontSize: "10px" }}>risk: {event.risk_level}</span>
                  {event.has_media && <span className="tag">media</span>}
                  {event.has_user_response && <span className="tag">user_response</span>}
                  {event.has_correction && <span className="tag">correction</span>}
                  {event.has_boundary_risk && <span className="tag" style={{ color: "var(--block)" }}>boundary_risk</span>}
                  <span className="text-dim mono" style={{ fontSize: "10px", marginLeft: "auto" }}>ID: {event.event_id}</span>
                </div>
              </div>
            ))}
          </div>
        </article>
      </div>
      <footer className="page-footer">Generated {formatDateTime(eventStreamData.generated_at)} · {subjectId}</footer>
    </>
  );
}
