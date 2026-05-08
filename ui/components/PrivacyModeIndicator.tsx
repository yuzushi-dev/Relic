// PR16D component skeleton — PrivacyModeIndicator.
// All view models come from relic/ui contracts; this shell renders a redacted
// placeholder so the file contract is satisfied.
import type { ReactNode } from "react";

export interface PrivacyModeIndicatorProps {
  children?: ReactNode;
}

export function PrivacyModeIndicator({ children }: PrivacyModeIndicatorProps) {
  return (
    <section aria-label="privacy mode" data-component="PrivacyModeIndicator">
      {children ?? <em>{"[redacted placeholder]"}</em>}
    </section>
  );
}
