import type { ChronicleStats } from "@/lib/chronicle-types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface Props {
  stats: ChronicleStats;
}

export function StatsPanel({ stats }: Props) {
  return (
    <div className="space-y-6" data-testid="stats-panel">
      <div className="grid grid-cols-3 gap-4">
        <Card className="rounded-none border-border text-center">
          <CardContent className="p-4">
            <div className="text-2xl font-bold font-mono tracking-tight text-primary">{stats.total_events}</div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground mt-1">Events</div>
          </CardContent>
        </Card>
        <Card className="rounded-none border-border text-center">
          <CardContent className="p-4">
            <div className="text-2xl font-bold font-mono tracking-tight text-primary">{stats.total_decisions}</div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground mt-1">Decisions</div>
          </CardContent>
        </Card>
        <Card className="rounded-none border-border text-center">
          <CardContent className="p-4">
            <div className="text-2xl font-bold font-mono tracking-tight text-primary">{stats.total_snapshots}</div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground mt-1">Snapshots</div>
          </CardContent>
        </Card>
      </div>

      {stats.by_severity && Object.keys(stats.by_severity).length > 0 && (
        <Card className="rounded-none border-border">
          <CardHeader className="p-4 pb-2">
            <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Distribution By Severity</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(stats.by_severity).filter(([, n]) => n > 0).map(([k, v]) => {
                const badgeVariant = k === "error" || k === "critical" ? "destructive" : k === "warning" ? "warning" : "secondary";
                return (
                  <Badge key={k} variant={badgeVariant} className="rounded-none font-mono text-xs">
                    {k}: {v}
                  </Badge>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {stats.last_event_at && (
        <div className="text-[10px] font-mono text-muted-foreground italic text-right">
          Last event recorded: {new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(stats.last_event_at))}
        </div>
      )}
    </div>
  );
}
