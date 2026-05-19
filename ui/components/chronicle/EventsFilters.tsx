"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

export function EventsFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const update = useCallback((key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value); else params.delete(key);
    router.push(`?${params.toString()}`);
  }, [router, searchParams]);

  return (
    <div className="flex flex-wrap gap-3" role="search" aria-label="Events filter">
      <label className="flex items-center gap-1 text-sm">
        severity:
        <select
          className="rounded border border-gray-300 px-2 py-1 text-xs"
          aria-label="severity"
          defaultValue={searchParams.get("severity") ?? ""}
          onChange={(e) => update("severity", e.target.value)}
        >
          <option value="">all</option>
          <option value="debug">debug</option>
          <option value="info">info</option>
          <option value="warning">warning</option>
          <option value="error">error</option>
          <option value="critical">critical</option>
        </select>
      </label>
      <label className="flex items-center gap-1 text-sm">
        category:
        <select
          className="rounded border border-gray-300 px-2 py-1 text-xs"
          aria-label="category"
          defaultValue={searchParams.get("category") ?? ""}
          onChange={(e) => update("category", e.target.value)}
        >
          <option value="">all</option>
          <option value="ingest">ingest</option>
          <option value="synthesis">synthesis</option>
          <option value="decision">decision</option>
          <option value="correction">correction</option>
          <option value="risk">risk</option>
          <option value="boundary">boundary</option>
          <option value="model_update">model_update</option>
          <option value="delivery">delivery</option>
        </select>
      </label>
      <label className="flex items-center gap-1 text-sm">
        sensitivity:
        <select
          className="rounded border border-gray-300 px-2 py-1 text-xs"
          aria-label="sensitivity"
          defaultValue={searchParams.get("sensitivity") ?? ""}
          onChange={(e) => update("sensitivity", e.target.value)}
        >
          <option value="">all</option>
          <option value="internal">internal</option>
          <option value="confidential">confidential</option>
          <option value="restricted">restricted</option>
        </select>
      </label>
    </div>
  );
}
