export type {
  ChronicleEvent,
  ChronicleDecision,
  ChronicleSnapshot,
  ChronicleProvenanceEdge,
  ChronicleStats,
} from "./chronicle-schemas";

export interface ChronicleEventFilters {
  category?: string;
  severity?: string;
  sensitivity?: string;
  from?: string;
  to?: string;
  limit?: number;
}

export interface ChronicleDecisionFilters {
  validation_status?: string;
  min_confidence?: number;
  limit?: number;
}

export interface ChronicleSnapshotFilters {
  label?: string;
  from?: string;
  to?: string;
  limit?: number;
}
