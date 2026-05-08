// PR16D component skeleton — EvidenceCard.
// All view models come from relic/ui contracts; this shell renders a redacted
// placeholder so the file contract is satisfied.
import type { ReactNode } from "react";

export interface EvidenceCardProps {
  children?: ReactNode;
}

export function EvidenceCard({ children }: EvidenceCardProps) {
  return (
    <section aria-label="evidence" data-component="EvidenceCard">
      {children ?? <em>{"[redacted placeholder]"}</em>}
    </section>
  );
}
