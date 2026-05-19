"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { formatDate } from "../lib/format";
import type { StudyOverview } from "../lib/workbench-data";

export function WorkbenchShell({
  children,
  studyOverviewData,
}: {
  children: React.ReactNode;
  studyOverviewData: StudyOverview;
}) {
  const pathname  = usePathname();
  const [open, setOpen]   = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const activeSubjects = studyOverviewData.subjects_active;
  const pendingReviews = studyOverviewData.pending_reviews;
  const riskAlerts     = studyOverviewData.active_risk_alerts;
  const provFails      = studyOverviewData.hermes_provisioning_failures ?? 0;
  const studyId        = studyOverviewData.study_id;
  const protocol       = studyOverviewData.protocol_version;

  const firstSubjectId = (studyOverviewData.subject_registry?.[0]?.subject_id ?? "subj_001").replace(/-/g, "_");
  const navItems: Array<{ href: Route; label: string }> = [
    { href: "/workbench/study", label: "Study Dashboard" },
    { href: `/workbench/subjects/${firstSubjectId}` as Route, label: "Subject Overview" },
    { href: `/workbench/subjects/${firstSubjectId}/baseline` as Route, label: "Baseline Profile" },
    { href: `/workbench/subjects/${firstSubjectId}/timeline` as Route, label: "Event Timeline" },
    { href: `/workbench/subjects/${firstSubjectId}/chronicle` as Route, label: "Chronicle" },
  ];

  const validationDate = useMemo(() => {
    if (!studyOverviewData.last_validation_run) return "never";
    return formatDate(studyOverviewData.last_validation_run);
  }, [studyOverviewData.last_validation_run]);

  const closeRail = () => setOpen(false);

  useEffect(() => {
    const saved = window.localStorage.getItem("relic-theme");
    const next =
      saved === "light" || saved === "dark"
        ? saved
        : window.matchMedia("(prefers-color-scheme: light)").matches
          ? "light"
          : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
  }, []);

  /* Close offcanvas rail on Escape — keyboard accessibility */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) closeRail();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const chooseTheme = (next: "dark" | "light") => {
    setTheme(next);
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem("relic-theme", next);
  };

  return (
    <>
      <button
        className="mobile-toggle"
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="workbench-rail"
        aria-label={open ? "Close navigation menu" : "Open navigation menu"}
      >
        Menu
      </button>

      {/* Backdrop — aria-hidden: it's decorative, keyboard users close with Escape */}
      <div
        className={`rail-backdrop ${open ? "open" : ""}`}
        aria-hidden="true"
        onClick={closeRail}
      />

      <div className="layout">
        {/* ── Sidebar ───────────────────────────────────────────────────── */}
        <aside
          id="workbench-rail"
          className={`rail ${open ? "open" : ""}`}
          aria-label="Workbench navigation"
        >
          {/* Brand wordmark */}
          <div className="brand-section">
            <div className="brand" aria-label="Relic">RELIC</div>
            <span className="brand-context">Researcher Workbench</span>
          </div>

          {/* Study status summary */}
          <section className="rail-status" aria-labelledby="status-summary-label">
            <h2 id="status-summary-label" className="rail-section-label">Study Status</h2>
            <dl className="status-list">
              {[
                { key: "ID",            val: studyId },
                { key: "Protocol",      val: `v${protocol}` },
                { key: "Active",        val: activeSubjects,    warn: false,           fault: false },
                { key: "Pending",       val: pendingReviews,    warn: pendingReviews > 0,  fault: false },
                { key: "Risk Alerts",   val: riskAlerts,        warn: false,           fault: riskAlerts > 0 },
                ...(provFails > 0 ? [{ key: "Prov. Fails", val: provFails, warn: false, fault: true }] : []),
              ].map((row) => (
                <div key={row.key} className="rail-status-row">
                  <dt className="rs-key">{row.key}</dt>
                  <dd
                    className="rs-val"
                    data-warn={("warn" in row && row.warn) || undefined}
                    data-fault={("fault" in row && row.fault) || undefined}
                  >
                    {String(row.val)}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          {/* Navigation */}
          <nav className="rail-nav" aria-label="Workbench sections">
            <div className="rail-section-label" aria-hidden="true">Workbench</div>
            {navItems.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/workbench/study" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  className={`rail-link ${isActive ? "active" : ""}`}
                  href={item.href}
                  onClick={closeRail}
                  aria-current={isActive ? "page" : undefined}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* Theme toggle */}
          <div className="rail-footer">
            <div className="rail-footer-label" id="theme-group-label">Appearance</div>
            <div
              className="theme-toggle"
              role="group"
              aria-labelledby="theme-group-label"
            >
              {(["dark", "light"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`theme-btn ${theme === t ? "active" : ""}`}
                  aria-pressed={theme === t}
                  onClick={() => chooseTheme(t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* id="main-content" target for skip-nav link (WCAG 2.4.1) */}
        <main id="main-content" className="content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </>
  );
}
