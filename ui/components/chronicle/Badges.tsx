import type { ReactNode } from "react";

const SEVERITY_STYLES: Record<string, string> = {
  debug: "bg-gray-100 text-gray-700",
  info: "bg-blue-100 text-blue-700",
  warning: "bg-amber-100 text-amber-800",
  error: "bg-red-100 text-red-700",
  critical: "bg-red-200 text-red-900 font-semibold",
};

const SENSITIVITY_STYLES: Record<string, string> = {
  public: "bg-green-100 text-green-700",
  internal: "bg-slate-100 text-slate-700",
  confidential: "bg-orange-100 text-orange-800",
  restricted: "bg-rose-200 text-rose-900",
};

const VALIDATION_STYLES: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  validated: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-700",
  superseded: "bg-gray-200 text-gray-700",
};

function Pill({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs ${className}`}>
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <Pill className={SEVERITY_STYLES[severity] ?? "bg-gray-100 text-gray-700"}>
      {severity}
    </Pill>
  );
}

export function SensitivityBadge({ sensitivity }: { sensitivity: string }) {
  return (
    <Pill className={SENSITIVITY_STYLES[sensitivity] ?? "bg-gray-100 text-gray-700"}>
      {sensitivity}
    </Pill>
  );
}

export function ValidationBadge({ status }: { status: string }) {
  return (
    <Pill className={VALIDATION_STYLES[status] ?? "bg-gray-100 text-gray-700"}>{status}</Pill>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2" aria-label={`confidence ${pct}%`}>
      <div className="h-1.5 w-24 rounded bg-gray-200">
        <div className="h-1.5 rounded bg-blue-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-600">{pct}%</span>
    </div>
  );
}
