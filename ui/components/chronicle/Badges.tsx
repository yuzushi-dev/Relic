import type { ReactNode } from "react";

const SEVERITY_CLASSES: Record<string, string> = {
  debug: "bg-muted text-muted-foreground border-border",
  info: "bg-primary/10 text-primary border-primary/20",
  warning: "bg-warning/10 text-warning border-warning/20",
  error: "bg-destructive/10 text-destructive border-destructive/20",
  critical: "bg-destructive/20 text-destructive border-destructive/30 font-bold",
};

const SENSITIVITY_CLASSES: Record<string, string> = {
  public: "bg-success/10 text-success border-success/20",
  internal: "bg-secondary text-secondary-foreground border-border",
  confidential: "bg-warning/10 text-warning border-warning/20",
  restricted: "bg-destructive/10 text-destructive border-destructive/20 font-bold",
};

const VALIDATION_CLASSES: Record<string, string> = {
  pending: "bg-warning/10 text-warning border-warning/20",
  validated: "bg-success/10 text-success border-success/20",
  rejected: "bg-destructive/10 text-destructive border-destructive/20",
  superseded: "bg-muted text-muted-foreground border-border",
};

function Pill({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center border px-2 py-0.5 text-[10px] font-mono rounded-none ${className}`}>
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <Pill className={SEVERITY_CLASSES[severity] ?? "bg-muted text-muted-foreground border-border"}>
      {severity}
    </Pill>
  );
}

export function SensitivityBadge({ sensitivity }: { sensitivity: string }) {
  return (
    <Pill className={SENSITIVITY_CLASSES[sensitivity] ?? "bg-muted text-muted-foreground border-border"}>
      {sensitivity}
    </Pill>
  );
}

export function ValidationBadge({ status }: { status: string }) {
  return (
    <Pill className={VALIDATION_CLASSES[status] ?? "bg-muted text-muted-foreground border-border"}>
      {status}
    </Pill>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2" aria-label={`confidence ${pct}%`}>
      <div className="h-1.5 w-24 bg-muted border border-border rounded-none">
        <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-muted-foreground">{pct}%</span>
    </div>
  );
}
