import type { ChronicleDecision } from "@/lib/chronicle-types";
import { ValidationBadge, ConfidenceBar } from "./Badges";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

function formatTs(ts: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(ts));
}

export function DecisionsList({ decisions }: { decisions: ChronicleDecision[] }) {
  if (decisions.length === 0)
    return <p className="text-sm text-muted-foreground italic p-4 text-center">No decisions match the current filters.</p>;
    
  return (
    <div className="space-y-4" data-testid="decisions-list">
      {decisions.map((d) => (
        <Card key={d.decision_id} className="rounded-none border-border">
          <CardHeader className="p-4 pb-2">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
              <CardTitle className="font-mono text-sm font-semibold text-foreground">{d.title}</CardTitle>
              <div className="flex flex-wrap items-center gap-2">
                <ValidationBadge status={d.validation_status} />
                <span className="text-[10px] font-mono text-muted-foreground">{formatTs(d.timestamp)}</span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-4 pt-0 space-y-3">
            <p className="text-sm text-muted-foreground leading-relaxed font-sans">{d.rationale}</p>
            
            <div className="flex flex-col md:flex-row md:items-center gap-4 pt-2 border-t border-border/50">
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase font-mono tracking-wider text-muted-foreground">Confidence:</span>
                <ConfidenceBar value={d.confidence} />
              </div>
              {d.actor && (
                <div className="text-xs text-muted-foreground font-mono">
                  <span>Actor: </span><strong className="text-foreground">{d.actor}</strong>
                </div>
              )}
            </div>

            {(d.inputs.length > 0 || d.outputs.length > 0) && (
              <div className="flex flex-col gap-1.5 text-xs font-mono pt-1 text-muted-foreground">
                {d.inputs.length > 0 && (
                  <div>
                    <span className="text-foreground font-semibold">Inputs:</span> {d.inputs.join(", ")}
                  </div>
                )}
                {d.outputs.length > 0 && (
                  <div>
                    <span className="text-foreground font-semibold">Outputs:</span> {d.outputs.join(", ")}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
