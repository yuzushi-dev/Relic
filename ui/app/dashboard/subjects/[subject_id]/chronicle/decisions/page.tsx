import { chronicleDecisions, getStudyOverview } from "@/lib/workbench-data";
import { DecisionsList } from "@/components/chronicle/DecisionsList";
import { DecisionsFilters } from "@/components/chronicle/DecisionsFilters";
import { SubjectNav } from "@/components/SubjectNav";

export function generateStaticParams() {
  return getStudyOverview().subject_registry.map((s) => ({
    subject_id: s.subject_id.replace(/-/g, "_"),
  }));
}

export default async function ChronicleDecisionsPage({
  params,
}: {
  params: Promise<{ subject_id: string }>;
}) {
  const { subject_id } = await params;
  const study = getStudyOverview();
  const result = chronicleDecisions(subject_id, { limit: 200 });

  return (
    <div className="space-y-8">
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="chronicle" />
      
      {/* Page Header */}
      <header className="border-b border-border pb-5">
        <div className="text-xs font-mono uppercase tracking-widest text-primary mb-1">Chronicle Audit Trail</div>
        <h1 className="text-3xl font-bold tracking-tight font-mono mb-2">Decisions History</h1>
        <p className="text-xs text-muted-foreground font-mono">
          {result.total > 0 && <span>Showing {result.decisions.length} of {result.total} recorded decisions</span>}
        </p>
      </header>

      <DecisionsFilters />
      <DecisionsList decisions={result.decisions} />
    </div>
  );
}
