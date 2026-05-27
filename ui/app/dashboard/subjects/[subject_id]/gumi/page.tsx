// Gumi Identity — Profile files + item battery scores
import { formatDate } from "../../../../../lib/format";
import { SubjectNav } from "../../../../../components/SubjectNav";
import { getGumiProfile, getStudyOverview } from "../../../../../lib/workbench-data";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../../../../components/ui/card";
import { Badge } from "../../../../../components/ui/badge";

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

function CalibrationSlider({ label, value, max = 7, color = "bg-primary" }: { label: string; value: number; max?: number; color?: string }) {
  const pct = Math.min(100, Math.max(0, Math.round((value / max) * 100)));
  return (
    <div className="py-2 space-y-1.5">
      <div className="flex justify-between items-center text-xs font-mono">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold text-foreground">{value.toFixed(2)}</span>
      </div>
      <div className="h-2 w-full bg-muted border border-border rounded-none relative">
        <div 
          className={`absolute top-0 bottom-0 w-1.5 ${color}`} 
          style={{ left: `${pct}%`, transform: 'translateX(-50%)' }} 
        />
      </div>
    </div>
  );
}

function MarkdownBlock({ title, content }: { title: string; content: string | null }) {
  const fileContent = content === null ? "File not found." : content.trim() === "" ? "Empty." : content;
  return (
    <Card className="col-span-12 rounded-none border-border">
      <CardHeader className="border-b border-border">
        <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <pre className="font-mono text-xs p-4 bg-muted/40 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-96 text-foreground">
          {fileContent}
        </pre>
      </CardContent>
    </Card>
  );
}

export default async function GumiPage({ params }: { params: Promise<{ subject_id: string }> }) {
  const { subject_id } = await params;
  const study = getStudyOverview();
  const g = getGumiProfile(subject_id);

  if (!g) {
    return (
      <div className="space-y-6">
        <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="gumi" />
        <header className="border-b border-border pb-5">
          <div className="text-xs font-mono uppercase tracking-widest text-destructive mb-1">GUMI PROFILE</div>
          <h1 className="text-3xl font-bold tracking-tight font-mono mb-2">{subject_id}</h1>
          <p className="text-sm text-muted-foreground">No Gumi profile found. Run <code>relic subject</code> to provision.</p>
        </header>
        <Card className="rounded-none border-border">
          <CardHeader>
            <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Live Data Source</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Available only in live mode with RELIC_HOME set.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const domains = Object.entries(g.domains);
  const tipiEntries = g.item_battery_scores ? Object.entries(g.item_battery_scores.tipi) : [];
  const ecrrsEntries = g.item_battery_scores ? Object.entries(g.item_battery_scores.ecrrs) : [];
  const projectEntries = g.item_battery_scores ? Object.entries(g.item_battery_scores.project_calibration) : [];

  return (
    <div className="space-y-8">
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="gumi" />
      
      {/* Page Header */}
      <header className="border-b border-border pb-5">
        <div className="text-xs font-mono uppercase tracking-widest text-primary mb-1">Gumi Agent Profile · {subject_id}</div>
        <h1 className="text-3xl font-bold tracking-tight font-mono mb-2">{g.agent_name}</h1>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground font-mono">
          <span>Mode: <Badge variant="warning" className="rounded-none">{g.generation_mode.toUpperCase()}</Badge></span>
          {g.sweet_spot_score !== null && (
            <>
              <span>•</span>
              <span>Sweet Spot Score: <Badge variant="success" className="rounded-none">{g.sweet_spot_score.toFixed(3)}</Badge></span>
            </>
          )}
          {g.created_at && (
            <>
              <span>•</span>
              <span>Created: {formatDate(g.created_at)}</span>
            </>
          )}
        </div>
      </header>

      {/* Grid of battery scores */}
      {g.item_battery_scores && (
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* TIPI Card */}
          <Card className="rounded-none border-border md:col-span-4">
            <CardHeader className="border-b border-border">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">TIPI — BIG FIVE</CardTitle>
            </CardHeader>
            <CardContent className="divide-y divide-border pt-4">
              {tipiEntries.map(([k, v]) => (
                <CalibrationSlider key={k} label={TIPI_LABELS[k] ?? k} value={v} max={7} color="bg-primary" />
              ))}
            </CardContent>
          </Card>

          {/* ECR-RS Card */}
          <Card className="rounded-none border-border md:col-span-4">
            <CardHeader className="border-b border-border">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">ECR-RS — ATTACHMENT</CardTitle>
            </CardHeader>
            <CardContent className="divide-y divide-border pt-4">
              {ecrrsEntries.map(([k, v]) => (
                <CalibrationSlider key={k} label={ECRRS_LABELS[k] ?? k} value={v} max={7} color="bg-info" />
              ))}
            </CardContent>
          </Card>

          {/* Sweet Spot Card */}
          <Card className="rounded-none border-border md:col-span-4">
            <CardHeader className="border-b border-border">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">SWEET SPOT</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center justify-center py-6 text-center">
              {g.sweet_spot_score !== null ? (
                <>
                  <div className="text-5xl font-bold text-success font-mono tracking-tight">
                    {g.sweet_spot_score.toFixed(2)}
                  </div>
                  <div className="font-mono text-[10px] text-muted-foreground mt-4 leading-relaxed">
                    target 0.3 – 0.7 range<br/>higher values = stronger profile match
                  </div>
                </>
              ) : (
                <span className="text-xs text-muted-foreground italic">Metric not computed.</span>
              )}

              {g.risk_flags.length > 0 && (
                <div className="w-full mt-6 pt-6 border-t border-border">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block mb-2">RISK FLAGS</span>
                  <div className="flex flex-wrap justify-center gap-1.5">
                    {g.risk_flags.map((f) => (
                      <Badge key={f} variant="destructive" className="rounded-none font-mono text-[9px] uppercase">
                        {f}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Project Calibration Card (in a wider block below standard traits if present) */}
          {projectEntries.length > 0 && (
            <Card className="rounded-none border-border col-span-12">
              <CardHeader className="border-b border-border">
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">PROJECT CALIBRATION</CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {projectEntries.map(([k, v]) => (
                    <CalibrationSlider key={k} label={k.replace(/_/g, " ")} value={v} max={10} color="bg-gumi" />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Background domains */}
      {domains.length > 0 && (
        <Card className="rounded-none border-border">
          <CardHeader className="border-b border-border">
            <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">BACKGROUND DOMAINS</CardTitle>
          </CardHeader>
          <CardContent className="p-4 bg-muted/20">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {domains.map(([domain, value]) => (
                <Card key={domain} className="rounded-none border-border bg-card border-dashed p-3 flex flex-col justify-start">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-primary border-b border-border pb-1 mb-2 font-mono">
                    {domain.replace(/_/g, " ")}
                  </div>
                  {typeof value === "object" && value !== null ? (
                    <ul className="space-y-2 text-xs font-mono">
                      {Object.entries(value).map(([k, v]) => (
                        <li key={k} className="leading-snug">
                          <span className="text-muted-foreground text-[9px] uppercase tracking-wider block font-semibold">
                            {k.replace(/_/g, " ")}
                          </span>
                          <span className="text-foreground text-xs">
                            {Array.isArray(v) ? v.join(", ") : String(v)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="font-mono text-xs text-foreground leading-normal">
                      {String(value)}
                    </div>
                  )}
                </Card>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Identity files */}
      <div className="grid grid-cols-1 gap-6">
        <MarkdownBlock title="SOUL.md" content={g.soul_md} />
        <MarkdownBlock title="WORLD.md" content={g.world_md} />
        <MarkdownBlock title="RELATIONSHIP POLICY" content={g.relationship_policy_md} />
      </div>

      <footer className="text-[10px] text-muted-foreground font-mono text-center pt-8 border-t border-border">
        Gumi Artifact · {subject_id}
      </footer>
    </div>
  );
}
