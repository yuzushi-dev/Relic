"use client";
import type { ChronicleEvent } from "@/lib/chronicle-types";
import { SeverityBadge, SensitivityBadge } from "./Badges";

function formatTs(ts: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(ts));
}

export function EventsTable({ events }: { events: ChronicleEvent[] }) {
  if (events.length === 0)
    return <p className="text-sm text-gray-500">No events match the current filters.</p>;
  return (
    <table className="w-full text-sm" data-testid="events-table">
      <thead>
        <tr className="border-b border-gray-200 text-left text-xs text-gray-500">
          <th className="pb-2 pr-4">Time</th>
          <th className="pb-2 pr-4">Category</th>
          <th className="pb-2 pr-4">Severity</th>
          <th className="pb-2 pr-4">Sensitivity</th>
          <th className="pb-2 pr-4">Summary</th>
          <th className="pb-2">Actor</th>
        </tr>
      </thead>
      <tbody>
        {events.map((e) => (
          <tr key={e.event_id} className="border-b border-gray-100 hover:bg-gray-50">
            <td className="py-2 pr-4 font-mono text-xs text-gray-500">{formatTs(e.timestamp)}</td>
            <td className="py-2 pr-4">
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{e.category}</span>
            </td>
            <td className="py-2 pr-4"><SeverityBadge severity={e.severity} /></td>
            <td className="py-2 pr-4"><SensitivityBadge sensitivity={e.sensitivity} /></td>
            <td className="py-2 pr-4">{e.summary}</td>
            <td className="py-2 text-xs text-gray-500">{e.actor ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
