import { chronicleSnapshots, getStudyOverview } from "@/lib/workbench-data";
import { SnapshotsList } from "@/components/chronicle/SnapshotsList";
import { SubjectNav } from "@/components/SubjectNav";

export const dynamic = "force-dynamic";

export async function generateStaticParams() {
  return getStudyOverview().subject_registry.map((s) => ({
    subject_id: s.subject_id.replace(/-/g, "_"),
  }));
}

export default async function ChronicleSnapshotsPage({
  params,
}: {
  params: Promise<{ subject_id: string }>;
}) {
  const { subject_id } = await params;
  const study = getStudyOverview();
  const result = chronicleSnapshots(subject_id, { limit: 200 });

  return (
    <>
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="chronicle" />
      <div className="space-y-4">
        <header>
          <div className="page-eyebrow">Chronicle</div>
          <h1 className="page-title">Snapshots</h1>
          <div className="page-meta">
            {result.total > 0 && <span>{result.snapshots.length} snapshots recorded</span>}
          </div>
        </header>
        <SnapshotsList snapshots={result.snapshots} />
      </div>
    </>
  );
}
