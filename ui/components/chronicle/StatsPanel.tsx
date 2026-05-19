import type { ChronicleStats } from "@/lib/chronicle-types";

interface Props {
  stats: ChronicleStats;
}

export function StatsPanel({ stats }: Props) {
  return (
    <div className="grid grid-cols-3 gap-4" data-testid="stats-panel">
      <div className="rounded border border-gray-200 p-3 text-center">
        <div className="text-2xl font-bold text-blue-600">{stats.total_events}</div>
        <div className="text-xs text-gray-500">Events</div>
      </div>
      <div className="rounded border border-gray-200 p-3 text-center">
        <div className="text-2xl font-bold text-purple-600">{stats.total_decisions}</div>
        <div className="text-xs text-gray-500">Decisions</div>
      </div>
      <div className="rounded border border-gray-200 p-3 text-center">
        <div className="text-2xl font-bold text-emerald-600">{stats.total_snapshots}</div>
        <div className="text-xs text-gray-500">Snapshots</div>
      </div>

      {stats.by_severity && Object.keys(stats.by_severity).length > 0 && (
        <div className="col-span-3 rounded border border-gray-200 p-3">
          <div className="mb-1 text-xs font-medium text-gray-500">By Severity</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.by_severity).filter(([, n]) => n > 0).map(([k, v]) => (
              <span key={k} className="rounded bg-slate-100 px-2 py-0.5 text-xs">
                {k}: {v}
              </span>
            ))}
          </div>
        </div>
      )}

      {stats.last_event_at && (
        <div className="col-span-3 text-xs text-gray-400">
          Last event: {new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(stats.last_event_at))}
        </div>
      )}
    </div>
  );
}
