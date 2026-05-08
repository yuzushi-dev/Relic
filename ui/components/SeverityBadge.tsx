// PR16D component skeleton — SeverityBadge.
// All view models come from relic/ui contracts; this shell renders a redacted
// placeholder so the file contract is satisfied.
import type { ReactNode } from "react";

export interface SeverityBadgeProps {
  children?: ReactNode;
}

export function SeverityBadge({ children }: SeverityBadgeProps) {
  return (
    <section aria-label="severity" data-component="SeverityBadge">
      {children ?? <em>{"[redacted placeholder]"}</em>}
    </section>
  );
}
