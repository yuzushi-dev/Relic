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

export default function BaselinePage({ params }: { params: { subject_id: string } }) {
  const study = getStudyOverview();
  const baselineData = getSubjectBaseline(params.subject_id);
  const gumiProfile = getGumiProfile(params.subject_id);
  if (!baselineData) {
    return (
      <>
        <SubjectNav subjects={study.subject_registry} currentSubjectId={params.subject_id} view="baseline" />
        <section className="hero">
          <div style={{ position: "relative", zIndex: 1 }}>
            <div className="eyebrow">BASELINE PROFILE</div>
            <h1>{params.subject_id}</h1>
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

  const d = { ...baselineData, subject_id: params.subject_id };
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
      <SubjectNav subjects={study.subject_registry} currentSubjectId={params.subject_id} view="baseline" />
      <section className="hero">
        <div style={{ position: "relative", zIndex: 1 }}>
          <div className="eyebrow">BASELINE PROFILE · VERSION {d.baseline_version}</div>
          <h1>{d.subject_id}</h1>
          <p className="lede">Method: <span style={{ color: "var(--gold)" }}>{d.baseline_method}</span> · Created {formatDate(d.creation_date)}</p>
        </div>
      </section>

      <div className="workbench-grid">
        <div className="card span-12">
          <div className="card-title">BASELINE FIELDS</div>
          <table className="dense-table">
            <thead>
              <tr>
                {["Field", "Value", "Origin", "Section"].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fields.map(f => (
                <tr key={f.name} style={{ borderBottom: "1px solid rgba(166,150,145,.14)" }}>
                  <td style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--ash)" }}>{f.name.replace(/_/g, " ")}</td>
                  <td style={{ fontSize: "13px", maxWidth: "400px" }}>{f.value}</td>
                  <td><span style={{ padding: "2px 8px", background: `color-mix(in srgb, ${ORIGIN_COLOR[f.origin] || "#a69691"} 16%, transparent)`, border: `1px solid color-mix(in srgb, ${ORIGIN_COLOR[f.origin] || "#a69691"} 40%, transparent)`, color: ORIGIN_COLOR[f.origin] || "#a69691", fontFamily: "var(--mono)", fontSize: "11px", textTransform: "uppercase" }}>{f.origin}</span></td>
                  <td style={{ color: "var(--text-muted)", fontSize: "12px" }}>{f.section}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {d.risk_flags.length > 0 && (
          <div className="card span-6">
            <div className="card-title">RISK FLAGS</div>
            {d.risk_flags.map(f => (
              <div key={f.flag_category} style={{ display: "flex", justifyContent: "space-between", gap: "12px", padding: "8px 0", borderBottom: "1px solid rgba(166,150,145,.14)" }}>
                <span style={{ fontFamily: "var(--mono)", fontSize: "12px" }}>{f.flag_category}</span>
                <span style={{ color: f.severity === "low" ? "#fbbf24" : "var(--red-soft)", fontFamily: "var(--mono)", fontSize: "11px", textTransform: "uppercase" }}>{f.severity}</span>
              </div>
            ))}
          </div>
        )}

        <div className={`card ${d.risk_flags.length > 0 ? "span-6" : "span-12"}`}>
          <div className="card-title">VERSION INFO</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            {[["Version", d.baseline_version], ["Created", formatDate(d.creation_date)]].map(([k,v]) => (
              <div key={k as string} style={{ padding: "8px", background: "var(--panel-2)", border: "1px solid var(--border)" }}>
                <div style={{ fontFamily: "var(--mono)", fontSize: "10px", color: "var(--gold)", textTransform: "uppercase", letterSpacing: ".12em" }}>{k}</div>
                <div style={{ fontFamily: "var(--head)", fontSize: "20px", marginTop: "4px" }}>{v}</div>
              </div>
            ))}
          </div>
        </div>

        {gumiProfile?.item_battery_scores && (
          <>
            <div className="card span-4">
              <div className="card-title">TIPI — BIG FIVE</div>
              {Object.entries(gumiProfile.item_battery_scores.tipi).map(([k, v]) => {
                const label = { extraversion: "Extraversion", agreeableness: "Agreeableness", conscientiousness: "Conscientiousness", emotional_stability: "Emotional Stability", openness: "Openness" }[k] ?? k;
                const pct = Math.min(100, Math.round((v / 7) * 100));
                return (
                  <div key={k} style={{ marginBottom: "12px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                      <span style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>{label}</span>
                      <span style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--gold)" }}>{v.toFixed(2)}</span>
                    </div>
                    <div style={{ height: "6px", background: "var(--border)", borderRadius: "3px" }}>
                      <div style={{ height: "100%", width: `${pct}%`, background: "color-mix(in srgb, var(--gold) 70%, transparent)", borderRadius: "3px" }} />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="card span-4">
              <div className="card-title">ECR-RS — ATTACHMENT</div>
              {Object.entries(gumiProfile.item_battery_scores.ecrrs).map(([k, v]) => {
                const label = { anxiety: "Anxiety", avoidance: "Avoidance" }[k] ?? k;
                const pct = Math.min(100, Math.round((v / 7) * 100));
                return (
                  <div key={k} style={{ marginBottom: "12px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                      <span style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>{label}</span>
                      <span style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "#60a5fa" }}>{v.toFixed(2)}</span>
                    </div>
                    <div style={{ height: "6px", background: "var(--border)", borderRadius: "3px" }}>
                      <div style={{ height: "100%", width: `${pct}%`, background: "color-mix(in srgb, #60a5fa 60%, transparent)", borderRadius: "3px" }} />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="card span-4">
              <div className="card-title">PROJECT CALIBRATION</div>
              {Object.entries(gumiProfile.item_battery_scores.project_calibration).length > 0
                ? Object.entries(gumiProfile.item_battery_scores.project_calibration).map(([k, v]) => {
                    const pct = Math.min(100, Math.round((v / 10) * 100));
                    return (
                      <div key={k} style={{ marginBottom: "12px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
                          <span style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>{k.replace(/_/g, " ")}</span>
                          <span style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "#c084fc" }}>{v.toFixed(2)}</span>
                        </div>
                        <div style={{ height: "6px", background: "var(--border)", borderRadius: "3px" }}>
                          <div style={{ height: "100%", width: `${pct}%`, background: "color-mix(in srgb, #c084fc 60%, transparent)", borderRadius: "3px" }} />
                        </div>
                      </div>
                    );
                  })
                : <p style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>No project scores.</p>
              }
            </div>
          </>
        )}

      </div>
      <div className="footer">Baseline profile · {d.subject_id}</div>
    </>
  );
}
