import type { ChronicleDecision } from "@/lib/chronicle-types";
import { ValidationBadge, ConfidenceBar } from "./Badges";

function formatTs(ts: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(ts));
}

export function DecisionsList({ decisions }: { decisions: ChronicleDecision[] }) {
  if (decisions.length === 0)
    return <p className="text-sm text-gray-500">No decisions match the current filters.</p>;
  return (
    <ul className="space-y-3" data-testid="decisions-list">
      {decisions.map((d) => (
        <li key={d.decision_id} className="rounded border border-gray-200 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <h3 className="text-sm font-semibold">{d.title}</h3>
              <p className="mt-1 text-xs text-gray-600">{d.rationale}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <ValidationBadge status={d.validation_status} />
                <ConfidenceBar value={d.confidence} />
                <span className="text-xs text-gray-400">{formatTs(d.timestamp)}</span>
                {d.actor && <span className="text-xs text-gray-400">by {d.actor}</span>}
              </div>
              {(d.inputs.length > 0 || d.outputs.length > 0) && (
                <div className="mt-2 flex gap-4 text-xs text-gray-500">
                  {d.inputs.length > 0 && <span>inputs: {d.inputs.join(", ")}</span>}
                  {d.outputs.length > 0 && <span>outputs: {d.outputs.join(", ")}</span>}
                </div>
              )}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
