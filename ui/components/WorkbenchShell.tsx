"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bot,
  BrainCircuit,
  ClipboardList,
  Database,
  History,
  Power,
  Shield,
  User,
  X,
} from "lucide-react";
import type { StudyOverview } from "../lib/workbench-data";

function Clock() {
  const [time, setTime] = useState("00:00:00");

  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString("en-GB"));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, []);

  return <span className="hidden font-mono text-xs tracking-widest text-primary lg:inline">{time}</span>;
}

export function WorkbenchShell({
  children,
  studyOverviewData,
}: {
  children: React.ReactNode;
  studyOverviewData: StudyOverview;
}) {
  const pathname = usePathname();
  const [confirmLock, setConfirmLock] = useState(false);
  const [locked, setLocked] = useState(false);

  const activeSubjectId = useMemo(() => {
    const match = pathname.match(/^\/dashboard\/subjects\/([^/]+)/);
    return match ? match[1] : null;
  }, [pathname]);

  const fallbackSubject = studyOverviewData.subject_registry[0]?.subject_id.replace(/-/g, "_") ?? "subj_001";
  const subjectId = activeSubjectId ?? fallbackSubject;
  const subjectRoot = `/dashboard/subjects/${subjectId}`;

  const navItems = [
    { label: "Study", href: "/dashboard", icon: Activity, active: pathname === "/dashboard" },
    { label: "Subject", href: subjectRoot, icon: BrainCircuit, active: pathname === subjectRoot },
    { label: "Baseline", href: `${subjectRoot}/baseline`, icon: ClipboardList, active: pathname.startsWith(`${subjectRoot}/baseline`) },
    { label: "Gumi", href: `${subjectRoot}/gumi`, icon: Bot, active: pathname.startsWith(`${subjectRoot}/gumi`) },
    { label: "Chronicle", href: `${subjectRoot}/chronicle`, icon: History, active: pathname.startsWith(`${subjectRoot}/chronicle`) },
  ];

  const mobileItems = [navItems[0], navItems[1], navItems[4], navItems[3]];
  const breadcrumb = [
    "ROOT",
    ...pathname
      .split("/")
      .filter(Boolean)
      .map((part) => (part === "dashboard" ? "STUDY" : part.replace(/_/g, " ").toUpperCase())),
  ];

  return (
    <div className="ris-shell ris-scanlines grid min-h-screen grid-cols-1 grid-rows-[52px_1fr] text-foreground md:grid-cols-[64px_1fr]">
      <header
        className="ris-status-bar z-30 col-span-full row-start-1 flex h-[52px] items-center gap-3 px-3 md:px-4"
        data-testid="ris-status-bar"
      >
        <img alt="Relic" className="h-8 w-8" src={`${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/relic-mark.svg`} />
        <div className="hidden min-w-0 items-center gap-1 truncate font-mono text-[11px] tracking-wider text-muted-foreground sm:flex">
          {breadcrumb.map((part, index) => (
            <span key={`${part}-${index}`}>
              {index > 0 ? <span className="px-1 text-[#4a555b]">/</span> : null}
              <span className={index === breadcrumb.length - 1 ? "text-primary" : ""}>{part}</span>
            </span>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2 md:gap-3">
          <span className="ris-chip inline-flex items-center gap-1.5 border border-success/60 bg-success/15 px-2 py-1 text-success">
            <i className="ris-blink h-1.5 w-1.5 bg-success" />
            LIVE
          </span>
          <span className="ris-chip hidden items-center gap-1.5 border border-primary/60 bg-primary/15 px-2 py-1 text-primary sm:inline-flex">
            <Database className="h-3 w-3" />
            {studyOverviewData.subjects_active} SUBJECTS
          </span>
          <Clock />
          <div className="hidden items-center gap-2 border-l border-border pl-3 lg:flex">
            <span className="flex h-7 w-7 items-center justify-center border border-primary/50 bg-muted text-primary">
              <User className="h-3.5 w-3.5" />
            </span>
            <span className="leading-none">
              <strong className="block font-display text-xs tracking-widest">RESEARCHER</strong>
              <small className="font-mono text-[9px] text-muted-foreground">R-0007-RELIC</small>
            </span>
          </div>
        </div>
      </header>

      <nav
        aria-label="Workbench navigation"
        className="ris-nav-rail z-20 row-start-2 hidden flex-col items-center gap-1 py-3 md:flex"
        data-testid="ris-nav-rail"
      >
        {navItems.map(({ active, href, icon: Icon, label }) => (
          <Link
            aria-label={label}
            className="ris-nav-link relative flex h-11 w-11 items-center justify-center border border-transparent text-muted-foreground hover:border-border hover:bg-muted hover:text-foreground"
            data-active={active}
            href={href as Route}
            key={label}
            title={label}
          >
            {active ? <span className="absolute inset-y-2 left-0 w-0.5 bg-primary" /> : null}
            <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
          </Link>
        ))}
        <button
          aria-label="End session"
          className="ris-nav-link mt-auto flex h-11 w-11 items-center justify-center border border-transparent text-destructive hover:border-destructive/60 hover:bg-destructive/15"
          onClick={() => setConfirmLock(true)}
          title="End session"
          type="button"
        >
          <Power className="h-[18px] w-[18px]" strokeWidth={1.75} />
        </button>
      </nav>

      <main className="row-start-2 min-w-0 overflow-x-hidden md:col-start-2" id="main-content" tabIndex={-1}>
        <div className="mx-auto w-full max-w-[1480px] p-4 pb-20 md:p-5 lg:p-6">{children}</div>
      </main>

      <nav
        aria-label="Mobile workbench navigation"
        className="ris-status-bar fixed inset-x-0 bottom-0 z-40 grid h-[60px] grid-cols-4 border-t border-border md:hidden"
        data-testid="ris-mobile-nav"
      >
        {mobileItems.map(({ active, href, icon: Icon, label }) => (
          <Link
            className="ris-mobile-link flex flex-col items-center justify-center gap-1 border border-transparent font-display text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
            data-active={active}
            href={href as Route}
            key={label}
          >
            <Icon className="h-4 w-4" strokeWidth={1.75} />
            {label}
          </Link>
        ))}
      </nav>

      {confirmLock ? (
        <div
          aria-label="End session confirmation"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-5"
          role="dialog"
        >
          <section className="ris-panel w-full max-w-md border-destructive/60 bg-card p-5 shadow-[0_0_20px_var(--ris-red-glow)]">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h2 className="font-display text-lg font-bold tracking-wider text-destructive">END SESSION</h2>
              <button aria-label="Close" className="text-muted-foreground hover:text-foreground" onClick={() => setConfirmLock(false)} type="button">
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="py-5 text-sm text-muted-foreground">
              Lock the workbench and revoke the current researcher token. Re-authentication will be required.
            </p>
            <div className="flex justify-end gap-2">
              <button className="ris-btn border border-border bg-muted px-4 py-2 text-muted-foreground" onClick={() => setConfirmLock(false)} type="button">
                Cancel
              </button>
              <button
                className="ris-btn border border-destructive bg-destructive px-4 py-2 text-black"
                onClick={() => {
                  setConfirmLock(false);
                  setLocked(true);
                }}
                type="button"
              >
                <Shield className="mr-2 inline h-3.5 w-3.5" />
                Lock Workbench
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {locked ? (
        <div
          aria-label="Workbench locked"
          aria-modal="true"
          className="ris-scanlines fixed inset-0 z-[60] flex flex-col items-center justify-center gap-6 bg-black/95 p-6 text-center"
          role="dialog"
        >
          <Shield className="h-12 w-12 text-destructive" strokeWidth={1.5} />
          <div className="space-y-2">
            <h2 className="font-display text-2xl font-bold tracking-[0.3em] text-destructive">WORKBENCH LOCKED</h2>
            <p className="font-mono text-xs tracking-wider text-muted-foreground">
              Researcher token revoked · session ended · R-0007-RELIC
            </p>
          </div>
          <button
            className="ris-btn border border-primary bg-primary px-5 py-2 font-display text-sm tracking-widest text-primary-foreground"
            onClick={() => setLocked(false)}
            type="button"
          >
            <User className="mr-2 inline h-3.5 w-3.5" />
            Re-authenticate
          </button>
        </div>
      ) : null}
    </div>
  );
}
