import Link from "next/link";
import type { StudyOverview } from "../lib/workbench-data";

type Props = {
  subjects: StudyOverview["subject_registry"];
  currentSubjectId: string;
  view: "baseline" | "timeline" | "gumi" | "overview";
};

const VIEW_SUFFIX: Record<Props["view"], string> = {
  overview: "",
  baseline: "/baseline",
  timeline: "/timeline",
  gumi: "/gumi",
};

export function SubjectNav({ subjects, currentSubjectId, view }: Props) {
  return (
    <nav className="filter-bar" style={{ marginBottom: 0, borderBottom: "none", background: "transparent" }}>
      <span className="filter-label">Quick Switch</span>
      {subjects.map((s) => {
        const slug = s.subject_id.replace(/-/g, "_");
        const isCurrent = slug === currentSubjectId || s.subject_id === currentSubjectId;
        return (
          <Link
            key={s.subject_id}
            href={`/workbench/subjects/${slug}${VIEW_SUFFIX[view]}` as any}
            className={`filter-btn ${isCurrent ? "active" : ""}`}
            style={{ textDecoration: "none" }}
          >
            {s.subject_id}
          </Link>
        );
      })}
    </nav>
  );
}
