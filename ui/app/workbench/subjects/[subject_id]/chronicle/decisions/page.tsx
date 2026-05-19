import { chronicleDecisions, getStudyOverview } from "@/lib/workbench-data";
import { DecisionsList } from "@/components/chronicle/DecisionsList";
import { DecisionsFilters } from "@/components/chronicle/DecisionsFilters";
import { SubjectNav } from "@/components/SubjectNav";

export const dynamic = "force-dynamic";

export async function generateStaticParams() {
  return getStudyOverview().subject_registry.map((s) => ({
    subject_id: s.subject_id.replace(/-/g, "_"),
  }));
}

export default async function ChronicleDecisionsPage({
  params,
  searchParams,
}: {
  params: Promise<{ subject_id: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { subject_id } = await params;
  const sp = await searchParams;
  const study = getStudyOverview();
  const result = chronicleDecisions(subject_id, {
    validation_status: sp.validation_status,
    min_confidence: sp.min_confidence ? Number(sp.min_confidence) : undefined,
    limit: 200,
  });

  return (
    <>
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="chronicle" />
      <div className="space-y-4">
        <header>
          <div className="page-eyebrow">Chronicle</div>
          <h1 className="page-title">Decisions</h1>
          <div className="page-meta">
            {result.total > 0 && <span>{result.decisions.length} shown of {result.total}</span>}
          </div>
        </header>
        <DecisionsFilters />
        <DecisionsList decisions={result.decisions} />
      </div>
    </>
  );
}
