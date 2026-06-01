"use client";
import type { ChronicleEvent } from "@/lib/chronicle-types";
import { SeverityBadge, SensitivityBadge } from "./Badges";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useSearchParams } from "next/navigation";

function formatTs(ts: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(ts));
}

export function EventsTable({ events }: { events: ChronicleEvent[] }) {
  const searchParams = useSearchParams();
  const severity = searchParams.get("severity") ?? "";
  const category = searchParams.get("category") ?? "";
  const sensitivity = searchParams.get("sensitivity") ?? "";

  const filtered = events.filter((event) => {
    if (severity && event.severity !== severity) return false;
    if (category && event.category !== category) return false;
    if (sensitivity && event.sensitivity !== sensitivity) return false;
    return true;
  });

  if (filtered.length === 0)
    return <p className="text-sm text-muted-foreground italic p-4 text-center">No events match the current filters.</p>;
    
  return (
    <div className="overflow-x-auto border border-border">
      <Table data-testid="events-table">
        <TableHeader>
          <TableRow className="bg-muted/10">
            <TableHead className="font-mono text-xs uppercase tracking-wider">Time</TableHead>
            <TableHead className="font-mono text-xs uppercase tracking-wider">Category</TableHead>
            <TableHead className="font-mono text-xs uppercase tracking-wider">Severity</TableHead>
            <TableHead className="font-mono text-xs uppercase tracking-wider">Sensitivity</TableHead>
            <TableHead className="font-mono text-xs uppercase tracking-wider">Summary</TableHead>
            <TableHead className="font-mono text-xs uppercase tracking-wider">Actor</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((e) => (
            <TableRow key={e.event_id} className="hover:bg-muted/30">
              <TableCell className="font-mono text-xs text-muted-foreground whitespace-nowrap">{formatTs(e.timestamp)}</TableCell>
              <TableCell>
                <Badge variant="outline" className="rounded-none font-mono text-[10px]">
                  {e.category}
                </Badge>
              </TableCell>
              <TableCell><SeverityBadge severity={e.severity} /></TableCell>
              <TableCell><SensitivityBadge sensitivity={e.sensitivity} /></TableCell>
              <TableCell className="text-sm font-medium text-foreground">{e.summary}</TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">{e.actor ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
