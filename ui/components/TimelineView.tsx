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
      <section className="hero">
        <div style={{ position: "relative", zIndex: 1 }}>
          <div className="eyebrow">EVENT TIMELINE · {subjectId}</div>
          <h1>Event Stream</h1>
          <p className="lede">
            {events.length} events · {events.filter((event) => event.decision === "delivered").length} delivered ·{" "}
            {events.filter((event) => event.decision === "blocked").length} blocked · generated{" "}
            {formatDateTime(eventStreamData.generated_at)}
          </p>
        </div>
      </section>

      <div className="workbench-grid">
        <div className="card span-12">
          <div className="card-title">ONTOLOGY CLASS LEGEND</div>
          <div className="token-row">
            {classes.map((cls) => {
              const color = ONTOLOGY_COLORS[cls] || "#a69691";
              return (
                <span
                  key={cls}
                  style={{
                    padding: "3px 8px",
                    border: `1px solid color-mix(in srgb, ${color} 40%, transparent)`,
                    background: `color-mix(in srgb, ${color} 12%, transparent)`,
                    color,
                    fontFamily: "var(--mono)",
                    fontSize: "10px",
                    textTransform: "uppercase",
                    letterSpacing: ".06em",
                  }}
                >
                  {cls.replace(/_/g, " ")}
                </span>
              );
            })}
          </div>
        </div>

        <div className="card span-12">
          <div className="card-title">FILTER</div>
          <div className="token-row">
            <button onClick={() => setFilter("all")} className={`token token-button ${filter === "all" ? "active-token" : ""}`}>
              all
            </button>
            {classes.map((cls) => (
              <button
                key={cls}
                onClick={() => setFilter(cls)}
                className={`token token-button ${filter === cls ? "active-token" : ""}`}
              >
                {cls.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>

        <div className="card span-12">
          <div className="card-title">EVENTS ({filtered.length})</div>
          {filtered.length === 0 && <p className="analysis-copy">No events match filter.</p>}
          {filtered.map((event) => (
            <div key={event.event_id} style={{ padding: "16px 0", borderBottom: "1px solid rgba(166,150,145,.14)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px", gap: "12px" }}>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <span
                    style={{
                      padding: "2px 8px",
                      background: `color-mix(in srgb, ${ONTOLOGY_COLORS[event.ontological_class] || "#a69691"} 16%, transparent)`,
                      border: `1px solid color-mix(in srgb, ${ONTOLOGY_COLORS[event.ontological_class] || "#a69691"} 40%, transparent)`,
                      color: ONTOLOGY_COLORS[event.ontological_class] || "#a69691",
                      fontFamily: "var(--mono)",
                      fontSize: "10px",
                      textTransform: "uppercase",
                      letterSpacing: ".06em",
                    }}
                  >
                    {event.ontological_class.replace(/_/g, " ")}
                  </span>
                  <span className="token">{event.initiator}</span>
                  <span className="token">{event.event_class}</span>
                  {event.decision === "delivered" && <span className="token active-token">delivered</span>}
                  {event.decision === "blocked" && <span className="token">blocked</span>}
                </div>
                <span style={{ fontFamily: "var(--mono)", fontSize: "11px", color: "var(--gold)", whiteSpace: "nowrap" }}>
                  {formatDateTime(event.timestamp)}
                </span>
              </div>
              <p className="transcript-text">{event.content_preview || "[blocked by policy]"}</p>
              <div className="token-row">
                <span className="status-text">risk: {event.risk_level}</span>
                {event.has_media && <span className="status-text">media</span>}
                {event.has_user_response && <span className="status-text">user_response</span>}
                {event.has_correction && <span className="status-text">correction</span>}
                {event.has_boundary_risk && <span className="status-text">boundary_risk</span>}
                <span className="status-text">id: {event.event_id}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="footer">Event stream · {subjectId}</div>
    </>
  );
}
