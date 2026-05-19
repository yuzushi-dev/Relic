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

export default async function SubjectPage({ params }: { params: Promise<{ subject_id: string }> }) {
  const { subject_id } = await params;
  const d = getSubjectOverview(subject_id);
  if (!d) {
    return (
      <>
        <section className="hero">
          <div style={{ position: "relative", zIndex: 1 }}>
            <div className="eyebrow">Subject profile</div>
            <h1>{subject_id}</h1>
            <p className="lede">No live subject profile was found for this id.</p>
          </div>
        </section>
        <div className="workbench-grid">
          <article className="card span-12">
            <div className="card-title">Live Data Source</div>
            <p className="analysis-copy">Expected `$RELIC_HOME/subjects/{subject_id}/subject_profile.json`.</p>
          </article>
        </div>
      </>
    );
  }
  const prov = d.hermes_profile_status;
  const subjectIntelligence = getSubjectIntelligence(subject_id);
  const gumiProfile = getGumiProfile(subject_id);

  return (
    <>
      <header className="page-header">
        <div className="page-eyebrow">Subject Profile · {d.experiment_id}</div>
        <h1 className="page-title">{d.subject_id}</h1>
        <div className="page-meta">
          <span>Status: <span style={{ color: "var(--ok)", fontWeight: 600 }}>{d.subject_status.toUpperCase()}</span></span>
          <span className="mono" style={{ opacity: 0.5 }}>|</span>
          <span>Condition: <span style={{ color: "var(--pend)", fontWeight: 600 }}>{d.active_condition}</span></span>
          <span className="mono" style={{ opacity: 0.5 }}>|</span>
          <span>Consent: <span style={{ color: "var(--ok)" }}>{d.consent_status}</span></span>
        </div>
      </header>

      <div className="stat-bar" role="region" aria-label="Subject Summary">
        {[
          { label: "Gumi Instance", value: d.active_gumi_instance },
          { label: "Hermes Profile", value: prov.profile_name },
          { label: "Last Interaction", value: formatDate(d.last_user_interaction) },
          { label: "Pending Reviews", value: d.pending_review_count, state: d.pending_review_count > 0 ? "warn" : undefined },
        ].map(s => (
          <div key={s.label} className="stat-item">
            <div className="stat-key">{s.label}</div>
            <div className="stat-val" style={{ fontSize: "16px", wordBreak: "break-all" }} data-warn={s.state === "warn" || undefined}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      <div className="wgrid" style={{ marginTop: "16px" }}>
        <div className="card col-12" style={{ padding: "12px 16px" }}>
          <div className="tag-row" style={{ margin: 0 }}>
            <Link href={`/workbench/subjects/${d.subject_id}/baseline`} className="filter-btn" style={{ textDecoration: "none" }}>Baseline Profile</Link>
            <Link href={`/workbench/subjects/${d.subject_id}/timeline`} className="filter-btn" style={{ textDecoration: "none" }}>Event Timeline</Link>
            <Link href={`/workbench/subjects/${d.subject_id}/gumi` as any} className="filter-btn" style={{ textDecoration: "none" }}>Gumi Profile</Link>
            <Link href={`/workbench/subjects/${d.subject_id}/chronicle` as any} className="filter-btn" style={{ textDecoration: "none" }}>Chronicle</Link>
          </div>
        </div>
      </div>

      <SubjectIntelligence subjectIntelligence={subjectIntelligence} />

      <div className="wgrid">
        <div className="card col-4">
          <h2 className="card-label">HERMES PROFILE</h2>
          <div className="state-marker" data-state={prov.provisioned ? "active" : "failed"}>
            {prov.provisioned ? "Provisioned" : "Not Provisioned"}
          </div>
          <div className="mono text-dim" style={{ marginTop: "12px", fontSize: "11px" }}>{prov.profile_name}</div>
        </div>

        <div className="card col-4">
          <h2 className="card-label">BOOTSTRAP</h2>
          <div className="state-marker" data-state="active">
            {d.bootstrap_status}
          </div>
        </div>

        <div className="card col-4">
          <h2 className="card-label">RISK ASSESSMENT</h2>
          <div className="stat-val" data-fault={d.risk_summary.severity !== "none" || undefined} data-ok={d.risk_summary.severity === "none" || undefined}>
            {d.risk_summary.severity.toUpperCase()}
          </div>
          <div className="mono text-dim" style={{ marginTop: "4px", fontSize: "11px" }}>
            {d.risk_summary.flag_count} flags detected
          </div>
        </div>

        <div className="card col-6">
          <h2 className="card-label">ACTIVE CRON MODES</h2>
          <div className="tag-row">
            {d.active_cron_modes.map(m => (
              <span key={m} className="tag">{m}</span>
            ))}
          </div>
        </div>

        <div className="card col-6">
          <h2 className="card-label">PAUSE STATE</h2>
          <div className="tag-row">
            {Object.entries(d.pause_state).filter(([,v]) => v).map(([k]) => (
              <span key={k} className="tag" style={{ borderColor: "var(--block)", color: "var(--block)" }}>{k}</span>
            ))}
            {Object.values(d.pause_state).every(v => !v) && (
              <span className="mono text-dim">All components active</span>
            )}
          </div>
        </div>

        {gumiProfile && (
          <div className="card col-12">
            <h2 className="card-label">GUMI AGENT · {gumiProfile.agent_name}</h2>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div className="tag-row" style={{ marginBottom: "12px" }}>
                  <span className="tag">{gumiProfile.generation_mode}</span>
                  {gumiProfile.sweet_spot_score !== null && (
                    <span className="tag" style={{ borderColor: "var(--ok)", color: "var(--ok)" }}>
                      score {gumiProfile.sweet_spot_score.toFixed(3)}
                    </span>
                  )}
                </div>
                {gumiProfile.soul_md && (
                  <p className="prose" style={{ maxWidth: "800px" }}>
                    {gumiProfile.soul_md.split("\n").slice(0, 3).join(" ")}...
                  </p>
                )}
              </div>
              <Link href={`/workbench/subjects/${d.subject_id}/gumi` as any} className="filter-btn active" style={{ textDecoration: "none" }}>
                View Agent Details →
              </Link>
            </div>
          </div>
        )}

      </div>

      <footer className="page-footer">Subject Scope: {d.subject_id}</footer>
    </>
  );
}
