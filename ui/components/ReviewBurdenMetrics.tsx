// PR16D component skeleton — ReviewBurdenMetrics.
// All view models come from relic/ui contracts; this shell renders a redacted
// placeholder so the file contract is satisfied.
import type { ReactNode } from "react";

export interface ReviewBurdenMetricsProps {
  children?: ReactNode;
}

export function ReviewBurdenMetrics({ children }: ReviewBurdenMetricsProps) {
  return (
    <section aria-label="review burden metrics" data-component="ReviewBurdenMetrics">
      {children ?? <em>{"[redacted placeholder]"}</em>}
    </section>
  );
}
