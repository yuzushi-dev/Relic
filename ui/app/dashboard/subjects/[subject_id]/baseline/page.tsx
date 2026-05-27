// Subject Baseline — PR27D
import { formatDate } from "../../../../../lib/format";
import { SubjectNav } from "../../../../../components/SubjectNav";
import { getGumiProfile, getStudyOverview, getSubjectBaseline } from "../../../../../lib/workbench-data";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../../../../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../../../components/ui/table";
import { Badge } from "../../../../../components/ui/badge";

type FieldValue = {
  value?: string | number;
  values?: string[];
  origin: string;
};

function flattenFields(group: Record<string, FieldValue>, section: string) {
  return Object.entries(group).map(([name, field]) => {
    let value: string;
    if (field.values) {
      value = field.values.join(", ");
    } else if (field.value !== null && field.value !== undefined && typeof field.value === "object") {
      // Nested object (e.g. psychological_scores dict): render as "key: val" pairs
      value = Object.entries(field.value as Record<string, unknown>)
        .map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "number" ? (v as number).toFixed(2) : String(v)}`)
        .join(" · ");
    } else {
      value = String(field.value ?? "--");
    }
    return { name, value, origin: field.origin, section };
  });
}

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
      <div className="space-y-6">
        <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="baseline" />
        <header className="border-b border-border pb-5">
          <div className="text-xs font-mono uppercase tracking-widest text-destructive mb-1">BASELINE PROFILE</div>
          <h1 className="text-3xl font-bold tracking-tight font-mono mb-2">{subject_id}</h1>
          <p className="text-sm text-muted-foreground">No live baseline artifact is available for this subject yet.</p>
        </header>
        <Card className="rounded-none border-border">
          <CardHeader>
            <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Live Data Source</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">Demo baseline fields are intentionally hidden in live mode.</p>
          </CardContent>
        </Card>
      </div>
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
    <div className="space-y-8">
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="baseline" />
      
      {/* Page Header */}
      <header className="border-b border-border pb-5">
        <div className="text-xs font-mono uppercase tracking-widest text-primary mb-1">Baseline Profile · Version {d.baseline_version}</div>
        <h1 className="text-3xl font-bold tracking-tight font-mono mb-2">{d.subject_id}</h1>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground font-mono">
          <span>Method: <Badge variant="warning" className="rounded-none">{d.baseline_method}</Badge></span>
          <span>•</span>
          <span>Created: {formatDate(d.creation_date)}</span>
        </div>
      </header>

      {/* Main Registry Fields */}
      <Card className="rounded-none border-border">
        <CardHeader className="border-b border-border">
          <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Baseline Profile Fields</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/10">
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Field</TableHead>
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Value</TableHead>
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Origin</TableHead>
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Section</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {fields.map((f) => {
                  const originVariant = f.origin === "subject-stated" ? "success" : f.origin === "researcher-coded" ? "default" : "secondary";
                  return (
                    <TableRow key={f.name} className="hover:bg-muted/30">
                      <TableCell className="font-mono text-xs text-muted-foreground capitalize">
                        {f.name.replace(/_/g, " ")}
                      </TableCell>
                      <TableCell className="text-sm font-medium">{f.value}</TableCell>
                      <TableCell>
                        <Badge variant={originVariant} className="rounded-none font-mono text-[9px] uppercase">
                          {f.origin}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{f.section}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Flags & Info */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {d.risk_flags.length > 0 && (
          <Card className="rounded-none border-border md:col-span-6">
            <CardHeader className="border-b border-border">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Risk Flags</CardTitle>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-border">
              {d.risk_flags.map((f) => {
                const badgeVariant = f.severity === "high" ? "destructive" : "warning";
                return (
                  <div key={f.flag_category} className="p-4 flex justify-between items-center text-sm">
                    <span className="font-mono text-foreground font-medium">{f.flag_category}</span>
                    <Badge variant={badgeVariant} className="rounded-none font-mono text-[10px] uppercase">
                      {f.severity}
                    </Badge>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        )}

        <Card className={`rounded-none border-border ${d.risk_flags.length > 0 ? "md:col-span-6" : "col-span-12"}`}>
          <CardHeader className="border-b border-border">
            <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Version Information</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 pt-4">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">Baseline Version</div>
              <div className="font-mono text-lg font-bold">{d.baseline_version}</div>
            </div>
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">Creation Date</div>
              <div className="font-mono text-lg font-bold">{formatDate(d.creation_date)}</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Battery Scores if available */}
      {gumiProfile?.item_battery_scores && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="rounded-none border-border">
            <CardHeader className="border-b border-border">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">TIPI — BIG FIVE</CardTitle>
            </CardHeader>
            <CardContent className="divide-y divide-border pt-4">
              {Object.entries(gumiProfile.item_battery_scores.tipi).map(([k, v]) => {
                const label = { extraversion: "Extraversion", agreeableness: "Agreeableness", conscientiousness: "Conscientiousness", emotional_stability: "Emotional Stability", openness: "Openness" }[k] ?? k;
                return (
                  <CalibrationSlider key={k} label={label} value={v} max={7} color="bg-primary" />
                );
              })}
            </CardContent>
          </Card>

          <Card className="rounded-none border-border">
            <CardHeader className="border-b border-border">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">ECR-RS — ATTACHMENT</CardTitle>
            </CardHeader>
            <CardContent className="divide-y divide-border pt-4">
              {Object.entries(gumiProfile.item_battery_scores.ecrrs).map(([k, v]) => {
                const label = { anxiety: "Anxiety", avoidance: "Avoidance" }[k] ?? k;
                return (
                  <CalibrationSlider key={k} label={label} value={v} max={7} color="bg-info" />
                );
              })}
            </CardContent>
          </Card>

          <Card className="rounded-none border-border">
            <CardHeader className="border-b border-border">
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Project Calibration</CardTitle>
            </CardHeader>
            <CardContent className="divide-y divide-border pt-4">
              {Object.entries(gumiProfile.item_battery_scores.project_calibration).length > 0 ? (
                Object.entries(gumiProfile.item_battery_scores.project_calibration).map(([k, v]) => (
                  <CalibrationSlider key={k} label={k.replace(/_/g, " ")} value={v} max={10} color="bg-gumi" />
                ))
              ) : (
                <p className="text-xs text-muted-foreground italic pt-4 text-center">No project scores calibrated.</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <footer className="text-[10px] text-muted-foreground font-mono text-center pt-8 border-t border-border">
        Baseline Artifact · Subject Scope: {d.subject_id}
      </footer>
    </div>
  );
}
