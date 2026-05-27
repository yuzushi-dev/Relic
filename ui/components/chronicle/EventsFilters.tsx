"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";

export function EventsFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const update = useCallback((key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value); else params.delete(key);
    router.push(`?${params.toString()}`);
  }, [router, searchParams]);

  return (
    <Card className="rounded-none border-border bg-muted/10 p-4">
      <CardContent className="p-0 flex flex-wrap gap-4 items-center" role="search" aria-label="Events filter">
        <label className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
          <span>Severity:</span>
          <select
            className="rounded-none border border-input bg-background px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring text-foreground"
            aria-label="severity"
            defaultValue={searchParams.get("severity") ?? ""}
            onChange={(e) => update("severity", e.target.value)}
          >
            <option value="">ALL</option>
            <option value="debug">DEBUG</option>
            <option value="info">INFO</option>
            <option value="warning">WARNING</option>
            <option value="error">ERROR</option>
            <option value="critical">CRITICAL</option>
          </select>
        </label>
        
        <label className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
          <span>Category:</span>
          <select
            className="rounded-none border border-input bg-background px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring text-foreground"
            aria-label="category"
            defaultValue={searchParams.get("category") ?? ""}
            onChange={(e) => update("category", e.target.value)}
          >
            <option value="">ALL</option>
            <option value="ingest">INGEST</option>
            <option value="synthesis">SYNTHESIS</option>
            <option value="decision">DECISION</option>
            <option value="correction">CORRECTION</option>
            <option value="risk">RISK</option>
            <option value="boundary">BOUNDARY</option>
            <option value="model_update">MODEL UPDATE</option>
            <option value="delivery">DELIVERY</option>
          </select>
        </label>

        <label className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
          <span>Sensitivity:</span>
          <select
            className="rounded-none border border-input bg-background px-3 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring text-foreground"
            aria-label="sensitivity"
            defaultValue={searchParams.get("sensitivity") ?? ""}
            onChange={(e) => update("sensitivity", e.target.value)}
          >
            <option value="">ALL</option>
            <option value="internal">INTERNAL</option>
            <option value="confidential">CONFIDENTIAL</option>
            <option value="restricted">RESTRICTED</option>
          </select>
        </label>
      </CardContent>
    </Card>
  );
}
