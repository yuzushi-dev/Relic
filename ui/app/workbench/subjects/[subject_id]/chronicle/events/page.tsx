import { chronicleEvents, getStudyOverview } from "@/lib/workbench-data";
import { EventsTable } from "@/components/chronicle/EventsTable";
import { EventsFilters } from "@/components/chronicle/EventsFilters";
import { SubjectNav } from "@/components/SubjectNav";

export const dynamic = "force-dynamic";

export async function generateStaticParams() {
  return getStudyOverview().subject_registry.map((s) => ({
    subject_id: s.subject_id.replace(/-/g, "_"),
  }));
}

export default async function ChronicleEventsPage({
  params,
  searchParams,
}: {
  params: Promise<{ subject_id: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { subject_id } = await params;
  const sp = await searchParams;
  const study = getStudyOverview();
  const result = chronicleEvents(subject_id, {
    category: sp.category,
    severity: sp.severity,
    sensitivity: sp.sensitivity,
    from: sp.from,
    to: sp.to,
    limit: 200,
  });

  return (
    <>
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="chronicle" />
      <div className="space-y-4">
        <header>
          <div className="page-eyebrow">Chronicle</div>
          <h1 className="page-title">Events</h1>
          <div className="page-meta">
            {result.total > 0 && <span>{result.events.length} shown of {result.total}</span>}
          </div>
        </header>
        <EventsFilters />
        <EventsTable events={result.events} />
      </div>
    </>
  );
}
