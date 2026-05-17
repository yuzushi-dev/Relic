// Timeline Event Stream — PR27G
export const dynamic = process.env.RELIC_UI_BUILD_TARGET === 'static' ? 'force-static' : 'force-dynamic'

export async function generateStaticParams() {
  if (process.env.RELIC_UI_BUILD_TARGET !== 'static') return [];
  return [{ subject_id: 'subj_001' }];
}
import { TimelineView } from "../../../../../components/TimelineView";
import { SubjectNav } from "../../../../../components/SubjectNav";
import { getEventStream, getStudyOverview } from "../../../../../lib/workbench-data";

export function generateStaticParams() {
  return getStudyOverview().subject_registry.map((subject) => ({
    subject_id: subject.subject_id.replace(/-/g, "_"),
  }));
}

export default async function TimelinePage({ params }: { params: Promise<{ subject_id: string }> }) {
  const { subject_id } = await params;
  const study = getStudyOverview();
  const eventStreamData = getEventStream(subject_id);

  if (!eventStreamData) {
    return (
      <>
        <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="timeline" />
      <header className="page-header">
        <div className="page-eyebrow">Subject History · {subject_id}</div>
        <h1 className="page-title">Event Timeline</h1>
        <p className="page-meta">No live event stream available</p>
      </header>
      <div className="wgrid">
        <article className="card col-12">
          <h2 className="card-label">Live Data Source</h2>
          <p className="empty-state">Demo event records are intentionally hidden in live mode.</p>
        </article>
      </div>
      </>
    );
  }

  return (
    <>
      <SubjectNav subjects={study.subject_registry} currentSubjectId={subject_id} view="timeline" />
      <TimelineView subjectId={subject_id} eventStreamData={eventStreamData} />
    </>
  );
}
