// Subject Baseline — PR27D
import { formatDate } from "../../../../../lib/format";
import { SubjectNav } from "../../../../../components/SubjectNav";
import { getGumiProfile, getStudyOverview, getSubjectBaseline } from "../../../../../lib/workbench-data";

type FieldValue = {
  value?: string | number;
  values?: string[];
  origin: string;
};

function flattenFields(group: Record<string, FieldValue>, section: string) {
  return Object.entries(group).map(([name, field]) => ({
    name,
    value: field.values ? field.values.join(", ") : String(field.value ?? "--"),
    origin: field.origin,
    section,
  }));
}

const ORIGIN_COLOR: Record<string, string> = {
  "subject-stated": "#60a5fa",
  "researcher-coded": "#c084fc",
  "system-inferred": "#a69691",
};

export function generateStaticParams() {
  return getStudyOverview().subject_registry.map((subject) => ({
    subject_id: subject.subject_id.replace(/-/g, "_"),
  }));
}

export default async function BaselinePage({ params }: { params: Promise<{ subject_id: string }> }) {
  const { subject_id } = await params;
  const study = getStudyOverview();
  const baselineData = getSubjectBaseline(subject_id);
  const gumiProfile = getGumiProfile(subject_id);
  if (!baselineData) {
    return (
      <>
        <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="baseline" />
        <section className="hero">
          <div style={{ position: "relative", zIndex: 1 }}>
            <div className="eyebrow">BASELINE PROFILE</div>
            <h1>{subject_id}</h1>
            <p className="lede">No live baseline artifact is available for this subject yet.</p>
          </div>
        </section>
        <div className="workbench-grid">
          <article className="card span-12">
            <div className="card-title">Live Data Source</div>
            <p className="analysis-copy">Demo baseline fields are intentionally hidden in live mode.</p>
          </article>
        </div>
      </>
    );
  }

  const d = { ...baselineData, subject_id };
  const fields = [
    ...flattenFields(d.self_report_fields, "Self-Report"),
    ...flattenFields(d.researcher_coded_fields, "Researcher-Coded"),
    ...flattenFields(d.system_inferred_fields, "System-Inferred"),
    ...flattenFields(d.interaction_preferences, "Interaction Preferences"),
    ...flattenFields(d.relational_expectations, "Relational Expectations"),
    ...flattenFields(d.boundaries, "Boundaries"),
    { name: "opt_out_categories", value: d.opt_out_categories.values.join(", "), origin: d.opt_out_categories.origin, section: "Boundaries" },
  ];

  return (
    <>
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="baseline" />
      <header className="page-header">
        <div className="page-eyebrow">Baseline Profile · Version {d.baseline_version}</div>
        <h1 className="page-title">{d.subject_id}</h1>
        <div className="page-meta">
          <span>Method: <span style={{ color: "var(--pend)", fontWeight: 600 }}>{d.baseline_method}</span></span>
          <span className="mono" style={{ opacity: 0.5 }}>|</span>
          <span>Created {formatDate(d.creation_date)}</span>
        </div>
      </header>

      <div className="wgrid">
        <article className="card col-12">
          <h2 className="card-label">BASELINE FIELDS</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Field</th>
                <th scope="col">Value</th>
                <th scope="col">Origin</th>
                <th scope="col">Section</th>
              </tr>
            </thead>
            <tbody>
              {fields.map(f => (
                <tr key={f.name}>
                  <td className="mono text-dim">{f.name.replace(/_/g, " ")}</td>
                  <td>{f.value}</td>
                  <td>
                    <span className="stream-chip" data-stream={f.origin === "subject-stated" ? "evidence" : f.origin === "researcher-coded" ? "approved" : "neutral"}>
                      {f.origin}
                    </span>
                  </td>
                  <td className="text-dim">{f.section}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>

        {d.risk_flags.length > 0 && (
          <article className="card col-6">
            <h2 className="card-label">RISK FLAGS</h2>
            <div className="data-list">
              {d.risk_flags.map(f => (
                <div key={f.flag_category} className="data-row">
                  <span className="mono">{f.flag_category}</span>
                  <span className="state-marker" data-state={f.severity === "high" ? "failed" : "paused"}>
                    {f.severity.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </article>
        )}

        <article className={`card ${d.risk_flags.length > 0 ? "col-6" : "col-12"}`}>
          <h2 className="card-label">VERSION INFO</h2>
          <div className="stat-bar" style={{ marginBottom: 0 }}>
            {[["Baseline Version", d.baseline_version], ["Creation Date", formatDate(d.creation_date)]].map(([k,v]) => (
              <div key={k as string} className="stat-item">
                <div className="stat-key">{k}</div>
                <div className="stat-val" style={{ fontSize: "18px" }}>{v}</div>
              </div>
            ))}
          </div>
        </article>

        {gumiProfile?.item_battery_scores && (
          <>
            <article className="card col-4">
              <h2 className="card-label">TIPI — BIG FIVE</h2>
              {Object.entries(gumiProfile.item_battery_scores.tipi).map(([k, v]) => {
                const label = { extraversion: "Extraversion", agreeableness: "Agreeableness", conscientiousness: "Conscientiousness", emotional_stability: "Emotional Stability", openness: "Openness" }[k] ?? k;
                const pct = Math.min(100, Math.round((v / 7) * 100));
                return (
                  <div key={k} className="facet-row">
                    <div className="facet-header">
                      <span className="facet-name">{label}</span>
                      <span className="facet-stats">{v.toFixed(2)}</span>
                    </div>
                    <div className="facet-track">
                      <div className="facet-needle" style={{ left: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </article>

            <article className="card col-4">
              <h2 className="card-label">ECR-RS — ATTACHMENT</h2>
              {Object.entries(gumiProfile.item_battery_scores.ecrrs).map(([k, v]) => {
                const label = { anxiety: "Anxiety", avoidance: "Avoidance" }[k] ?? k;
                const pct = Math.min(100, Math.round((v / 7) * 100));
                return (
                  <div key={k} className="facet-row">
                    <div className="facet-header">
                      <span className="facet-name">{label}</span>
                      <span className="facet-stats">{v.toFixed(2)}</span>
                    </div>
                    <div className="facet-track">
                      <div className="facet-needle" style={{ left: `${pct}%`, background: "var(--inf)" }} />
                    </div>
                  </div>
                );
              })}
            </article>

            <article className="card col-4">
              <h2 className="card-label">PROJECT CALIBRATION</h2>
              {Object.entries(gumiProfile.item_battery_scores.project_calibration).length > 0
                ? Object.entries(gumiProfile.item_battery_scores.project_calibration).map(([k, v]) => {
                    const pct = Math.min(100, Math.round((v / 10) * 100));
                    return (
                      <div key={k} className="facet-row">
                        <div className="facet-header">
                          <span className="facet-name">{k.replace(/_/g, " ")}</span>
                          <span className="facet-stats">{v.toFixed(2)}</span>
                        </div>
                        <div className="facet-track">
                          <div className="facet-needle" style={{ left: `${pct}%`, background: "var(--gumi)" }} />
                        </div>
                      </div>
                    );
                  })
                : <p className="empty-state">No project scores calibrated.</p>
              }
            </article>
          </>
        )}
      </div>
      <footer className="page-footer">Baseline Artifact · {d.subject_id}</footer>
    </>
  );
}
