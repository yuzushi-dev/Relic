"use client";

import { useState } from "react";
import { formatDateTime } from "../lib/format";
import type { EventStream } from "../lib/workbench-data";

type ValidStream = "evidence" | "inference" | "pending" | "approved" | "blocked" | "gumi" | "runtime" | "correction" | "neutral";

function eventStream(event: EventStream["events"][number]): ValidStream {
  if (event.decision === "blocked") return "blocked";
  switch (event.event_class) {
    case "gumi_initiative": case "checkin": return "gumi";
    case "system":                          return "runtime";
    case "researcher_action":               return "evidence";
    case "user_message":                    return "evidence";
    default:
      if (event.ontological_class.includes("inference"))  return "inference";
      if (event.ontological_class.includes("correction")) return "correction";
      return "neutral";
  }
}

export function TimelineView({ subjectId, eventStreamData }: { subjectId: string; eventStreamData: EventStream }) {
  const [filter, setFilter] = useState("all");
  const events = eventStreamData.events;
  const classes = Array.from(new Set(events.map((e) => e.event_class))).sort();
  const filtered = filter === "all" ? events : events.filter((e) => e.event_class === filter);

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
          {eventStreamData.stream === "live" && (
            <>
              <span className="mono" style={{ opacity: 0.5 }}>|</span>
              <span
                className="state-marker"
                data-state="active"
                aria-label="live stream"
                style={{ fontSize: "11px" }}
              >
                live
              </span>
            </>
          )}
        </div>
      </header>

      <div className="wgrid">
        <article className="card col-12">
          <h2 className="card-label">Filter by Class</h2>
          <div className="filter-bar" role="group" aria-label="Filter events by class">
            <span className="filter-label">Class</span>
            <button
              type="button"
              onClick={() => setFilter("all")}
              className={`filter-btn ${filter === "all" ? "active" : ""}`}
              aria-pressed={filter === "all"}
            >
              all
            </button>
            {classes.map((cls) => (
              <button
                key={cls}
                type="button"
                onClick={() => setFilter(cls)}
                className={`filter-btn ${filter === cls ? "active" : ""}`}
                aria-pressed={filter === cls}
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
                    <span className="stream-chip" data-stream={eventStream(event)}>
                      {event.ontological_class.replace(/_/g, " ")}
                    </span>
                    <span className="tag">{event.initiator}</span>
                    <span className="tag">{event.event_class.replace(/_/g, " ")}</span>
                  </div>
                  <time className="mono text-dim" style={{ fontSize: "11px" }}>
                    {formatDateTime(event.timestamp)}
                  </time>
                </div>
                <p
                  className="prose"
                  style={{ marginBottom: "12px" }}
                  title={event.content_preview || undefined}
                >
                  {event.content_preview || "[blocked by policy]"}
                </p>
                <div className="tag-row">
                  {event.risk_level !== "none" && (
                    <span className="text-dim mono" style={{ fontSize: "10px", color: event.risk_level === "high" ? "var(--block)" : event.risk_level === "medium" ? "var(--block)" : "var(--pend)" }}>
                      risk: {event.risk_level}
                    </span>
                  )}
                  {event.has_media && <span className="tag">media</span>}
                  {event.has_user_response && <span className="tag">user_response</span>}
                  {event.has_correction && <span className="tag">correction</span>}
                  {event.has_boundary_risk && <span className="tag" style={{ color: "var(--block)" }}>boundary_risk</span>}
                  <span className="text-dim mono" style={{ fontSize: "10px", marginLeft: "auto" }}>
                    {event.event_id.startsWith("chr_") ? event.event_id.slice(4, 16) : event.event_id.slice(0, 12)}
                  </span>
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
