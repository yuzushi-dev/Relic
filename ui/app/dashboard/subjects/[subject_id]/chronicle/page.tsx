import { chronicleStats, chronicleEvents, chronicleDecisions, getStudyOverview } from "@/lib/workbench-data";
import { StatsPanel } from "@/components/chronicle/StatsPanel";
import { EventsTable } from "@/components/chronicle/EventsTable";
import { DecisionsList } from "@/components/chronicle/DecisionsList";
import { SubjectNav } from "@/components/SubjectNav";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export function generateStaticParams() {
  return getStudyOverview().subject_registry.map((s) => ({
    subject_id: s.subject_id.replace(/-/g, "_"),
  }));
}

export default async function ChroniclePage({
  params,
}: {
  params: Promise<{ subject_id: string }>;
}) {
  const { subject_id } = await params;
  const study = getStudyOverview();
  const [stats, recentEvents, recentDecisions] = await Promise.all([
    Promise.resolve(chronicleStats(subject_id)),
    Promise.resolve(chronicleEvents(subject_id, { limit: 5 })),
    Promise.resolve(chronicleDecisions(subject_id, { limit: 3 })),
  ]);

  const statsData = stats ?? {
    subject_id,
    total_events: 0,
    total_decisions: 0,
    total_snapshots: 0,
    by_category: {},
    by_severity: {},
    by_sensitivity: {},
    first_event_at: null,
    last_event_at: null,
  };

  return (
    <div className="space-y-8">
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="chronicle" />
      
      {/* Page Header */}
      <header className="border-b border-border pb-5">
        <div className="text-xs font-mono uppercase tracking-widest text-primary mb-1">Chronicle Audit Trail</div>
        <h1 className="text-3xl font-bold tracking-tight font-mono mb-2">Event & Decision History</h1>
        <p className="text-xs text-muted-foreground font-mono">
          Auditable event logs for subject: <strong className="text-foreground">{subject_id}</strong>
        </p>
      </header>

      {/* Stats Summary Panel */}
      <StatsPanel stats={statsData} />

      {/* Recent Events Card */}
      <Card className="rounded-none border-border">
        <CardHeader className="border-b border-border flex flex-row items-center justify-between p-4">
          <div>
            <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Recent Events</CardTitle>
          </div>
          <Link href={`/dashboard/subjects/${subject_id}/chronicle/events`} className="text-xs text-primary hover:underline font-mono">
            View All Events →
          </Link>
        </CardHeader>
        <CardContent className="p-0">
          <EventsTable events={recentEvents.events} />
        </CardContent>
      </Card>

      {/* Recent Decisions Card */}
      <Card className="rounded-none border-border">
        <CardHeader className="border-b border-border flex flex-row items-center justify-between p-4">
          <div>
            <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Recent Decisions</CardTitle>
          </div>
          <Link href={`/dashboard/subjects/${subject_id}/chronicle/decisions`} className="text-xs text-primary hover:underline font-mono">
            View All Decisions →
          </Link>
        </CardHeader>
        <CardContent className="p-4">
          <DecisionsList decisions={recentDecisions.decisions} />
        </CardContent>
      </Card>
    </div>
  );
}
