import { chronicleStats, chronicleEvents, chronicleDecisions, getStudyOverview } from "@/lib/workbench-data";
import { StatsPanel } from "@/components/chronicle/StatsPanel";
import { EventsTable } from "@/components/chronicle/EventsTable";
import { DecisionsList } from "@/components/chronicle/DecisionsList";
import { SubjectNav } from "@/components/SubjectNav";
import Link from "next/link";

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
    <>
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="chronicle" />
      <div className="space-y-8">
        <header>
          <div className="page-eyebrow">Chronicle</div>
          <h1 className="page-title">Event & Decision Trail</h1>
          <p className="page-meta">
            Auditable trail for subject <span className="font-mono">{subject_id}</span>
          </p>
        </header>

        <StatsPanel stats={statsData} />

        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="card-label">Recent events</h2>
            <Link
              href={`/workbench/subjects/${subject_id}/chronicle/events` as any}
              className="text-sm text-blue-600 hover:underline"
            >
              View all →
            </Link>
          </div>
          <EventsTable events={recentEvents.events} />
        </section>

        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="card-label">Recent decisions</h2>
            <Link
              href={`/workbench/subjects/${subject_id}/chronicle/decisions` as any}
              className="text-sm text-blue-600 hover:underline"
            >
              View all →
            </Link>
          </div>
          <DecisionsList decisions={recentDecisions.decisions} />
        </section>
      </div>
    </>
  );
}
