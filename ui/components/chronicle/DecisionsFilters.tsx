"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";

export function DecisionsFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const update = useCallback((key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value); else params.delete(key);
    router.push(`?${params.toString()}`);
  }, [router, searchParams]);

  return (
    <Card className="rounded-none border-border bg-muted/10 p-4">
      <CardContent className="p-0 flex flex-wrap gap-4 items-center" role="search" aria-label="Decisions filter">
        <label className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
          <span>Status:</span>
          <select
            className="rounded-none border border-input bg-background px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring text-foreground"
            aria-label="validation_status"
            defaultValue={searchParams.get("validation_status") ?? ""}
            onChange={(e) => update("validation_status", e.target.value)}
          >
            <option value="">ALL</option>
            <option value="pending">PENDING</option>
            <option value="validated">VALIDATED</option>
            <option value="rejected">REJECTED</option>
            <option value="superseded">SUPERSEDED</option>
          </select>
        </label>
        
        <label className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
          <span>Min Confidence:</span>
          <input
            type="number"
            min="0" max="1" step="0.05"
            className="w-20 rounded-none border border-input bg-background px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring text-foreground"
            aria-label="min_confidence"
            defaultValue={searchParams.get("min_confidence") ?? ""}
            onChange={(e) => update("min_confidence", e.target.value)}
          />
        </label>
      </CardContent>
    </Card>
  );
}
