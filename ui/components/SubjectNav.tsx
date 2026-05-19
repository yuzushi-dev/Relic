"use client";
import Link from "next/link";
import type { StudyOverview } from "../lib/workbench-data";

type Props = {
  subjects: StudyOverview["subject_registry"];
  currentSubjectId: string;
  view: "baseline" | "timeline" | "gumi" | "overview" | "chronicle";
};

const VIEW_SUFFIX: Record<Exclude<Props["view"], "chronicle">, string> = {
  overview: "",
  baseline: "/baseline",
  timeline: "/timeline",
  gumi: "/gumi",
};

export function SubjectNav({ subjects, currentSubjectId, view }: Props) {
  const subjectSlug = currentSubjectId.replace(/-/g, "_");
  const base = `/workbench/subjects/${subjectSlug}`;

  if (view === "chronicle") {
    return (
      <nav aria-label="Chronicle navigation">
        <div className="mb-3">
          <span className="filter-label">Subject</span>
          <div className="flex flex-wrap gap-1">
            {subjects.map((s) => {
              const slug = s.subject_id.replace(/-/g, "_");
              const isCurrent = slug === currentSubjectId || s.subject_id === currentSubjectId;
              return (
                <Link
                  key={s.subject_id}
                  href={`/workbench/subjects/${slug}/chronicle` as any}
                  className={`filter-btn ${isCurrent ? "active" : ""}`}
                  style={{ textDecoration: "none" }}
                >
                  {s.subject_id}
                </Link>
              );
            })}
          </div>
        </div>
        <div className="border-t border-gray-200 pt-3">
          <span className="filter-label">Chronicle</span>
          <div className="flex flex-wrap gap-1">
            <Link href={`${base}/chronicle` as any} className="filter-btn" style={{ textDecoration: "none" }}>Overview</Link>
            <Link href={`${base}/chronicle/events` as any} className="filter-btn" style={{ textDecoration: "none" }}>Events</Link>
            <Link href={`${base}/chronicle/decisions` as any} className="filter-btn" style={{ textDecoration: "none" }}>Decisions</Link>
            <Link href={`${base}/chronicle/snapshots` as any} className="filter-btn" style={{ textDecoration: "none" }}>Snapshots</Link>
          </div>
        </div>
      </nav>
    );
  }

  const suffix = VIEW_SUFFIX[view] ?? "";
  return (
    <nav aria-label="Subject navigation">
      <span className="filter-label">Quick Switch</span>
      <div className="flex flex-wrap gap-1">
        {subjects.map((s) => {
          const slug = s.subject_id.replace(/-/g, "_");
          const isCurrent = slug === currentSubjectId || s.subject_id === currentSubjectId;
          return (
            <Link
              key={s.subject_id}
              href={`/workbench/subjects/${slug}${suffix}` as any}
              className={`filter-btn ${isCurrent ? "active" : ""}`}
              style={{ textDecoration: "none" }}
            >
              {s.subject_id}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
