import { formatDateTime } from "../lib/format";
import type { SubjectIntelligenceData } from "../lib/workbench-data";

type Facet = SubjectIntelligenceData["facet_groups"][number]["facets"][number];

function FacetRow({ facet }: { facet: Facet }) {
  const position = Math.round(facet.position * 100);
  const confidence = Math.round(facet.confidence * 100);

  return (
    <div className="facet-row">
      <div className="facet-head">
        <span className="mono">{facet.facet}</span>
        <span className="status-text">
          pos {facet.position.toFixed(2)} · conf {facet.confidence.toFixed(2)} · {facet.observations} obs
        </span>
      </div>
      <div className="facet-scale">
        <span>{facet.left_anchor}</span>
        <div className="facet-track" aria-label={`${facet.facet} position ${position}%`}>
          <div className="facet-fill" style={{ width: `${position}%` }} />
        </div>
        <span>{facet.right_anchor}</span>
      </div>
      <div className="confidence-track" aria-label={`${facet.facet} confidence ${confidence}%`}>
        <div className="confidence-fill" style={{ width: `${confidence}%` }} />
      </div>
    </div>
  );
}

export function SubjectIntelligence({ subjectIntelligence }: { subjectIntelligence: SubjectIntelligenceData | null }) {
  if (!subjectIntelligence) {
    return (
      <section className="workbench-grid">
        <article className="card span-12">
          <div className="card-title">Behavioral Model</div>
          <p className="analysis-copy">
            No live behavioral model is available for this subject yet. Demo intelligence is intentionally hidden in live mode.
          </p>
        </article>
      </section>
    );
  }

  const summary = subjectIntelligence.model_summary;

  return (
    <>
      <section className="summary-strip" style={{ marginTop: "20px" }}>
        {[
          { label: "Facets Modeled", value: `${summary.facets_modeled} / ${summary.facets_total}` },
          { label: "Observations", value: `${summary.seed_observations}` },
          { label: "Extraction Signals", value: `${summary.extraction_signals}` },
          { label: "Hypotheses", value: `${summary.hypotheses}` },
        ].map((item) => (
          <div key={item.label} className="strip-item">
            <div className="strip-label">{item.label}</div>
            <div className="strip-value">{item.value}</div>
          </div>
        ))}
      </section>

      <section className="workbench-grid">
        <article className="card span-8">
          <div className="card-title">Behavioral Summary</div>
          <p className="analysis-copy">{summary.summary}</p>
          <div className="token-row" style={{ marginTop: "14px" }}>
            {subjectIntelligence.top_traits.map((trait) => (
              <span key={trait} className="token">{trait}</span>
            ))}
          </div>
        </article>

        <article className="card span-4">
          <div className="card-title">Active Goals</div>
          <ul className="analysis-list">
            {subjectIntelligence.active_goals.map((goal) => (
              <li key={goal}>{goal}</li>
            ))}
          </ul>
        </article>

        <article className="card span-4">
          <div className="card-title">Top Confidence Facets</div>
          <div className="metric-list">
            {subjectIntelligence.top_confidence_facets.map((facet) => (
              <div key={facet.facet} className="metric-row">
                <span className="mono">{facet.facet}</span>
                <span>pos {facet.position.toFixed(2)}</span>
                <span>conf {facet.confidence.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="card span-8">
          <div className="card-title">Cross-Facet Hypotheses</div>
          <div className="stack">
            {subjectIntelligence.hypotheses.map((hypothesis) => (
              <section key={hypothesis.title} className="hypothesis-block">
                <div className="facet-head">
                  <h2>{hypothesis.title}</h2>
                  <span className="token active-token">
                    {hypothesis.confidence.toFixed(2)} {hypothesis.confidence_label}
                  </span>
                </div>
                <p className="analysis-copy">{hypothesis.summary}</p>
                <div className="token-row">
                  {hypothesis.facets.map((facet) => (
                    <span key={facet} className="token">{facet}</span>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </article>

        <article className="card span-12">
          <div className="card-title">Facet Model</div>
          <div className="facet-grid">
            {subjectIntelligence.facet_groups.map((group) => (
              <section key={group.group} className="facet-group">
                <h2>{group.group}</h2>
                {group.facets.map((facet) => (
                  <FacetRow key={facet.facet} facet={facet} />
                ))}
              </section>
            ))}
          </div>
        </article>

        <article className="card span-8">
          <div className="card-title">Evidence Transcript</div>
          <div className="transcript-list">
            {subjectIntelligence.transcript.map((item) => (
              <article key={item.id} className="transcript-item">
                <div className="transcript-meta">
                  {formatDateTime(item.timestamp)} · {item.channel} · {item.id}
                </div>
                <p className="transcript-text">{item.content}</p>
              </article>
            ))}
          </div>
        </article>

        <article className="card span-4">
          <div className="card-title">Extraction Sample</div>
          <div className="stack">
            {subjectIntelligence.extraction_sample.map((signal) => (
              <div key={`${signal.facet}-${signal.source}`} className="signal-row">
                <span className="mono">{signal.facet}</span>
                <span>{signal.direction}</span>
                <span className="status-text">strength {signal.strength.toFixed(2)} · {signal.source}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="card span-12">
          <div className="card-title">Artifacts</div>
          <div className="metric-list artifact-list">
            {subjectIntelligence.artifacts.map((artifact) => (
              <div key={artifact.name} className="metric-row">
                <span className="mono">{artifact.name}</span>
                <span>{artifact.kind}</span>
                <span className="status-text">{artifact.lineage}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </>
  );
}
