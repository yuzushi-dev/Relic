import type { ChronicleSnapshot } from "./chronicle-types";

export type DiffEntryKind = "added" | "removed" | "changed" | "unchanged";

export interface DiffEntry {
  key: string;
  kind: DiffEntryKind;
  before?: unknown;
  after?: unknown;
}

export function diffSnapshots(
  prev: ChronicleSnapshot | null,
  curr: ChronicleSnapshot,
): DiffEntry[] {
  const before = (prev?.state ?? {}) as Record<string, unknown>;
  const after = curr.state as Record<string, unknown>;
  const keys = new Set<string>([...Object.keys(before), ...Object.keys(after)]);
  const entries: DiffEntry[] = [];
  for (const key of keys) {
    const hasBefore = key in before;
    const hasAfter = key in after;
    if (!hasBefore && hasAfter) entries.push({ key, kind: "added", after: after[key] });
    else if (hasBefore && !hasAfter) entries.push({ key, kind: "removed", before: before[key] });
    else {
      const same = JSON.stringify(before[key]) === JSON.stringify(after[key]);
      entries.push({ key, kind: same ? "unchanged" : "changed", before: before[key], after: after[key] });
    }
  }
  return entries.sort((a, b) => a.key.localeCompare(b.key));
}
