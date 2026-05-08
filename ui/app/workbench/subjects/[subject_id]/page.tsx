// Subject Overview — PR27C
import Link from "next/link";
import { SubjectIntelligence } from "../../../../components/SubjectIntelligence";
import { formatDate } from "../../../../lib/format";
import { getGumiProfile, getStudyOverview, getSubjectIntelligence, getSubjectOverview } from "../../../../lib/workbench-data";

export function generateStaticParams() {
  return getStudyOverview().subject_registry.map((subject) => ({
    subject_id: subject.subject_id.replace(/-/g, "_"),
  }));
}

export default function SubjectPage({ params }: { params: { subject_id: string } }) {
  const d = getSubjectOverview(params.subject_id);
  if (!d) {
    return (
      <>
        <section className="hero">
          <div style={{ position: "relative", zIndex: 1 }}>
            <div className="eyebrow">Subject profile</div>
            <h1>{params.subject_id}</h1>
            <p className="lede">No live subject profile was found for this id.</p>
          </div>
        </section>
        <div className="workbench-grid">
          <article className="card span-12">
            <div className="card-title">Live Data Source</div>
            <p className="analysis-copy">Expected `$RELIC_HOME/subjects/{params.subject_id}/subject_profile.json`.</p>
          </article>
        </div>
      </>
    );
  }
  const prov = d.hermes_profile_status;
  const subjectIntelligence = getSubjectIntelligence(params.subject_id);
  const gumiProfile = getGumiProfile(params.subject_id);

  return (
    <>
      <section className="hero">
        <div className="hero-grid">
          <div>
            <div className="eyebrow">Subject profile · {d.experiment_id}</div>
            <h1>{d.subject_id}</h1>
            <p className="lede">
              Status: <span style={{ color: "#84d1a4", textTransform: "uppercase" }}>{d.subject_status}</span>
              {" · "}Condition: <span style={{ color: "var(--gold)" }}>{d.active_condition}</span>
              {" · "}Consent: <span style={{ color: "#84d1a4" }}>{d.consent_status}</span>
            </p>
          </div>
          <aside className="hero-side">
            <div className="eyebrow">Subject state</div>
            <div className="token-row" style={{ marginTop: "14px" }}>
              <span className="token active-token">{d.bootstrap_status}</span>
              <span className="token">{prov.profile_name}</span>
              <span className="token">{d.pending_review_count} reviews</span>
            </div>
          </aside>
        </div>
      </section>

      <div className="summary-strip" style={{ marginTop: "20px" }}>
        {[
          { label: "Gumi Instance", value: d.active_gumi_instance },
          { label: "Hermes Profile", value: prov.profile_name },
          { label: "Last Interaction", value: formatDate(d.last_user_interaction) },
          { label: "Pending Reviews", value: d.pending_review_count },
        ].map(s => (
          <div key={s.label} className="strip-item">
            <div className="strip-label">{s.label}</div>
            <div style={{ marginTop: "6px", fontFamily: "var(--mono)", fontSize: "12px", color: "var(--ash)", wordBreak: "break-all" }}>{s.value}</div>
          </div>
        ))}
      </div>

      <SubjectIntelligence subjectIntelligence={subjectIntelligence} />

      <div className="workbench-grid">

        <div className="card span-4">
          <div className="card-title">HERMES PROFILE</div>
          <div className="status-chip">
            <div className="status-dot" />
            {prov.provisioned ? "Provisioned" : "Not Provisioned"}
          </div>
          <div style={{ marginTop: "12px", fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>{prov.profile_name}</div>
        </div>

        <div className="card span-4">
          <div className="card-title">BOOTSTRAP</div>
          <div className="status-chip">
            <div className="status-dot" />
            {d.bootstrap_status}
          </div>
        </div>

        <div className="card span-4">
          <div className="card-title">RISK ASSESSMENT</div>
          <div style={{ fontFamily: "var(--head)", fontSize: "32px", color: d.risk_summary.severity === "none" ? "#84d1a4" : "#fbbf24" }}>
            {d.risk_summary.severity.toUpperCase()}
          </div>
          <div style={{ fontFamily: "var(--mono)", fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
            {d.risk_summary.flag_count} flags
          </div>
        </div>

        <div className="card span-6">
          <div className="card-title">ACTIVE CRON MODES</div>
          <div className="token-row">
            {d.active_cron_modes.map(m => (
              <span key={m} className="token">{m}</span>
            ))}
          </div>
        </div>

        <div className="card span-6">
          <div className="card-title">PAUSE STATE</div>
          <div className="token-row">
            {Object.entries(d.pause_state).filter(([,v]) => v).map(([k]) => (
              <span key={k} className="token" style={{ borderColor: "var(--red)", color: "var(--red-soft)", background: "color-mix(in srgb, var(--red) 20%, transparent)" }}>{k}</span>
            ))}
            {Object.values(d.pause_state).every(v => !v) && (
              <span style={{ color: "var(--text-muted)", fontFamily: "var(--mono)", fontSize: "11px" }}>All active</span>
            )}
          </div>
        </div>

        {gumiProfile && (
          <div className="card span-12">
            <div className="card-title">GUMI · {gumiProfile.agent_name}</div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px" }}>
              <div>
                <div className="token-row" style={{ marginBottom: "8px" }}>
                  <span className="token">{gumiProfile.generation_mode}</span>
                  {gumiProfile.sweet_spot_score !== null && (
                    <span className="token" style={{ borderColor: "#84d1a4", color: "#84d1a4" }}>
                      score {gumiProfile.sweet_spot_score.toFixed(3)}
                    </span>
                  )}
                </div>
                {gumiProfile.soul_md && (
                  <p style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)", margin: "0", maxWidth: "600px", lineHeight: "1.5", overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical" }}>
                    {gumiProfile.soul_md.split("\n").slice(0, 3).join(" ")}
                  </p>
                )}
              </div>
              <Link href={`/workbench/subjects/${d.subject_id}/gumi` as any} className="token" style={{ textDecoration: "none", whiteSpace: "nowrap" }}>
                View Profile →
              </Link>
            </div>
          </div>
        )}

        <div className="card span-12">
          <div className="card-title">VIEWS</div>
          <div className="token-row">
            <Link href={`/workbench/subjects/${d.subject_id}/baseline`} className="token" style={{ textDecoration: "none" }}>Baseline Profile</Link>
            <Link href={`/workbench/subjects/${d.subject_id}/timeline`} className="token" style={{ textDecoration: "none" }}>Event Timeline</Link>
            <Link href={`/workbench/subjects/${d.subject_id}/gumi` as any} className="token" style={{ textDecoration: "none" }}>Gumi Profile</Link>
          </div>
        </div>

      </div>

      <div className="footer">Subject scope: {d.subject_id}</div>
    </>
  );
}
