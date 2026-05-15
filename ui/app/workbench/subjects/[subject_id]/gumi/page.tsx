// Gumi Identity — Profile files + item battery scores
export const dynamic = 'force-dynamic'
import { formatDate } from "../../../../../lib/format";
import { SubjectNav } from "../../../../../components/SubjectNav";
import { getGumiProfile, getStudyOverview } from "../../../../../lib/workbench-data";

export function generateStaticParams() {
  return getStudyOverview().subject_registry.map((subject) => ({
    subject_id: subject.subject_id.replace(/-/g, "_"),
  }));
}

const TIPI_LABELS: Record<string, string> = {
  extraversion: "Extraversion",
  agreeableness: "Agreeableness",
  conscientiousness: "Conscientiousness",
  emotional_stability: "Emotional Stability",
  openness: "Openness",
};

const ECRRS_LABELS: Record<string, string> = {
  anxiety: "Anxiety",
  avoidance: "Avoidance",
};

function ScoreBar({ label, value, max = 7 }: { label: string; value: number; max?: number }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div style={{ marginBottom: "12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
        <span style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>{label}</span>
        <span style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--gold)" }}>{value.toFixed(2)}</span>
      </div>
      <div style={{ height: "6px", background: "var(--border)", borderRadius: "3px" }}>
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: "color-mix(in srgb, var(--gold) 70%, transparent)",
            borderRadius: "3px",
          }}
        />
      </div>
    </div>
  );
}

function MarkdownBlock({ title, content }: { title: string; content: string | null }) {
  if (content === null) {
    return (
      <div className="card span-12">
        <div className="card-title">{title}</div>
        <p style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>File not found.</p>
      </div>
    );
  }
  if (content.trim() === "") {
    return (
      <div className="card span-12">
        <div className="card-title">{title}</div>
        <p style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>Empty.</p>
      </div>
    );
  }
  return (
    <div className="card span-12">
      <div className="card-title">{title}</div>
      <pre
        style={{
          fontFamily: "var(--mono)",
          fontSize: "12px",
          lineHeight: "1.7",
          color: "var(--text)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          margin: 0,
          maxHeight: "480px",
          overflowY: "auto",
        }}
      >
        {content}
      </pre>
    </div>
  );
}

export default async function GumiPage({ params }: { params: Promise<{ subject_id: string }> }) {
  const { subject_id } = await params;
  const study = getStudyOverview();
  const g = getGumiProfile(subject_id);

  if (!g) {
    return (
      <>
        <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="gumi" />
        <section className="hero">
          <div style={{ position: "relative", zIndex: 1 }}>
            <div className="eyebrow">GUMI PROFILE</div>
            <h1>{subject_id}</h1>
            <p className="lede">No Gumi profile found. Run <code>relic subject</code> to provision.</p>
          </div>
        </section>
        <div className="workbench-grid">
          <article className="card span-12">
            <div className="card-title">Live Data Source</div>
            <p className="analysis-copy">Available only in live mode with RELIC_HOME set.</p>
          </article>
        </div>
      </>
    );
  }

  const domains = Object.entries(g.domains);
  const tipiEntries = g.item_battery_scores ? Object.entries(g.item_battery_scores.tipi) : [];
  const ecrrsEntries = g.item_battery_scores ? Object.entries(g.item_battery_scores.ecrrs) : [];
  const projectEntries = g.item_battery_scores ? Object.entries(g.item_battery_scores.project_calibration) : [];

  return (
    <>
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="gumi" />
      <header className="page-header">
        <div className="page-eyebrow">Gumi Agent Profile · {subject_id}</div>
        <h1 className="page-title">{g.agent_name}</h1>
        <div className="page-meta">
          <span>Mode: <span style={{ color: "var(--pend)", fontWeight: 600 }}>{g.generation_mode.toUpperCase()}</span></span>
          <span className="mono" style={{ opacity: 0.5 }}>|</span>
          {g.sweet_spot_score !== null && (
            <>
              <span>Sweet Spot: <span style={{ color: "var(--ok)" }}>{g.sweet_spot_score.toFixed(3)}</span></span>
              <span className="mono" style={{ opacity: 0.5 }}>|</span>
            </>
          )}
          {g.created_at && <span>Created {formatDate(g.created_at)}</span>}
        </div>
      </header>

      <div className="wgrid">
        {/* Item battery scores */}
        {g.item_battery_scores && (
          <>
            <article className="card col-4">
              <h2 className="card-label">TIPI — BIG FIVE</h2>
              {tipiEntries.map(([k, v]) => {
                const pct = Math.min(100, Math.round((v / 7) * 100));
                return (
                  <div key={k} className="facet-row">
                    <div className="facet-header">
                      <span className="facet-name">{TIPI_LABELS[k] ?? k}</span>
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
              {ecrrsEntries.map(([k, v]) => {
                const pct = Math.min(100, Math.round((v / 7) * 100));
                return (
                  <div key={k} className="facet-row">
                    <div className="facet-header">
                      <span className="facet-name">{ECRRS_LABELS[k] ?? k}</span>
                      <span className="facet-stats">{v.toFixed(2)}</span>
                    </div>
                    <div className="facet-track">
                      <div className="facet-needle" style={{ left: `${pct}%`, background: "var(--inf)" }} />
                    </div>
                  </div>
                );
              })}
              {projectEntries.length > 0 && (
                <>
                  <h2 className="card-label" style={{ marginTop: "24px" }}>PROJECT CALIBRATION</h2>
                  {projectEntries.map(([k, v]) => {
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
                  })}
                </>
              )}
            </article>

            <article className="card col-4">
              <h2 className="card-label">SWEET SPOT</h2>
              {g.sweet_spot_score !== null ? (
                <div style={{ textAlign: "center", padding: "20px 0" }}>
                  <div className="stat-val" style={{ fontSize: "64px", color: "var(--ok)" }}>
                    {g.sweet_spot_score.toFixed(2)}
                  </div>
                  <div className="mono text-dim" style={{ marginTop: "12px", fontSize: "11px" }}>
                    target 0.3 – 0.7 range<br/>higher values = stronger profile match
                  </div>
                </div>
              ) : (
                <p className="empty-state">Metric not computed.</p>
              )}

              {g.risk_flags.length > 0 && (
                <div style={{ marginTop: "24px" }}>
                  <h2 className="card-label">RISK FLAGS</h2>
                  <div className="tag-row">
                    {g.risk_flags.map((f) => (
                      <span key={f} className="tag" style={{ color: "var(--block)", borderColor: "var(--block)" }}>
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </article>
          </>
        )}

        {/* Background domains */}
        {domains.length > 0 && (
          <article className="card col-12">
            <h2 className="card-label">BACKGROUND DOMAINS</h2>
            <div className="wgrid" style={{ marginTop: "12px", gap: "10px" }}>
              {domains.map(([domain, value]) => (
                <div
                  key={domain}
                  className="card col-3"
                  style={{ background: "var(--s1)", borderStyle: "dashed" }}
                >
                  <div className="stat-key">{domain.replace(/_/g, " ")}</div>
                  <div className="mono" style={{ fontSize: "13px", marginTop: "4px" }}>
                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                  </div>
                </div>
              ))}
            </div>
          </article>
        )}

        {/* Identity files */}
        <MarkdownBlock title="SOUL.md" content={g.soul_md} />
        <MarkdownBlock title="WORLD.md" content={g.world_md} />
        <MarkdownBlock title="RELATIONSHIP POLICY" content={g.relationship_policy_md} />

      </div>

      <footer className="page-footer">Gumi Artifact · {subject_id}</footer>
    </>
  );
}
