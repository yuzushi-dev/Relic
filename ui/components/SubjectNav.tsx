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
    <nav
      style={{
        display: "flex",
        gap: "6px",
        flexWrap: "wrap",
        padding: "10px 0",
        borderBottom: "1px solid var(--border)",
        marginBottom: "0",
      }}
    >
      {subjects.map((s) => {
        const slug = s.subject_id.replace(/-/g, "_");
        const isCurrent = slug === currentSubjectId || s.subject_id === currentSubjectId;
        return (
          <Link
            key={s.subject_id}
            href={`/workbench/subjects/${slug}${VIEW_SUFFIX[view]}` as any}
            style={{
              fontFamily: "var(--mono)",
              fontSize: "11px",
              padding: "3px 10px",
              border: `1px solid ${isCurrent ? "var(--gold)" : "var(--border)"}`,
              color: isCurrent ? "var(--gold)" : "var(--text-muted)",
              background: isCurrent ? "color-mix(in srgb, var(--gold) 10%, transparent)" : "transparent",
              textDecoration: "none",
              letterSpacing: ".04em",
            }}
          >
            {s.subject_id}
          </Link>
        );
      })}
    </nav>
  );
}
