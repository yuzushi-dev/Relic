// Subject Overview — PR27C
import Link from "next/link";
import { SubjectIntelligence } from "../../../../components/SubjectIntelligence";
import { formatDate } from "../../../../lib/format";
import { getGumiProfile, getStudyOverview, getSubjectIntelligence, getSubjectOverview } from "../../../../lib/workbench-data";
import { Badge } from "../../../../components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../../components/ui/card";

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
      <div className="space-y-6">
        <header className="border-b border-border pb-5">
          <div className="text-xs font-mono uppercase tracking-widest text-destructive mb-1">Subject profile</div>
          <h1 className="text-3xl font-bold tracking-tight font-mono mb-2">{subject_id}</h1>
          <p className="text-sm text-muted-foreground">No live subject profile was found for this id.</p>
        </header>
        <Card className="rounded-none border-border">
          <CardHeader>
            <CardTitle className="font-mono text-sm font-semibold uppercase tracking-wider">Live Data Source</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground font-mono">Expected `$RELIC_HOME/subjects/{subject_id}/subject_profile.json`.</p>
          </CardContent>
        </Card>
      </div>
    );
  }
  const prov = d.hermes_profile_status;
  const subjectIntelligence = getSubjectIntelligence(subject_id);
  const gumiProfile = getGumiProfile(subject_id);

  const statusVariant = d.subject_status === "active" ? "success" : "secondary";
  const conditionVariant = d.active_condition ? "warning" : "secondary";
  const consentVariant = d.consent_status === "consented" ? "success" : "destructive";

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <header className="border-b border-border pb-5">
        <div className="text-xs font-mono uppercase tracking-widest text-primary mb-1">
          Subject Profile · {d.experiment_id}
        </div>
        <h1 className="text-3xl font-bold tracking-tight font-mono mb-3">{d.subject_id}</h1>
        <div className="flex flex-wrap gap-3 items-center text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Status:</span>
            <Badge variant={statusVariant} className="rounded-none capitalize">{d.subject_status}</Badge>
          </div>
          <span className="text-muted-foreground">•</span>
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Condition:</span>
            <Badge variant={conditionVariant} className="rounded-none">{d.active_condition}</Badge>
          </div>
          <span className="text-muted-foreground">•</span>
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Consent:</span>
            <Badge variant={consentVariant} className="rounded-none capitalize">{d.consent_status}</Badge>
          </div>
        </div>
      </header>

      {/* Summary Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" role="region" aria-label="Subject Summary">
        {[
          { label: "Gumi Instance", value: d.active_gumi_instance },
          { label: "Hermes Profile", value: prov.profile_name },
          { label: "Last Interaction", value: formatDate(d.last_user_interaction) },
          { label: "Pending Reviews", value: d.pending_review_count, isWarning: d.pending_review_count > 0 },
        ].map((s) => (
          <Card key={s.label} className="rounded-none border-border">
            <CardHeader className="p-4 pb-1">
              <CardDescription className="text-[10px] font-semibold uppercase tracking-wider">{s.label}</CardDescription>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className={`text-sm font-semibold font-mono truncate ${s.isWarning ? "text-warning" : "text-foreground"}`}>
                {s.value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Subject-specific navigation links for convenience */}
      <Card className="rounded-none border-border p-3 bg-muted/20">
        <div className="flex flex-wrap gap-2">
          {[
            { href: `/dashboard/subjects/${d.subject_id}/baseline`, label: "Baseline Profile" },
            { href: `/dashboard/subjects/${d.subject_id}/timeline`, label: "Event Timeline" },
            { href: `/dashboard/subjects/${d.subject_id}/gumi`, label: "Gumi Profile" },
            { href: `/dashboard/subjects/${d.subject_id}/chronicle`, label: "Chronicle Log" },
          ].map((link) => (
            <Link
              key={link.href}
              href={link.href as any}
              className="inline-flex items-center justify-center whitespace-nowrap text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring border h-8 px-3 border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </Card>

      {/* Subject Intelligence tabs */}
      <SubjectIntelligence subjectIntelligence={subjectIntelligence} />

      {/* Runtime Status (compact single card) */}
      <Card className="rounded-none border-border">
        <CardHeader className="pb-2">
          <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Runtime Status</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-3 text-xs font-mono">
            <div>
              <dt className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Hermes Profile</dt>
              <dd className="flex items-center gap-1.5">
                <Badge variant={prov.provisioned ? "success" : "destructive"} className="rounded-none text-[10px]">
                  {prov.provisioned ? "OK" : "Missing"}
                </Badge>
                <span className="text-muted-foreground truncate max-w-[120px]">{prov.profile_name}</span>
              </dd>
            </div>
            <div>
              <dt className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Bootstrap</dt>
              <dd><Badge variant="success" className="rounded-none text-[10px]">{d.bootstrap_status}</Badge></dd>
            </div>
            <div>
              <dt className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Risk</dt>
              <dd className="flex items-center gap-1.5">
                <Badge variant={d.risk_summary.severity !== "none" ? "destructive" : "success"} className="rounded-none text-[10px] uppercase">
                  {d.risk_summary.severity}
                </Badge>
                {d.risk_summary.flag_count > 0 && (
                  <span className="text-muted-foreground">{d.risk_summary.flag_count} flags</span>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Cron Modes</dt>
              <dd className="flex flex-wrap gap-1">
                {d.active_cron_modes.length > 0
                  ? d.active_cron_modes.map((m) => (
                      <Badge key={m} variant="outline" className="rounded-none text-[10px]">{m}</Badge>
                    ))
                  : <span className="text-muted-foreground italic">none</span>
                }
              </dd>
            </div>
            <div className="md:col-span-4">
              <dt className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Pause State</dt>
              <dd className="flex flex-wrap gap-1">
                {Object.entries(d.pause_state).filter(([, v]) => v).map(([k]) => (
                  <Badge key={k} variant="destructive" className="rounded-none text-[10px] uppercase">{k}</Badge>
                ))}
                {Object.values(d.pause_state).every((v) => !v) && (
                  <span className="text-muted-foreground italic">All components active</span>
                )}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Gumi Agent card */}
      <div className="grid grid-cols-1 gap-6">
        {gumiProfile && (
          <Card className="rounded-none border-border md:col-span-3">
            <CardHeader>
              <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                Gumi Agent · {gumiProfile.agent_name}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div className="space-y-3">
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="outline" className="rounded-none font-mono text-[10px]">
                    {gumiProfile.generation_mode}
                  </Badge>
                  {gumiProfile.sweet_spot_score !== null && (
                    <Badge variant="success" className="rounded-none font-mono text-[10px]">
                      Score: {gumiProfile.sweet_spot_score.toFixed(3)}
                    </Badge>
                  )}
                </div>
                {gumiProfile.soul_md && (
                  <p className="text-xs text-muted-foreground leading-relaxed max-w-3xl italic">
                    "{gumiProfile.soul_md.split("\n").slice(0, 3).join(" ")}..."
                  </p>
                )}
              </div>
              <Link
                href={`/dashboard/subjects/${d.subject_id}/gumi`}
                className="inline-flex items-center justify-center whitespace-nowrap text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring border h-9 px-4 border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground shrink-0"
              >
                View Agent Details →
              </Link>
            </CardContent>
          </Card>
        )}
      </div>

      <footer className="text-[10px] text-muted-foreground font-mono text-center pt-8 border-t border-border">
        Subject Scope: {d.subject_id}
      </footer>
    </div>
  );
}
