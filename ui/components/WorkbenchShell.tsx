"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { formatDate } from "../lib/format";
import type { StudyOverview } from "../lib/workbench-data";
import { Menu, X, Sun, Moon, Database, User, Activity, FileText, ClipboardList } from "lucide-react";

export function WorkbenchShell({
  children,
  studyOverviewData,
}: {
  children: React.ReactNode;
  studyOverviewData: StudyOverview;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("light");

  const activeSubjects = studyOverviewData.subjects_active;
  const pendingReviews = studyOverviewData.pending_reviews;
  const riskAlerts = studyOverviewData.active_risk_alerts;
  const provFails = studyOverviewData.hermes_provisioning_failures ?? 0;
  const studyId = studyOverviewData.study_id;
  const protocol = studyOverviewData.protocol_version;

  // Extract active subject ID from path: /dashboard/subjects/[subject_id]...
  const activeSubjectId = useMemo(() => {
    const match = pathname.match(/^\/dashboard\/subjects\/([^\/]+)/);
    return match ? match[1] : null;
  }, [pathname]);

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
    <div className="min-h-screen bg-background text-foreground flex flex-col md:flex-row">
      {/* Mobile Toggle Button */}
      <button
        className="fixed bottom-4 right-4 z-50 p-3 bg-primary text-primary-foreground shadow-lg md:hidden hover:opacity-90 active:scale-95 transition-all flex items-center justify-center rounded-none border border-border"
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="workbench-rail"
        aria-label={open ? "Close navigation menu" : "Open navigation menu"}
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden transition-opacity"
          aria-hidden="true"
          onClick={closeRail}
        />
      )}

      {/* Sidebar / Rail */}
      <aside
        id="workbench-rail"
        className={`fixed inset-y-0 left-0 w-64 bg-card border-r border-border z-45 md:z-0 flex flex-col h-screen transform transition-transform duration-200 ease-in-out md:translate-x-0 md:sticky md:top-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Workbench navigation"
      >
        {/* Brand section */}
        <div className="p-6 border-b border-border flex flex-col gap-1">
          <div className="font-mono text-xl font-bold tracking-wider text-primary flex items-center gap-2">
            <Database className="h-5 w-5" />
            <span>RELIC</span>
          </div>
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Researcher Workbench
          </span>
        </div>

        {/* Study status summary */}
        <div className="p-4 border-b border-border bg-muted/20">
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Study Status
          </h2>
          <dl className="grid grid-cols-2 gap-x-2 gap-y-1.5 text-xs">
            <div className="flex flex-col">
              <dt className="text-muted-foreground text-[10px]">ID</dt>
              <dd className="font-mono font-medium truncate">{studyId}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-muted-foreground text-[10px]">Protocol</dt>
              <dd className="font-mono font-medium">v{protocol}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-muted-foreground text-[10px]">Active</dt>
              <dd className="font-semibold">{activeSubjects}</dd>
            </div>
            <div className="flex flex-col">
              <dt className="text-muted-foreground text-[10px]">Pending</dt>
              <dd className={`font-semibold ${pendingReviews > 0 ? "text-warning" : ""}`}>
                {pendingReviews}
              </dd>
            </div>
            <div className="flex flex-col col-span-2">
              <dt className="text-muted-foreground text-[10px]">Risk Alerts</dt>
              <dd className={`font-semibold ${riskAlerts > 0 ? "text-destructive font-bold" : ""}`}>
                {riskAlerts}
              </dd>
            </div>
            {provFails > 0 && (
              <div className="flex flex-col col-span-2">
                <dt className="text-muted-foreground text-[10px]">Prov. Fails</dt>
                <dd className="font-semibold text-destructive">{provFails}</dd>
              </div>
            )}
          </dl>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-4" aria-label="Workbench sections">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 mb-2">
              Core
            </div>
            <Link
              href="/dashboard"
              onClick={closeRail}
              className={`flex items-center gap-2.5 px-3 py-2 text-sm border-l-2 transition-colors ${
                pathname === "/dashboard"
                  ? "border-primary bg-accent/30 text-foreground font-medium"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:bg-accent/10"
              }`}
            >
              <Activity className="h-4 w-4" />
              <span>Study Dashboard</span>
            </Link>
          </div>

          {/* Subject-specific navigation */}
          {activeSubjectId ? (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 mb-2 flex items-center gap-1.5">
                <User className="h-3 w-3" />
                <span>Subject: {activeSubjectId}</span>
              </div>
              <div className="space-y-1">
                {[
                  {
                    href: `/dashboard/subjects/${activeSubjectId}` as Route,
                    label: "Subject Overview",
                    icon: Activity,
                  },
                  {
                    href: `/dashboard/subjects/${activeSubjectId}/baseline` as Route,
                    label: "Baseline Profile",
                    icon: ClipboardList,
                  },
                  {
                    href: `/dashboard/subjects/${activeSubjectId}/gumi` as Route,
                    label: "Gumi Profile",
                    icon: User,
                  },
                  {
                    href: `/dashboard/subjects/${activeSubjectId}/timeline` as Route,
                    label: "Event Timeline",
                    icon: FileText,
                  },
                  {
                    href: `/dashboard/subjects/${activeSubjectId}/chronicle` as Route,
                    label: "Chronicle Audit",
                    icon: Database,
                  },
                ].map((item) => {
                  const isActive =
                    pathname === item.href ||
                    (item.href !== `/dashboard/subjects/${activeSubjectId}` &&
                      pathname.startsWith(item.href));
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={closeRail}
                      className={`flex items-center gap-2.5 px-3 py-2 text-sm border-l-2 transition-colors ${
                        isActive
                          ? "border-primary bg-accent/30 text-foreground font-medium"
                          : "border-transparent text-muted-foreground hover:text-foreground hover:bg-accent/10"
                      }`}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ) : (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-3 mb-2">
                Subject Context
              </div>
              <p className="text-xs text-muted-foreground px-3 italic">
                Select a subject from the dashboard registry to view profiles.
              </p>
            </div>
          )}
        </nav>

        {/* Footer / Theme toggle */}
        <div className="p-4 border-t border-border bg-muted/10">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            Appearance
          </div>
          <div className="flex border border-border bg-muted p-0.5 rounded-none">
            <button
              type="button"
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs transition-colors ${
                theme === "light"
                  ? "bg-background text-foreground font-medium shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => chooseTheme("light")}
            >
              <Sun className="h-3.5 w-3.5" />
              <span>Light</span>
            </button>
            <button
              type="button"
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs transition-colors ${
                theme === "dark"
                  ? "bg-background text-foreground font-medium shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => chooseTheme("dark")}
            >
              <Moon className="h-3.5 w-3.5" />
              <span>Dark</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main id="main-content" className="flex-1 flex flex-col min-w-0 overflow-x-hidden min-h-screen" tabIndex={-1}>
        <div className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
