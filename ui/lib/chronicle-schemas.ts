import { z } from "zod";

export const ChronicleSeverity = z.enum(["debug", "info", "warning", "error", "critical"]).catch("info");
export const ChronicleSensitivity = z.enum(["public", "internal", "confidential", "restricted", "safe", "researcher"]).catch("internal");
export const ChronicleValidationStatus = z.enum(["pending", "validated", "rejected", "superseded"]).catch("pending");

export const ChronicleEventSchema = z.object({
  event_id: z.string(),
  subject_id: z.string(),
  timestamp: z.string(),
  category: z.string(),
  severity: ChronicleSeverity,
  sensitivity: ChronicleSensitivity.default("internal"),
  actor: z.string().nullable().optional(),
  summary: z.string(),
  payload: z.record(z.string(), z.unknown()).optional().default({}),
  tags: z.array(z.string()).optional().default([]),
});

export const ChronicleDecisionSchema = z.object({
  decision_id: z.string(),
  subject_id: z.string(),
  timestamp: z.string(),
  title: z.string(),
  rationale: z.string(),
  confidence: z.number().min(0).max(1),
  validation_status: ChronicleValidationStatus,
  inputs: z.array(z.string()).optional().default([]),
  outputs: z.array(z.string()).optional().default([]),
  actor: z.string().nullable().optional(),
});

export const ChronicleSnapshotSchema = z.object({
  snapshot_id: z.string(),
  subject_id: z.string(),
  timestamp: z.string(),
  label: z.string().nullable().optional(),
  state: z.record(z.string(), z.unknown()),
  parent_snapshot_id: z.string().nullable().optional(),
  diff_summary: z.string().nullable().optional(),
});

export const ChronicleProvenanceEdgeSchema = z.object({
  edge_id: z.string(),
  from_id: z.string(),
  to_id: z.string(),
  relation: z.string(),
  timestamp: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional().default({}),
});

export const ChronicleStatsSchema = z.object({
  subject_id: z.string(),
  total_events: z.number(),
  total_decisions: z.number(),
  total_snapshots: z.number(),
  by_category: z.record(z.string(), z.number()),
  by_severity: z.record(z.string(), z.number()),
  by_sensitivity: z.record(z.string(), z.number()),
  first_event_at: z.string().nullable(),
  last_event_at: z.string().nullable(),
});

// Manually-defined types matching the Zod schema shapes
// Using optional (?) for fields that are .optional() or .nullable().optional() in Zod
export interface ChronicleEvent {
  event_id: string;
  subject_id: string;
  timestamp: string;
  category: string;
  severity: "debug" | "info" | "warning" | "error" | "critical";
  sensitivity: "public" | "internal" | "confidential" | "restricted" | "safe" | "researcher";
  actor?: string | null;
  summary: string;
  payload: Record<string, unknown>;
  tags: string[];
}

export interface ChronicleDecision {
  decision_id: string;
  subject_id: string;
  timestamp: string;
  title: string;
  rationale: string;
  confidence: number;
  validation_status: "pending" | "validated" | "rejected" | "superseded";
  inputs: string[];
  outputs: string[];
  actor?: string | null;
}

export interface ChronicleSnapshot {
  snapshot_id: string;
  subject_id: string;
  timestamp: string;
  label?: string | null;
  state: Record<string, unknown>;
  parent_snapshot_id?: string | null;
  diff_summary?: string | null;
}

export interface ChronicleProvenanceEdge {
  edge_id: string;
  from_id: string;
  to_id: string;
  relation: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface ChronicleStats {
  subject_id: string;
  total_events: number;
  total_decisions: number;
  total_snapshots: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  by_sensitivity: Record<string, number>;
  first_event_at: string | null;
  last_event_at: string | null;
}
