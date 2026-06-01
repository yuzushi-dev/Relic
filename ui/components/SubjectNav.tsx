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
  const base = `/dashboard/subjects/${subjectSlug}`;

  if (view === "chronicle") {
    return (
      <nav aria-label="Chronicle navigation" className="ris-subject-bar space-y-3 p-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-display text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">SUBJECT</span>
          <div className="flex flex-wrap gap-1.5">
            {subjects.map((s) => {
              const slug = s.subject_id.replace(/-/g, "_");
              const isCurrent = slug === currentSubjectId || s.subject_id === currentSubjectId;
              return (
                <Link
                  key={s.subject_id}
                  href={`/dashboard/subjects/${slug}/chronicle` as any}
                  className={`ris-subject-link inline-flex items-center justify-center whitespace-nowrap border px-3 font-mono text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring ${
                    isCurrent
                      ? "border-primary bg-primary text-black"
                      : "border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground"
                  }`}
                >
                  {s.subject_id}
                </Link>
              );
            })}
          </div>
          <span className="ris-chip ml-auto inline-flex items-center gap-1.5 border border-primary/60 bg-primary/15 px-2 py-1 text-primary">
            <i className="ris-blink h-1.5 w-1.5 bg-primary" />
            SCOPED
          </span>
        </div>
        <div className="border-t border-border pt-3">
          <span className="mb-2 block font-display text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Chronicle Sections</span>
          <div className="flex flex-wrap gap-1.5">
            {[
              { href: `${base}/chronicle`, label: "Overview" },
              { href: `${base}/chronicle/events`, label: "Events Log" },
              { href: `${base}/chronicle/decisions`, label: "Decisions History" },
              { href: `${base}/chronicle/snapshots`, label: "State Snapshots" },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href as any}
                className="ris-subject-link inline-flex items-center justify-center whitespace-nowrap border border-input bg-background px-3 text-xs font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      </nav>
    );
  }

  const suffix = VIEW_SUFFIX[view] ?? "";
  return (
    <nav aria-label="Subject navigation" className="ris-subject-bar flex flex-wrap items-center gap-3 p-3">
      <span className="font-display text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">SUBJECT</span>
      <div className="flex flex-wrap gap-1.5">
        {subjects.map((s) => {
          const slug = s.subject_id.replace(/-/g, "_");
          const isCurrent = slug === currentSubjectId || s.subject_id === currentSubjectId;
          return (
            <Link
              key={s.subject_id}
              href={`/dashboard/subjects/${slug}${suffix}` as any}
              className={`ris-subject-link inline-flex items-center justify-center whitespace-nowrap border px-3 font-mono text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring ${
                isCurrent
                  ? "border-primary bg-primary text-black"
                  : "border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground"
              }`}
            >
              {s.subject_id}
            </Link>
          );
        })}
      </div>
      <span className="ris-chip ml-auto inline-flex items-center gap-1.5 border border-primary/60 bg-primary/15 px-2 py-1 text-primary">
        <i className="ris-blink h-1.5 w-1.5 bg-primary" />
        SCOPED
      </span>
    </nav>
  );
}
