"use client";

import Link from "next/link";
import { useState, type CSSProperties } from "react";
import { formatDate, formatDateTime } from "../lib/format";
import type { StudyOverview, SubjectRow } from "../lib/workbench-data";
import { Badge } from "./ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "./ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { ClipboardList, ShieldAlert, CheckCircle2, AlertTriangle, HelpCircle } from "lucide-react";

function StatusMarker({ status }: { status: SubjectRow["status"] }) {
  const variant = status === "active" ? "success" : status === "paused" ? "warning" : "secondary";
  return (
    <Badge variant={variant} className="capitalize rounded-none font-mono">
      {status}
    </Badge>
  );
}

function RiskBadge({ risk }: { risk: SubjectRow["risk"] }) {
  const variant = risk === "high" || risk === "critical" ? "destructive" : risk === "medium" || risk === "low" ? "warning" : "secondary";
  return (
    <Badge variant={variant} className="capitalize rounded-none font-mono">
      {risk}
    </Badge>
  );
}

function HermesCell({ profileId }: { profileId: string | null | undefined }) {
  if (!profileId) {
    return <Badge variant="destructive" className="rounded-none font-mono">failed</Badge>;
  }
  return (
    <code className="text-xs bg-muted px-1.5 py-0.5 border border-border font-mono">
      {profileId}
    </code>
  );
}

function ReviewCell({ pending }: { pending: boolean }) {
  if (pending) {
    return <Badge variant="warning" className="rounded-none font-mono">queued</Badge>;
  }
  return <span className="text-muted-foreground">—</span>;
}

export function StudyDashboard({ studyOverviewData }: { studyOverviewData: StudyOverview }) {
  const [conditionFilter, setConditionFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const subjects = studyOverviewData.subject_registry;
  const conditions = ["all", ...Array.from(new Set(subjects.map((s) => s.condition)))];
  const statuses = ["all", "active", "paused", "archived"];

  const filtered = subjects.filter(
    (s) =>
      (conditionFilter === "all" || s.condition === conditionFilter) &&
      (statusFilter === "all" || s.status === statusFilter),
  );

  const validation = studyOverviewData.last_validation_run
    ? formatDateTime(studyOverviewData.last_validation_run)
    : "never";

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <header className="border-b border-border pb-4">
        <div className="mb-1 font-mono text-[11px] uppercase tracking-[0.24em] text-primary">
          Root / Study / Overview
        </div>
        <h1 className="mb-2 font-display text-3xl font-bold uppercase tracking-tight">
          {studyOverviewData.study_id}
        </h1>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground font-mono">
          <span>Protocol: v{studyOverviewData.protocol_version}</span>
          <span>•</span>
          <span>{subjects.length} Subjects Registered</span>
          <span>•</span>
          <span>Validated: {validation}</span>
        </div>
      </header>

      {/* Stat Bar */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5" role="region" aria-label="Study Metrics">
        {[
          {
            key: "Active Subjects",
            val: studyOverviewData.subjects_active,
            icon: CheckCircle2,
            color: "text-success",
            accent: "var(--ris-green)",
          },
          {
            key: "Paused Subjects",
            val: studyOverviewData.subjects_paused,
            icon: AlertTriangle,
            color: studyOverviewData.subjects_paused > 0 ? "text-warning" : "text-muted-foreground",
            accent: "var(--ris-amber)",
          },
          {
            key: "Archived",
            val: studyOverviewData.subjects_archived,
            icon: HelpCircle,
            color: "text-muted-foreground",
            accent: "var(--ris-cyan)",
          },
          {
            key: "Active Risks",
            val: studyOverviewData.active_risk_alerts,
            icon: ShieldAlert,
            color: studyOverviewData.active_risk_alerts > 0 ? "text-destructive" : "text-muted-foreground",
            accent: "var(--ris-red)",
          },
          {
            key: "Pending Review",
            val: studyOverviewData.pending_reviews,
            icon: ClipboardList,
            color: studyOverviewData.pending_reviews > 0 ? "text-warning" : "text-muted-foreground",
            accent: "var(--ris-violet)",
          },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Card
              key={item.key}
              className="ris-kpi border-border"
              style={{ "--ris-kpi-accent": item.accent } as CSSProperties}
            >
              <CardHeader className="flex flex-row items-center justify-between space-y-0 p-4 pb-2">
                <CardDescription className="text-[10px] font-semibold uppercase tracking-wider">
                  {item.key}
                </CardDescription>
                <Icon className={`h-4 w-4 ${item.color}`} />
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="font-display text-3xl font-bold tracking-tight">{item.val}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Subject Registry */}
      <Card className="border-border">
        <CardHeader className="border-b border-border bg-muted/30">
          <CardTitle className="font-display text-sm font-semibold uppercase tracking-[0.14em]">
            Subject Registry
          </CardTitle>
          <CardDescription>
            Core catalog of enrolled human-AI interaction profiles.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {/* Filters Bar */}
          <div className="p-4 border-b border-border bg-muted/20 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
            <div className="flex flex-wrap gap-4 items-center">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block mb-1.5">
                  Condition
                </span>
                <div className="flex flex-wrap gap-1">
                  {conditions.map((c) => (
                    <button
                      key={c}
                      type="button"
                      className={`ris-btn border px-2.5 py-1 text-xs transition-colors ${
                        conditionFilter === c
                          ? "bg-primary text-primary-foreground border-primary font-medium"
                          : "border-input bg-background hover:bg-accent"
                      }`}
                      onClick={() => setConditionFilter(c)}
                    >
                      {c.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block mb-1.5 md:text-right">
                Status
              </span>
              <div className="flex flex-wrap gap-1">
                {statuses.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`ris-btn border px-2.5 py-1 text-xs transition-colors ${
                      statusFilter === s
                        ? "bg-primary text-primary-foreground border-primary font-medium"
                        : "border-input bg-background hover:bg-accent"
                    }`}
                    onClick={() => setStatusFilter(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/10">
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Subject ID</TableHead>
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Condition</TableHead>
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Status</TableHead>
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Risk Level</TableHead>
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Hermes Profile</TableHead>
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Interaction</TableHead>
                  <TableHead className="font-mono text-xs uppercase tracking-wider">Review Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-24 text-center text-muted-foreground italic">
                      No subjects match the active filters.
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((subject) => (
                    <TableRow key={subject.subject_id} className="hover:bg-muted/30">
                      <TableCell className="font-mono font-medium">
                        <Link
                          href={`/dashboard/subjects/${subject.subject_id.replace(/-/g, "_")}`}
                          className="text-primary hover:underline"
                        >
                          {subject.subject_id}
                        </Link>
                      </TableCell>
                      <TableCell className="capitalize">
                        {subject.condition.replace(/_/g, " ")}
                      </TableCell>
                      <TableCell>
                        <StatusMarker status={subject.status} />
                      </TableCell>
                      <TableCell>
                        <RiskBadge risk={subject.risk} />
                      </TableCell>
                      <TableCell>
                        <HermesCell profileId={subject.hermes_profile_id} />
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {subject.last_user_interaction_at
                          ? formatDate(subject.last_user_interaction_at)
                          : "—"}
                      </TableCell>
                      <TableCell>
                        <ReviewCell pending={subject.pending_review} />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
