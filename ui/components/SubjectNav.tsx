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
      <nav aria-label="Chronicle navigation" className="space-y-4 bg-card p-4 border border-border">
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block mb-2">Subject Registry</span>
          <div className="flex flex-wrap gap-1.5">
            {subjects.map((s) => {
              const slug = s.subject_id.replace(/-/g, "_");
              const isCurrent = slug === currentSubjectId || s.subject_id === currentSubjectId;
              return (
                <Link
                  key={s.subject_id}
                  href={`/dashboard/subjects/${slug}/chronicle` as any}
                  className={`inline-flex items-center justify-center whitespace-nowrap text-xs font-mono font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring border h-8 px-3 ${
                    isCurrent
                      ? "bg-primary text-primary-foreground shadow"
                      : "border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground"
                  }`}
                >
                  {s.subject_id}
                </Link>
              );
            })}
          </div>
        </div>
        <div className="border-t border-border pt-3">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block mb-2">Chronicle Sections</span>
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
                className="inline-flex items-center justify-center whitespace-nowrap text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring border h-8 px-3 border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground"
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
    <nav aria-label="Subject navigation" className="bg-card p-4 border border-border">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block mb-2">Quick Switch Subject</span>
      <div className="flex flex-wrap gap-1.5">
        {subjects.map((s) => {
          const slug = s.subject_id.replace(/-/g, "_");
          const isCurrent = slug === currentSubjectId || s.subject_id === currentSubjectId;
          return (
            <Link
              key={s.subject_id}
              href={`/dashboard/subjects/${slug}${suffix}` as any}
              className={`inline-flex items-center justify-center whitespace-nowrap text-xs font-mono font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring border h-8 px-3 ${
                isCurrent
                  ? "bg-primary text-primary-foreground shadow"
                  : "border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground"
              }`}
            >
              {s.subject_id}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
