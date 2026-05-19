import type { ChronicleSnapshot } from "@/lib/chronicle-types";
import { diffSnapshots, type DiffEntry } from "@/lib/chronicle-diff";

const KIND_CLASS: Record<DiffEntry["kind"], string> = {
  added: "text-emerald-700",
  removed: "text-red-700",
  changed: "text-amber-700",
  unchanged: "text-gray-400",
};

const KIND_PREFIX: Record<DiffEntry["kind"], string> = {
  added: "+",
  removed: "-",
  changed: "~",
  unchanged: " ",
};

export function SnapshotsList({ snapshots }: { snapshots: ChronicleSnapshot[] }) {
  if (snapshots.length === 0)
    return <p className="text-sm text-gray-500">No snapshots recorded.</p>;
  const ordered = [...snapshots].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  return (
    <ul className="space-y-4" data-testid="snapshots-list">
      {ordered.slice().reverse().map((snap) => {
        const idx = ordered.findIndex((s) => s.snapshot_id === snap.snapshot_id);
        const prev = idx > 0 ? ordered[idx - 1] : null;
        const diff = diffSnapshots(prev, snap);
        const changed = diff.filter((e) => e.kind !== "unchanged");
        return (
          <li key={snap.snapshot_id} className="rounded border border-gray-200 p-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold">{snap.label ?? snap.snapshot_id}</h3>
                <div className="font-mono text-xs text-gray-500">{snap.timestamp}</div>
              </div>
              {snap.diff_summary && (
                <span className="text-xs text-gray-600">{snap.diff_summary}</span>
              )}
            </div>
            {changed.length > 0 && (
              <table className="mt-2 w-full text-xs">
                <tbody>
                  {changed.map((e) => (
                    <tr key={e.key} className={KIND_CLASS[e.kind]}>
                      <td className="w-6 pr-1 font-mono">{KIND_PREFIX[e.kind]}</td>
                      <td className="w-40 pr-2 font-mono">{e.key}</td>
                      <td className="font-mono">
                        {e.kind === "added" && JSON.stringify(e.after)}
                        {e.kind === "removed" && JSON.stringify(e.before)}
                        {e.kind === "changed" && `${JSON.stringify(e.before)} → ${JSON.stringify(e.after)}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </li>
        );
      })}
    </ul>
  );
}
