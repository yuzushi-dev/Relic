// Gumi Identity — Profile files + item battery scores
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
  if (!content) {
    return (
      <div className="card span-12">
        <div className="card-title">{title}</div>
        <p style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>File not found.</p>
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

export default function GumiPage({ params }: { params: { subject_id: string } }) {
  const study = getStudyOverview();
  const g = getGumiProfile(params.subject_id);

  if (!g) {
    return (
      <>
        <SubjectNav subjects={study.subject_registry} currentSubjectId={params.subject_id} view="gumi" />
        <section className="hero">
          <div style={{ position: "relative", zIndex: 1 }}>
            <div className="eyebrow">GUMI PROFILE</div>
            <h1>{params.subject_id}</h1>
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
      <SubjectNav subjects={study.subject_registry} currentSubjectId={params.subject_id} view="gumi" />
      <section className="hero">
        <div className="hero-grid">
          <div>
            <div className="eyebrow">GUMI PROFILE · {params.subject_id}</div>
            <h1>{g.agent_name}</h1>
            <p className="lede">
              Mode: <span style={{ color: "var(--gold)" }}>{g.generation_mode}</span>
              {g.sweet_spot_score !== null && (
                <>
                  {" · "}Sweet Spot:{" "}
                  <span style={{ color: "#84d1a4" }}>{g.sweet_spot_score.toFixed(3)}</span>
                </>
              )}
              {g.created_at && <>{" · "}Created {formatDate(g.created_at)}</>}
            </p>
          </div>
          {g.risk_flags.length > 0 && (
            <aside className="hero-side">
              <div className="eyebrow">Risk flags</div>
              <div className="token-row" style={{ marginTop: "14px" }}>
                {g.risk_flags.map((f) => (
                  <span key={f} className="token" style={{ borderColor: "#fbbf24", color: "#fbbf24" }}>
                    {f}
                  </span>
                ))}
              </div>
            </aside>
          )}
        </div>
      </section>

      <div className="workbench-grid">

        {/* Item battery scores */}
        {g.item_battery_scores && (
          <>
            <div className="card span-4">
              <div className="card-title">TIPI — BIG FIVE</div>
              {tipiEntries.map(([k, v]) => (
                <ScoreBar key={k} label={TIPI_LABELS[k] ?? k} value={v} max={7} />
              ))}
            </div>

            <div className="card span-4">
              <div className="card-title">ECR-RS — ATTACHMENT</div>
              {ecrrsEntries.map(([k, v]) => (
                <ScoreBar key={k} label={ECRRS_LABELS[k] ?? k} value={v} max={7} />
              ))}
              {projectEntries.length > 0 && (
                <>
                  <div className="card-title" style={{ marginTop: "16px" }}>PROJECT CALIBRATION</div>
                  {projectEntries.map(([k, v]) => (
                    <ScoreBar key={k} label={k.replace(/_/g, " ")} value={v} max={10} />
                  ))}
                </>
              )}
            </div>

            <div className="card span-4">
              <div className="card-title">SWEET SPOT</div>
              {g.sweet_spot_score !== null ? (
                <>
                  <div style={{ fontFamily: "var(--head)", fontSize: "48px", color: "#84d1a4" }}>
                    {g.sweet_spot_score.toFixed(2)}
                  </div>
                  <div style={{ fontFamily: "var(--mono)", fontSize: "11px", color: "var(--text-muted)", marginTop: "6px" }}>
                    target 0.3 – 0.7 · higher = stronger match
                  </div>
                </>
              ) : (
                <p style={{ fontFamily: "var(--mono)", fontSize: "12px", color: "var(--text-muted)" }}>Not computed.</p>
              )}
            </div>
          </>
        )}

        {/* Background domains */}
        {domains.length > 0 && (
          <div className="card span-12">
            <div className="card-title">BACKGROUND DOMAINS</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "10px", marginTop: "8px" }}>
              {domains.map(([domain, value]) => (
                <div
                  key={domain}
                  style={{
                    padding: "10px 14px",
                    background: "var(--panel)",
                    border: "1px solid var(--border)",
                    borderRadius: "4px",
                  }}
                >
                  <div style={{ fontFamily: "var(--mono)", fontSize: "10px", color: "var(--gold)", textTransform: "uppercase", letterSpacing: ".1em", marginBottom: "4px" }}>
                    {domain.replace(/_/g, " ")}
                  </div>
                  <div style={{ fontFamily: "var(--mono)", fontSize: "13px" }}>
                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Identity files */}
        <MarkdownBlock title="SOUL.md" content={g.soul_md} />
        <MarkdownBlock title="WORLD.md" content={g.world_md} />
        <MarkdownBlock title="RELATIONSHIP POLICY" content={g.relationship_policy_md} />

      </div>

      <div className="footer">Gumi profile · {params.subject_id}</div>
    </>
  );
}
