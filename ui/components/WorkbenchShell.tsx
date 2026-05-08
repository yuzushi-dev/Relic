"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { formatDate } from "../lib/format";
import type { StudyOverview } from "../lib/workbench-data";

const navItems: Array<{ href: Route; label: string }> = [
  { href: "/workbench/study", label: "Study Dashboard" },
  { href: "/workbench/subjects/subj_001" as Route, label: "Subject Overview" },
  { href: "/workbench/subjects/subj_001/baseline" as Route, label: "Baseline Profile" },
  { href: "/workbench/subjects/subj_001/timeline" as Route, label: "Event Timeline" },
];

export function WorkbenchShell({ children, studyOverviewData }: { children: React.ReactNode; studyOverviewData: StudyOverview }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const activeSubjects = studyOverviewData.subjects_active;
  const pendingReviews = studyOverviewData.pending_reviews;
  const riskAlerts = studyOverviewData.active_risk_alerts;
  const validationDate = useMemo(() => {
    if (!studyOverviewData.last_validation_run) return "never";
    return formatDate(studyOverviewData.last_validation_run);
  }, []);

  const closeRail = () => setOpen(false);

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("relic-theme");
    const nextTheme =
      savedTheme === "light" || savedTheme === "dark"
        ? savedTheme
        : window.matchMedia("(prefers-color-scheme: light)").matches
          ? "light"
          : "dark";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
  }, []);

  const chooseTheme = (nextTheme: "dark" | "light") => {
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("relic-theme", nextTheme);
  };

  return (
    <>
      <button
        className="mobile-toggle"
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="workbench-rail"
      >
        Menu
      </button>
      <button
        className={`rail-backdrop ${open ? "open" : ""}`}
        type="button"
        aria-label="Close navigation"
        onClick={closeRail}
      />
      <div className="layout">
        <aside id="workbench-rail" className={`rail ${open ? "open" : ""}`}>
          <div className="brand">
            Relic<span>&gt;</span>
          </div>
          <div className="sub">Researcher Workbench</div>

          <div className="rail-block">
            <div className="rail-label">Study Summary</div>
            <div className="metric">{activeSubjects}</div>
            <div className="rail-copy">
              Active subjects · {pendingReviews} reviews · {riskAlerts} risk alerts · validated {validationDate}
            </div>
          </div>

          <nav className="rail-section" aria-label="Workbench navigation">
            <div className="rail-label">Navigation</div>
            {navItems.map((item) => {
              const isActive = pathname === item.href || (item.href !== "/workbench/study" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  className={`rail-item ${isActive ? "active" : ""}`}
                  href={item.href}
                  onClick={closeRail}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="rail-section">
            <div className="rail-label">Theme</div>
            <div className="theme-toggle" role="group" aria-label="Color theme">
              <button
                type="button"
                className={theme === "dark" ? "active" : ""}
                aria-pressed={theme === "dark"}
                onClick={() => chooseTheme("dark")}
              >
                Dark
              </button>
              <button
                type="button"
                className={theme === "light" ? "active" : ""}
                aria-pressed={theme === "light"}
                onClick={() => chooseTheme("light")}
              >
                Light
              </button>
            </div>
          </div>

        </aside>
        <main className="content">{children}</main>
      </div>
    </>
  );
}
