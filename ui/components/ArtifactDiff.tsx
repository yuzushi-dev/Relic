// PR16D component skeleton — ArtifactDiff.
// All view models come from relic/ui contracts; this shell renders a redacted
// placeholder so the file contract is satisfied.
import type { ReactNode } from "react";

export interface ArtifactDiffProps {
  children?: ReactNode;
}

export function ArtifactDiff({ children }: ArtifactDiffProps) {
  return (
    <section aria-label="artifact diff" data-component="ArtifactDiff">
      {children ?? <em>{"[redacted placeholder]"}</em>}
    </section>
  );
}
