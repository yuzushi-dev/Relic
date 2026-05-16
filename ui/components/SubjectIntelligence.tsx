import { formatDateTime } from "../lib/format";
import type { SubjectIntelligenceData } from "../lib/workbench-data";

type Facet = SubjectIntelligenceData["facet_groups"][number]["facets"][number];

function confidenceLevel(c: number): "high" | "medium" | "low" {
  if (c >= 0.7) return "high";
  if (c >= 0.4) return "medium";
  return "low";
}

function FacetRow({ facet }: { facet: Facet }) {
  const positionPct   = Math.round(facet.position * 100);
  const confidencePct = Math.round(facet.confidence * 100);
  const level         = confidenceLevel(facet.confidence);

  return (
    <div className="facet-row">
      <div className="facet-header">
        {/* facet-name is a label, not a heading — already in an h3 group context */}
        <span className="facet-name">{facet.facet}</span>
        <span className="facet-stats">
          pos {facet.position.toFixed(2)}
          &ensp;·&ensp;
          conf {facet.confidence.toFixed(2)}
          &ensp;·&ensp;
          {facet.observations} obs
        </span>
      </div>

      <div className="facet-spectrum">
        <span className="facet-anchor" aria-hidden="true">{facet.left_anchor}</span>
        <div
          className="facet-track"
          role="meter"
          aria-label={`${facet.facet} position: ${positionPct}% toward ${facet.right_anchor}`}
          aria-valuenow={positionPct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className="facet-needle" style={{ left: `${positionPct}%` }} aria-hidden="true" />
        </div>
        <span className="facet-anchor" aria-hidden="true">{facet.right_anchor}</span>
      </div>

      <div className="confidence-bar">
        <div
          className="confidence-fill"
          data-level={level}
          style={{ width: `${confidencePct}%` }}
          role="meter"
          aria-label={`${facet.facet} confidence: ${confidencePct}% (${level})`}
          aria-valuenow={confidencePct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */

export function SubjectIntelligence({
  subjectIntelligence,
}: {
  subjectIntelligence: SubjectIntelligenceData | null;
}) {
  if (!subjectIntelligence) {
    return (
      <div className="wgrid" style={{ marginTop: "16px" }}>
        <article className="card col-12" data-stream="blocked">
          {/* h2 since page h1 exists in the parent view */}
          <h2 className="card-label">Behavioral model</h2>
          <p className="empty-state">
            No live behavioral model available for this subject.
            Demo intelligence is intentionally hidden in live mode.
          </p>
        </article>
      </div>
    );
  }

  const summary = subjectIntelligence.model_summary;

  return (
    <>
      {/* Stat bar — linked stat keys */}
      <div className="stat-bar" role="region" aria-label="Model summary statistics">
        {[
          { key: "Facets modeled", val: `${summary.facets_modeled} / ${summary.facets_total}` },
          { key: "Observations",   val: `${summary.seed_observations}` },
          { key: "Signals",        val: `${summary.extraction_signals}` },
          { key: "Hypotheses",     val: `${summary.hypotheses}` },
        ].map((item) => {
          const id = `si-stat-${item.key.toLowerCase().replace(/\s/g, "-")}`;
          return (
            <div key={item.key} className="stat-item">
              <div className="stat-key" id={id}>{item.key}</div>
              <div className="stat-val" aria-labelledby={id}>{item.val}</div>
            </div>
          );
        })}
      </div>

      <div className="wgrid">

        {/* Behavioral summary */}
        <article className="card col-8" data-stream="evidence" aria-labelledby="card-behavioral-summary">
          <h2 className="card-label" id="card-behavioral-summary">Behavioral summary</h2>
          <p className="prose">{summary.summary}</p>
          <div className="tag-row" aria-label="Top trait tags">
            {subjectIntelligence.top_traits.map((trait) => (
              <span key={trait} className="tag">{trait}</span>
            ))}
          </div>
        </article>

        {/* Active goals */}
        <article className="card col-4" aria-labelledby="card-active-goals">
          <h2 className="card-label" id="card-active-goals">Active goals</h2>
          <ul className="goal-list">
            {subjectIntelligence.active_goals.map((goal) => (
              <li key={goal}>
                {goal}
              </li>
            ))}
          </ul>
        </article>

        {/* Top confidence facets */}
        <article className="card col-4" aria-labelledby="card-top-facets">
          <h2 className="card-label" id="card-top-facets">Top confidence facets</h2>
          <div className="data-list">
            {subjectIntelligence.top_confidence_facets.map((facet) => (
              <div key={facet.facet} className="data-row">
                <span className="mono">{facet.facet}</span>
                <span className="text-dim">p{facet.position.toFixed(2)}</span>
                <span className="text-dim">c{facet.confidence.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </article>

        {/* Cross-facet hypotheses */}
        <article className="card col-8" data-stream="inference" aria-labelledby="card-hypotheses">
          <h2 className="card-label" id="card-hypotheses">Cross-facet hypotheses</h2>
          {subjectIntelligence.hypotheses.map((h) => (
            <section key={h.title} className="hypothesis-block" aria-labelledby={`hyp-${h.title.replace(/\s/g, "-")}`}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "10px", flexWrap: "wrap", marginBottom: "5px" }}>
                {/* h3 — nested under h2 card heading (WCAG 1.3.1) */}
                <h3
                  className="hypothesis-title"
                  id={`hyp-${h.title.replace(/\s/g, "-")}`}
                >
                  {h.title}
                </h3>
                <span
                  className="stream-chip"
                  data-stream={confidenceLevel(h.confidence) === "high" ? "approved" : confidenceLevel(h.confidence) === "medium" ? "pending" : "blocked"}
                  aria-label={`Confidence: ${h.confidence.toFixed(2)}, ${h.confidence_label}`}
                >
                  {h.confidence.toFixed(2)} {h.confidence_label}
                </span>
              </div>
              <p className="hypothesis-copy">{h.summary}</p>
              <div className="tag-row" aria-label="Related facets" style={{ marginTop: "6px" }}>
                {h.facets.map((f) => (
                  <span key={f} className="tag">{f}</span>
                ))}
              </div>
            </section>
          ))}
        </article>

        {/* Facet model */}
        <article className="card col-12" data-stream="inference" aria-labelledby="card-facet-model">
          <h2 className="card-label" id="card-facet-model">Facet model</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "0 40px" }}>
            {subjectIntelligence.facet_groups.map((group) => (
              <section key={group.group} aria-labelledby={`facet-group-${group.group.replace(/\s/g, "-")}`}>
                {/* h3 under h2 card heading */}
                <h3
                  className="group-header"
                  id={`facet-group-${group.group.replace(/\s/g, "-")}`}
                  style={{ marginTop: "14px" }}
                >
                  {group.group}
                </h3>
                {group.facets.map((facet) => (
                  <FacetRow key={facet.facet} facet={facet} />
                ))}
              </section>
            ))}
          </div>
        </article>

        {/* Evidence transcript */}
        <article className="card col-8" data-stream="evidence" aria-labelledby="card-evidence-transcript">
          <h2 className="card-label" id="card-evidence-transcript">Evidence transcript</h2>
          <div className="evidence-list" role="feed" aria-label="Evidence items">
            {subjectIntelligence.transcript.map((item) => (
              <article
                key={item.id}
                className="evidence-item"
                aria-labelledby={`ev-${item.id}`}
              >
                <div className="evidence-meta">
                  <span className="evidence-id" id={`ev-${item.id}`}>{item.id}</span>
                  <span className="stream-chip" data-stream="neutral">{item.channel}</span>
                  <time className="evidence-id" dateTime={item.timestamp}>
                    {formatDateTime(item.timestamp)}
                  </time>
                </div>
                <p className="evidence-text">{item.content}</p>
              </article>
            ))}
          </div>
        </article>

        {/* Extraction signals */}
        <article className="card col-4" data-stream="inference" aria-labelledby="card-signals">
          <h2 className="card-label" id="card-signals">Extraction signals</h2>
          {subjectIntelligence.extraction_sample.map((sig) => (
            <div key={`${sig.facet}-${sig.source}`} className="signal-row">
              <span className="mono" style={{ fontSize: "12px" }}>{sig.facet}</span>
              <span className="text-sub">{sig.direction}</span>
              <span className="text-dim">
                strength {sig.strength.toFixed(2)} · {sig.source}
              </span>
            </div>
          ))}
        </article>

        {/* Runtime artifacts */}
        <article className="card col-12" data-stream="runtime" aria-labelledby="card-artifacts">
          <h2 className="card-label" id="card-artifacts">Runtime artifacts</h2>
          {subjectIntelligence.artifacts.map((artifact) => (
            <div key={artifact.name} className="data-row artifact">
              <span className="mono">{artifact.name}</span>
              <span className="text-dim">{artifact.kind}</span>
              <span className="text-sub">{artifact.lineage}</span>
            </div>
          ))}
        </article>

      </div>
    </>
  );
}
