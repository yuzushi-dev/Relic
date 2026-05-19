"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

export function DecisionsFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const update = useCallback((key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value); else params.delete(key);
    router.push(`?${params.toString()}`);
  }, [router, searchParams]);

  return (
    <div className="flex flex-wrap gap-3" role="search" aria-label="Decisions filter">
      <label className="flex items-center gap-1 text-sm">
        status:
        <select
          className="rounded border border-gray-300 px-2 py-1 text-xs"
          aria-label="validation_status"
          defaultValue={searchParams.get("validation_status") ?? ""}
          onChange={(e) => update("validation_status", e.target.value)}
        >
          <option value="">all</option>
          <option value="pending">pending</option>
          <option value="validated">validated</option>
          <option value="rejected">rejected</option>
          <option value="superseded">superseded</option>
        </select>
      </label>
      <label className="flex items-center gap-1 text-sm">
        min confidence:
        <input
          type="number"
          min="0" max="1" step="0.05"
          className="w-16 rounded border border-gray-300 px-2 py-1 text-xs"
          aria-label="min_confidence"
          defaultValue={searchParams.get("min_confidence") ?? ""}
          onChange={(e) => update("min_confidence", e.target.value)}
        />
      </label>
    </div>
  );
}
