"use client";

import { useState } from "react";
import { formatDateTime } from "../lib/format";
import type { EventStream } from "../lib/workbench-data";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";
import { SlidersHorizontal, Clock } from "lucide-react";

type ValidStream = "evidence" | "inference" | "pending" | "approved" | "blocked" | "gumi" | "runtime" | "correction" | "neutral";

function eventStream(event: EventStream["events"][number]): ValidStream {
  if (event.decision === "blocked") return "blocked";
  switch (event.event_class) {
    case "gumi_initiative": case "checkin": return "gumi";
    case "system":                          return "runtime";
    case "researcher_action":               return "evidence";
    case "user_message":                    return "evidence";
    default:
      if (event.ontological_class.includes("inference"))  return "inference";
      if (event.ontological_class.includes("correction")) return "correction";
      return "neutral";
  }
}

function StreamBadge({ stream, children }: { stream: ValidStream; children: React.ReactNode }) {
  const variantMap: Record<ValidStream, "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info"> = {
    blocked: "destructive",
    gumi: "default", // primary
    runtime: "secondary",
    evidence: "success",
    inference: "warning",
    correction: "destructive",
    neutral: "outline",
    pending: "warning",
    approved: "success",
  };
  return (
    <Badge variant={variantMap[stream] ?? "outline"} className="rounded-none font-mono text-[9px] uppercase">
      {children}
    </Badge>
  );
}

export function TimelineView({ subjectId, eventStreamData }: { subjectId: string; eventStreamData: EventStream }) {
  const [filter, setFilter] = useState("all");
  const events = eventStreamData.events;
  const classes = Array.from(new Set(events.map((e) => e.event_class))).sort();
  const filtered = filter === "all" ? events : events.filter((e) => e.event_class === filter);

  const deliveredCount = events.filter((e) => e.decision === "delivered").length;
  const blockedCount = events.filter((e) => e.decision === "blocked").length;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <header className="border-b border-border pb-5">
        <div className="text-xs font-mono uppercase tracking-widest text-primary mb-1">Subject History · {subjectId}</div>
        <h1 className="text-3xl font-bold tracking-tight font-mono mb-2">Event Stream</h1>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground font-mono">
          <span>{events.length} Events Total</span>
          <span>•</span>
          <span className="text-success">{deliveredCount} Delivered</span>
          <span>•</span>
          <span className="text-destructive">{blockedCount} Blocked</span>
          {eventStreamData.stream === "live" && (
            <>
              <span>•</span>
              <Badge variant="success" className="rounded-none text-[9px] font-mono h-4">LIVE</Badge>
            </>
          )}
        </div>
      </header>

      {/* Filter by Class Card */}
      <Card className="rounded-none border-border">
        <CardHeader className="p-4 flex flex-row items-center gap-2 space-y-0">
          <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Filter by Event Class</CardTitle>
        </CardHeader>
        <CardContent className="p-4 pt-0">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter events by class">
            <button
              type="button"
              onClick={() => setFilter("all")}
              className={`px-2.5 py-1 text-xs border transition-colors rounded-none font-mono ${
                filter === "all"
                  ? "bg-primary text-primary-foreground border-primary font-medium"
                  : "border-input bg-background hover:bg-accent"
              }`}
              aria-pressed={filter === "all"}
            >
              All
            </button>
            {classes.map((cls) => (
              <button
                key={cls}
                type="button"
                onClick={() => setFilter(cls)}
                className={`px-2.5 py-1 text-xs border transition-colors rounded-none font-mono ${
                  filter === cls
                    ? "bg-primary text-primary-foreground border-primary font-medium"
                    : "border-input bg-background hover:bg-accent"
                }`}
                aria-pressed={filter === cls}
              >
                {cls.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Events List */}
      <Card className="rounded-none border-border">
        <CardHeader className="border-b border-border">
          <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            Audit Trail Events ({filtered.length})
          </CardTitle>
          {filtered.length === 0 && (
            <CardDescription className="pt-2 text-muted-foreground italic">
              No events match the selected filter.
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="p-0 divide-y divide-border">
          {filtered.map((event) => {
            const stream = eventStream(event);
            return (
              <div key={event.event_id} className="p-6 space-y-3 hover:bg-muted/10">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <StreamBadge stream={stream}>
                      {event.ontological_class.replace(/_/g, " ")}
                    </StreamBadge>
                    <Badge variant="outline" className="rounded-none font-mono text-[9px] uppercase border-border">
                      {event.initiator}
                    </Badge>
                    <Badge variant="secondary" className="rounded-none font-mono text-[9px] uppercase">
                      {event.event_class.replace(/_/g, " ")}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1 text-[10px] text-muted-foreground font-mono">
                    <Clock className="h-3 w-3" />
                    <time dateTime={event.timestamp}>
                      {formatDateTime(event.timestamp)}
                    </time>
                  </div>
                </div>

                <div className="text-sm bg-muted/40 p-3 border-l border-primary/50 text-foreground leading-relaxed font-mono">
                  {event.content_preview || <span className="italic text-muted-foreground">[Blocked by safety policy]</span>}
                </div>

                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  {event.risk_level !== "none" && (
                    <Badge variant="destructive" className="rounded-none font-mono text-[9px] uppercase">
                      Risk: {event.risk_level}
                    </Badge>
                  )}
                  {event.has_media && (
                    <Badge variant="outline" className="rounded-none font-mono text-[9px] uppercase text-muted-foreground">media</Badge>
                  )}
                  {event.has_user_response && (
                    <Badge variant="outline" className="rounded-none font-mono text-[9px] uppercase text-muted-foreground">user response</Badge>
                  )}
                  {event.has_correction && (
                    <Badge variant="outline" className="rounded-none font-mono text-[9px] uppercase text-muted-foreground">correction</Badge>
                  )}
                  {event.has_boundary_risk && (
                    <Badge variant="destructive" className="rounded-none font-mono text-[9px] uppercase">boundary risk</Badge>
                  )}
                  <span className="text-[10px] font-mono text-muted-foreground ml-auto">
                    ID: {event.event_id.startsWith("chr_") ? event.event_id.slice(4, 16) : event.event_id.slice(0, 12)}
                  </span>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <footer className="text-[10px] font-mono text-muted-foreground text-center pt-8 border-t border-border">
        Generated {formatDateTime(eventStreamData.generated_at)} · Subject Scope: {subjectId}
      </footer>
    </div>
  );
}
