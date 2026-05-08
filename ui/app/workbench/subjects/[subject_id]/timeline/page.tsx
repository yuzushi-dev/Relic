// Timeline Event Stream — PR27G
import { TimelineView } from "../../../../../components/TimelineView";
import { SubjectNav } from "../../../../../components/SubjectNav";
import { getEventStream, getStudyOverview } from "../../../../../lib/workbench-data";

export function generateStaticParams() {
  return getStudyOverview().subject_registry.map((subject) => ({
    subject_id: subject.subject_id.replace(/-/g, "_"),
  }));
}

export default function TimelinePage({ params }: { params: { subject_id: string } }) {
  const study = getStudyOverview();
  const eventStreamData = getEventStream(params.subject_id);

  if (!eventStreamData) {
    return (
      <>
        <SubjectNav subjects={study.subject_registry} currentSubjectId={params.subject_id} view="timeline" />
        <section className="hero">
          <div style={{ position: "relative", zIndex: 1 }}>
            <div className="eyebrow">EVENT TIMELINE · {params.subject_id}</div>
            <h1>Event Stream</h1>
            <p className="lede">No live event stream is available for this subject yet.</p>
          </div>
        </section>
        <div className="workbench-grid">
          <article className="card span-12">
            <div className="card-title">Live Data Source</div>
            <p className="analysis-copy">Demo event records are intentionally hidden in live mode.</p>
          </article>
        </div>
      </>
    );
  }

  return (
    <>
      <SubjectNav subjects={study.subject_registry} currentSubjectId={params.subject_id} view="timeline" />
      <TimelineView subjectId={params.subject_id} eventStreamData={eventStreamData} />
    </>
  );
}
