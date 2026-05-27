import type { ChronicleSnapshot } from "@/lib/chronicle-types";
import { diffSnapshots, type DiffEntry } from "@/lib/chronicle-diff";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const KIND_CLASS: Record<DiffEntry["kind"], string> = {
  added: "text-success font-mono",
  removed: "text-destructive font-mono",
  changed: "text-warning font-mono",
  unchanged: "text-muted-foreground font-mono",
};

const KIND_PREFIX: Record<DiffEntry["kind"], string> = {
  added: "+",
  removed: "-",
  changed: "~",
  unchanged: " ",
};

export function SnapshotsList({ snapshots }: { snapshots: ChronicleSnapshot[] }) {
  if (snapshots.length === 0)
    return <p className="text-sm text-muted-foreground italic p-4 text-center">No snapshots recorded.</p>;
  
  const ordered = [...snapshots].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  return (
    <div className="space-y-4" data-testid="snapshots-list">
      {ordered.slice().reverse().map((snap) => {
        const idx = ordered.findIndex((s) => s.snapshot_id === snap.snapshot_id);
        const prev = idx > 0 ? ordered[idx - 1] : null;
        const diff = diffSnapshots(prev, snap);
        const changed = diff.filter((e) => e.kind !== "unchanged");
        
        return (
          <Card key={snap.snapshot_id} className="rounded-none border-border">
            <CardHeader className="p-4 pb-2">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                <CardTitle className="font-mono text-sm font-semibold text-foreground">
                  {snap.label ?? snap.snapshot_id}
                </CardTitle>
                <div className="flex flex-wrap items-center gap-2">
                  {snap.diff_summary && (
                    <Badge variant="outline" className="rounded-none font-mono text-[10px] text-muted-foreground border-border">
                      {snap.diff_summary}
                    </Badge>
                  )}
                  <span className="text-[10px] font-mono text-muted-foreground">{snap.timestamp}</span>
                </div>
              </div>
            </CardHeader>
            
            {changed.length > 0 && (
              <CardContent className="p-4 pt-0">
                <div className="overflow-x-auto border border-border bg-muted/20 p-2">
                  <table className="w-full text-xs">
                    <tbody>
                      {changed.map((e) => (
                        <tr key={e.key} className={`${KIND_CLASS[e.kind]} border-b border-border/30 last:border-0 hover:bg-muted/10`}>
                          <td className="w-6 py-1 pl-2 font-mono font-bold">{KIND_PREFIX[e.kind]}</td>
                          <td className="w-48 py-1 font-mono font-semibold text-foreground">{e.key}</td>
                          <td className="py-1 pr-2 break-all">
                            {e.kind === "added" && JSON.stringify(e.after)}
                            {e.kind === "removed" && JSON.stringify(e.before)}
                            {e.kind === "changed" && (
                              <span className="space-x-1">
                                <span className="line-through opacity-60">{JSON.stringify(e.before)}</span>
                                <span>→</span>
                                <span className="font-bold">{JSON.stringify(e.after)}</span>
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            )}
          </Card>
        );
      })}
    </div>
  );
}
