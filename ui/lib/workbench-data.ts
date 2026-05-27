import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

import studyOverviewFixture from "../fixtures/researcher-workbench/study_overview.json";
import subjectOverviewFixture from "../fixtures/researcher-workbench/subject_overview_subj_001.json";
import subjectBaselineFixture from "../fixtures/researcher-workbench/subject_baseline_subj_001.json";
import eventStreamFixture from "../fixtures/researcher-workbench/event_stream_subj_001.json";
import subjectIntelligenceFixture from "../fixtures/researcher-workbench/subject_intelligence_subj_001.json";
import gumiProfileFixture from "../fixtures/researcher-workbench/gumi_profile_subj_001.json";
import chronicleEventsFixture from "../fixtures/chronicle/chronicle-events_subj_001.json";
import chronicleDecisionsFixture from "../fixtures/chronicle/chronicle-decisions_subj_001.json";
import chronicleSnapshotsFixture from "../fixtures/chronicle/chronicle-snapshots_subj_001.json";
import chronicleStatsFixture from "../fixtures/chronicle/chronicle-stats_subj_001.json";
import chronicleProvenanceFixture from "../fixtures/chronicle/chronicle-provenance_subj_001.json";
import {
  ChronicleEventSchema,
  ChronicleDecisionSchema,
  ChronicleSnapshotSchema,
  ChronicleProvenanceEdgeSchema,
  ChronicleStatsSchema,
  ChronicleEvent,
  ChronicleDecision,
  ChronicleSnapshot,
  ChronicleProvenanceEdge,
  ChronicleStats,
} from "./chronicle-schemas";
import type { ChronicleEventFilters, ChronicleDecisionFilters, ChronicleSnapshotFilters } from "./chronicle-types";

export type StudyOverview = typeof studyOverviewFixture;
export type SubjectOverview = typeof subjectOverviewFixture;
export type SubjectBaseline = typeof subjectBaselineFixture;
export type EventStream = typeof eventStreamFixture;
export type SubjectIntelligenceData = typeof subjectIntelligenceFixture;
export type SubjectRow = StudyOverview["subject_registry"][number];



type LiveSubjectProfile = {
  subject_id: string;
  experiment_id?: string;
  status?: string;
  hermes_profile_name?: string;
  hermes_home?: string;
  relic_subject_home?: string;
  profile_version?: number;
  created_at?: string;
  updated_at?: string;
};

type LiveCronData = {
  active_families: string[];
  pending_proactive_count: number;
  last_initiative_at: string | null;
  failed_jobs: number;
};

type LiveRiskData = {
  severity: "none" | "low" | "medium" | "high";
  flag_count: number;
  flags: string[];
};

export function getDataSource() {
  const source = process.env.RELIC_UI_DATA_SOURCE === "live" ? "live" : "demo";
  if (source === "live") {
    // Opt out of Next.js full-route cache so live data is always fresh.
    // noStore() is only called at request time in standalone server mode;
    // in static export (demo) this branch is never reached.
    const { unstable_noStore: noStore } = require("next/cache");
    noStore();
  }
  return source;
}

function relicHome() {
  return process.env.RELIC_HOME || path.join(process.cwd(), ".relic-live");
}

// Mirrors relic/paths.py:get_relic_home() exactly. Use ONLY for the canonical
// decision_events.jsonl reader (Plan §Task 1, Step 5). Other readers must keep
// relicHome() so the .relic-live dev fallback still works.
function relicHomeStrict() {
  const env = (process.env.RELIC_HOME || "").trim();
  if (env) return env;
  let home = process.env.HOME || "";
  if (!home) {
    try {
      // Mirror Python's Path.home(): fall back to /etc/passwd lookup when
      // HOME is unset (e.g. systemd-launched UI processes).
      const os = require("node:os");
      home = os.userInfo().homedir || "";
    } catch {
      home = "";
    }
  }
  return path.join(home, ".relic");
}

function hermesProfilesHome() {
  return process.env.HERMES_PROFILES_HOME || path.join(process.env.HOME || "", ".hermes", "profiles");
}

function readJson<T>(filePath: string): T | null {
  try {
    const content = fs.readFileSync(filePath, "utf8");
    return JSON.parse(content) as T;
  } catch (err) {
    console.error(`[Data] Error reading JSON from ${filePath}:`, err);
    return null;
  }
}

function readJsonLines<T>(filePath: string): T[] {
  try {
    return fs
      .readFileSync(filePath, "utf8")
      .split("\n")
      .filter(Boolean)
      .flatMap((line) => {
        try { return [JSON.parse(line) as T]; } catch { return []; }
      });
  } catch (err) {
    console.error(`[Data] Error reading JSONL from ${filePath}:`, err);
    return [];
  }
}

function liveProfiles() {
  const relic = relicHome();
  const subjectsDir = path.join(relic, "subjects");
  console.log(`[Data] Loading live profiles from: ${subjectsDir}`);
  try {
    const entries = fs.readdirSync(subjectsDir, { withFileTypes: true });
    console.log(`[Data] Found ${entries.length} entries in subjects directory`);
    return entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => {
        const profilePath = path.join(subjectsDir, entry.name, "subject_profile.json");
        const profile = readJson<LiveSubjectProfile>(profilePath);
        if (profile?.subject_id) {
          profile.relic_subject_home = path.join(relic, "subjects", profile.subject_id);
          if (profile.hermes_profile_name) {
            profile.hermes_home = path.join(hermesProfilesHome(), profile.hermes_profile_name);
          }
        } else {
          console.warn(`[Data] Invalid profile at ${profilePath}`);
        }
        return profile;
      })
      .filter((profile): profile is LiveSubjectProfile => Boolean(profile?.subject_id));
  } catch (err) {
    console.error(`[Data] Error listing subjects directory ${subjectsDir}:`, err);
    return [];
  }
}

function readCronData(profile: LiveSubjectProfile): LiveCronData {
  const subjectHome = profile.relic_subject_home ?? "";

  // Active cron families from install manifest written during bootstrap
  const cronManifest = subjectHome
    ? readJson<{ families?: string[] }>(path.join(subjectHome, "gumi_cron_manifest.json"))
    : null;
  const active_families = cronManifest?.families ?? [];

  // Pending proactive (Plan §Task 1, Step 5): read canonical decision_events.jsonl
  // under RELIC_HOME. Interim Task 1 semantics — count entries where
  // decision === "DELIVER" and outcome_status !== "silent"; decision-type
  // agnostic until Task 9 makes the proactive queue path the sole producer.
  let pending_proactive_count = 0;
  let last_initiative_at: string | null = null;
  {
    const logPath = path.join(relicHomeStrict(), "decision_events.jsonl");
    type CheckinEntry = {
      status?: string;
      decision?: string;
      timestamp?: string;
      created_at?: string;
      event_kind?: string;
      posture?: string;
      outcome_status?: string;
      wake_agent_emitted?: boolean;
      decision_type?: string;
    };
    const entries = readJsonLines<CheckinEntry>(logPath);
    for (const entry of entries) {
      const isPending =
        entry.decision === "DELIVER" && entry.outcome_status !== "silent";
      if (isPending) pending_proactive_count++;
      const ts = entry.timestamp ?? entry.created_at ?? null;
      if (ts && (!last_initiative_at || ts > last_initiative_at)) last_initiative_at = ts;
    }
  }

  // Failed jobs: count entries with returncode != 0 in install_manifest apply_results
  const manifest = subjectHome
    ? readJson<{ apply_results?: Array<{ returncode?: number }> }>(
        path.join(subjectHome, "gumi_cron_manifest.json")
      )
    : null;
  const failed_jobs = (manifest?.apply_results ?? []).filter((r) => r.returncode !== 0).length;

  return { active_families, pending_proactive_count, last_initiative_at, failed_jobs };
}

function readRiskData(profile: LiveSubjectProfile): LiveRiskData {
  const subjectHome = profile.relic_subject_home ?? "";
  if (!subjectHome) return { severity: "none", flag_count: 0, flags: [] };

  const sweetSpot = readJson<{ risk_flags?: string[] }>(
    path.join(subjectHome, "gumi_sweet_spot_config.json")
  );
  const flags = sweetSpot?.risk_flags ?? [];
  const flag_count = flags.length;
  const severity: LiveRiskData["severity"] =
    flag_count === 0 ? "none" : flag_count === 1 ? "low" : flag_count <= 3 ? "medium" : "high";
  return { severity, flag_count, flags };
}

// ---------------------------------------------------------------------------
// Subject DB (per-subject relic.db) query helper
// ---------------------------------------------------------------------------

type SubjectDbRow = Record<string, unknown>;

function querySubjectDb(dbPath: string, sql: string): SubjectDbRow[] {
  if (!fs.existsSync(dbPath)) return [];
  const python = process.env.RELIC_PYTHON || "python3";
  try {
    // One-liner python script: connect read-only (avoids WAL issues on ro mounts), execute, dump JSON
    const script = `import sqlite3,json,sys;db=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro&immutable=1",uri=True);db.row_factory=sqlite3.Row;rows=db.execute(sys.argv[2]).fetchall();print(json.dumps([dict(r) for r in rows]))`;
    const out = execFileSync(python, ["-c", script, dbPath, sql], {
      encoding: "utf8",
      timeout: 5000,
      maxBuffer: 8 * 1024 * 1024,
    });
    return JSON.parse(out) as SubjectDbRow[];
  } catch (err) {
    console.error(`[SubjectDb] query failed:`, (err as Error).message?.slice(0, 200));
    return [];
  }
}

function readConsentStatus(profile: LiveSubjectProfile): string {
  const subjectHome = profile.relic_subject_home ?? "";
  if (!subjectHome) return "not configured";
  const consent = readJson<{ delivery?: boolean; recorded_by_researcher_id?: string }>(
    path.join(subjectHome, "consent_record.json")
  );
  if (!consent) return "not configured";
  return consent.recorded_by_researcher_id ? "consented" : "partial";
}

function readLastInitiative(profile: LiveSubjectProfile): string | null {
  const subjectHome = profile.relic_subject_home ?? "";
  if (!subjectHome) return null;
  type DeliveryEntry = { created_at?: string; status?: string };
  const entries = readJsonLines<DeliveryEntry>(path.join(subjectHome, "delivery_decision_log.jsonl"));
  const sent = entries.filter((e) => e.status === "sent" || e.status === "delivery_ready");
  if (!sent.length) return null;
  return sent.reduce((latest, e) => {
    if (!e.created_at) return latest;
    return !latest || e.created_at > latest ? e.created_at : latest;
  }, null as string | null);
}

function liveSubjectRow(profile: LiveSubjectProfile): SubjectRow {
  const status =
    profile.status === "paused" ? "paused" : profile.status === "archived" ? "archived" : "active";
  const cron = readCronData(profile);
  const risk = readRiskData(profile);
  return {
    subject_id: profile.subject_id,
    gumi_instance_id: profile.hermes_profile_name || "",
    condition: profile.experiment_id || "unassigned",
    status,
    risk: risk.severity,
    hermes_profile_id: profile.hermes_profile_name || "",
    last_user_interaction_at: profile.updated_at || profile.created_at || "",
    last_gumi_initiative_at: cron.last_initiative_at ?? readLastInitiative(profile),
    pending_review: cron.pending_proactive_count > 0,
  };
}

export function getStudyOverview(): StudyOverview {
  if (getDataSource() !== "live") return studyOverviewFixture;

  const profiles = liveProfiles();
  const subjects = profiles.map(liveSubjectRow);
  const active = subjects.filter((s) => s.status === "active").length;
  const paused = subjects.filter((s) => s.status === "paused").length;
  const archived = subjects.filter((s) => s.status === "archived").length;
  const failedCronJobs = profiles.reduce((sum, p) => sum + readCronData(p).failed_jobs, 0);

  return {
    ...studyOverviewFixture,
    study_id: "live-researcher-ui",
    protocol_version: "live-runtime",
    last_validation_run: "",
    subjects_active: active,
    subjects_paused: paused,
    subjects_archived: archived,
    pending_reviews: subjects.filter((s) => s.pending_review).length,
    active_risk_alerts: subjects.filter((s) => s.risk !== "none").length,
    hermes_provisioning_failures: subjects.filter((s) => !s.hermes_profile_id).length,
    failed_cron_jobs: failedCronJobs,
    subject_registry: subjects,
  };
}

export function getSubjectOverview(subjectId: string): SubjectOverview | null {
  if (getDataSource() !== "live") return { ...subjectOverviewFixture, subject_id: subjectId };

  const profile = liveProfiles().find((p) => p.subject_id === subjectId);
  if (!profile) return null;

  const cron = readCronData(profile);
  const risk = readRiskData(profile);
  const consentStatus = readConsentStatus(profile);

  return {
    ...subjectOverviewFixture,
    subject_id: profile.subject_id,
    experiment_id: profile.experiment_id || "unassigned",
    subject_status: profile.status || "draft",
    active_condition: profile.experiment_id || "unassigned",
    consent_status: consentStatus,
    bootstrap_status: profile.status || "draft",
    active_gumi_instance: profile.hermes_profile_name || "not provisioned",
    last_user_interaction: profile.updated_at || profile.created_at || "",
    pending_review_count: cron.pending_proactive_count,
    hermes_profile_status: {
      profile_name: profile.hermes_profile_name || "not provisioned",
      hermes_home: profile.hermes_home || "",
      provisioned: Boolean(profile.hermes_profile_name),
    },
    risk_summary: risk,
    active_cron_modes: cron.active_families,
    pause_state: {
      pause_all: false,
      pause_proactive: false,
      pause_checkin: false,
      pause_followup: false,
      pause_images: false,
      pause_audio: false,
      pause_music: false,
      pause_diegetic_life: false,
      pause_relic_ingestion: false,
    },
  };
}

export function getSubjectBaseline(subjectId: string): SubjectBaseline | null {
  if (getDataSource() !== "live") return subjectBaselineFixture;

  const profile = liveProfiles().find((p) => p.subject_id === subjectId);
  if (!profile?.relic_subject_home) return null;

  const subjectHome = profile.relic_subject_home;
  const live = readJson<Record<string, unknown>>(path.join(subjectHome, "baseline_user_profile.json"));
  if (!live) return null;

  // Normalize risk_flags: may be string[] or {flag_category,...}[]
  const rawFlags = (live.risk_flags as unknown[]) ?? [];
  const risk_flags = rawFlags.map((f) => {
    if (typeof f === "string") {
      return { flag_category: f, severity: "low" as const, notes: null, reviewed_at: "", origin: "system-inferred" };
    }
    const fo = f as Record<string, unknown>;
    return {
      flag_category: String(fo.flag_category ?? fo.flag ?? f),
      severity: (fo.severity as "low" | "medium" | "high") ?? "low",
      notes: (fo.notes as string | null) ?? null,
      reviewed_at: String(fo.reviewed_at ?? ""),
      origin: String(fo.origin ?? "system-inferred"),
    };
  });

  // Normalize boundaries to {values: string[], origin} shape if needed
  const rawBoundaries = (live.boundaries as Record<string, unknown>) ?? {};
  const boundaries: Record<string, { values: string[]; origin: string }> = {};
  for (const [k, v] of Object.entries(rawBoundaries)) {
    if (Array.isArray(v)) {
      boundaries[k] = { values: v.map(String), origin: "subject-stated" };
    } else if (v && typeof v === "object" && "values" in v) {
      boundaries[k] = v as { values: string[]; origin: string };
    }
  }

  // opt_out_categories
  const rawOpt = (live.opt_out_categories as { values?: string[]; origin?: string } | undefined);
  const opt_out_categories = {
    values: rawOpt?.values ?? [],
    origin: rawOpt?.origin ?? "subject-stated",
  };

  // version_history from baseline artifact + profile_edit_log
  const baselineHistory = (live.version_history as SubjectBaseline["version_history"]) ?? [];
  type EditEntry = { step?: string; value?: string; ts?: string };
  const editLines = readJsonLines<EditEntry>(path.join(subjectHome, "profile_edit_log.jsonl"));
  const editHistory: SubjectBaseline["version_history"] = editLines
    .filter((e) => e.step === "status_changed" || e.step === "baseline_artifact_written")
    .map((e, i) => ({
      version: baselineHistory.length + i + 1,
      edited_at: e.ts ?? "",
      edited_by: "researcher",
      fields_changed: [e.step ?? "unknown"],
      edit_mode: "tui",
      change_summary: e.value ?? e.step ?? "",
    }));

  return {
    ...subjectBaselineFixture,
    schema_version: String(live.schema_version ?? "v1.0"),
    bootstrap_session_id: String(live.bootstrap_session_id ?? ""),
    researcher_id: String(live.researcher_id ?? ""),
    subject_id: subjectId,
    creation_date: String(live.creation_date ?? ""),
    baseline_method: String(live.baseline_method ?? "structured_interview_item_battery"),
    baseline_version: Number(live.baseline_version ?? 1),
    self_report_fields: (live.self_report_fields as SubjectBaseline["self_report_fields"]) ?? {},
    researcher_coded_fields: (live.researcher_coded_fields as SubjectBaseline["researcher_coded_fields"]) ?? {},
    system_inferred_fields: (live.system_inferred_fields as SubjectBaseline["system_inferred_fields"]) ?? subjectBaselineFixture.system_inferred_fields,
    interaction_preferences: (live.interaction_preferences as SubjectBaseline["interaction_preferences"]) ?? {},
    relational_expectations: (live.relational_expectations as SubjectBaseline["relational_expectations"]) ?? {},
    boundaries: boundaries as SubjectBaseline["boundaries"],
    opt_out_categories,
    risk_flags: risk_flags as SubjectBaseline["risk_flags"],
    version_history: [...baselineHistory, ...editHistory],
  };
}

export type GumiProfile = {
  subject_id: string;
  agent_name: string;
  soul_md: string | null;
  world_md: string | null;
  relationship_policy_md: string | null;
  domains: Record<string, unknown>;
  sweet_spot_score: number | null;
  risk_flags: string[];
  generation_mode: string;
  item_battery_scores: {
    tipi: Record<string, number>;
    ecrrs: Record<string, number>;
    project_calibration: Record<string, number>;
  } | null;
  created_at: string;
};

export function getGumiProfile(subjectId: string): GumiProfile | null {
  if (getDataSource() !== "live") return { ...gumiProfileFixture, subject_id: subjectId };

  const profile = liveProfiles().find((p) => p.subject_id === subjectId);
  if (!profile?.relic_subject_home) return null;

  const subjectHome = profile.relic_subject_home;
  const hermesHome = profile.hermes_home ?? "";

  const background = readJson<{
    domains?: Record<string, unknown>;
    generation_mode?: string;
    created_at?: string;
  }>(path.join(subjectHome, "gumi_background_profile.json"));

  const sweetSpot = readJson<{ sweet_spot_score?: number; risk_flags?: string[] }>(
    path.join(subjectHome, "gumi_sweet_spot_config.json")
  );

  const battery = readJson<{ scores?: { tipi?: Record<string, number>; ecrrs?: Record<string, number>; project_calibration?: Record<string, number> } }>(
    path.join(subjectHome, "item_battery_response.json")
  );

  function readText(filePath: string): string | null {
    try { return fs.readFileSync(filePath, "utf8"); } catch { return null; }
  }

  // Gumi name from identity generation log or hermes profile name
  const idLog = readJson<{ agent_name?: string }>(
    path.join(subjectHome, "provenance", "identity_generation_log.json")
  );
  const agentName = idLog?.agent_name ?? profile.hermes_profile_name?.replace("gumi-", "") ?? "Gumi";

  const worldText = readText(path.join(subjectHome, "gumi_world.md"));
  const worldFallback = hermesHome ? readText(path.join(hermesHome, "workspace", "gumi", "world.md")) : null;
  // Synthesize world_md from background domains if the dedicated file is empty/missing
  const worldSynthesized = (() => {
    const domains = background?.domains ?? {};
    if (!Object.keys(domains).length) return null;
    const lines: string[] = ["# Gumi World Profile (synthesized from background domains)\n"];
    for (const [domain, data] of Object.entries(domains)) {
      lines.push(`## ${domain.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}`);
      if (data && typeof data === "object" && !Array.isArray(data)) {
        for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
          const val = Array.isArray(v) ? v.join(", ") : String(v);
          lines.push(`- **${k.replace(/_/g, " ")}**: ${val}`);
        }
      } else {
        lines.push(`- ${String(data)}`);
      }
      lines.push("");
    }
    return lines.join("\n");
  })();
  const world_md = worldText || worldFallback || worldSynthesized;

  const relText = readText(path.join(subjectHome, "gumi_relationship_policy.md"));
  const relFallback = hermesHome ? readText(path.join(hermesHome, "workspace", "gumi", "relationship_policy.md")) : null;
  // Synthesize relationship_policy_md from boundary_policy.json if the file is empty/missing
  const relSynthesized = (() => {
    const bp = readJson<Record<string, unknown>>(path.join(subjectHome, "boundary_policy.json"));
    if (!bp) return null;
    const lines: string[] = ["# Relationship Policy (synthesized from boundary_policy.json)\n"];
    for (const [k, v] of Object.entries(bp)) {
      if (k === "created_at" || k === "updated_at" || k === "experiment_id") continue;
      const val = Array.isArray(v) ? (v.length ? v.join(", ") : "none") : String(v);
      lines.push(`- **${k.replace(/_/g, " ")}**: ${val}`);
    }
    return lines.join("\n");
  })();
  const relationship_policy_md = relText || relFallback || relSynthesized;

  return {
    subject_id: subjectId,
    agent_name: agentName,
    soul_md: hermesHome ? readText(path.join(hermesHome, "SOUL.md")) : null,
    world_md,
    relationship_policy_md,
    domains: background?.domains ?? {},
    sweet_spot_score: sweetSpot?.sweet_spot_score ?? null,
    risk_flags: sweetSpot?.risk_flags ?? [],
    generation_mode: background?.generation_mode ?? "unknown",
    item_battery_scores: battery?.scores
      ? {
          tipi: battery.scores.tipi ?? {},
          ecrrs: battery.scores.ecrrs ?? {},
          project_calibration: battery.scores.project_calibration ?? {},
        }
      : null,
    created_at: background?.created_at ?? "",
  };
}

export function getEventStream(subjectId: string): EventStream | null {
  if (getDataSource() !== "live") return eventStreamFixture;

  const profile = liveProfiles().find((p) => p.subject_id === subjectId);
  if (!profile?.relic_subject_home) return null;

  const subjectHome = profile.relic_subject_home;

  type DeliveryEntry = {
    event_type?: string; status?: string; created_at?: string;
    delivery_backend?: string; hermes_cron_job?: string;
    message_text_hash?: string; target_display?: string;
  };
  type BootstrapEntry = { step?: string; value?: string; ts?: string };
  type EditEntry = { step?: string; value?: string; ts?: string };

  const deliveries = readJsonLines<DeliveryEntry>(path.join(subjectHome, "delivery_decision_log.jsonl"));
  const bootstrapEntries = readJsonLines<BootstrapEntry>(path.join(subjectHome, "bootstrap_session.jsonl"));
  const editEntries = readJsonLines<EditEntry>(path.join(subjectHome, "profile_edit_log.jsonl"));

  const events: EventStream["events"] = [];
  let idx = 0;

  for (const e of bootstrapEntries) {
    if (!e.ts || !e.step) continue;
    events.push({
      event_id: `boot_${idx++}`,
      subject_id: subjectId,
      gumi_instance_id: profile.hermes_profile_name || "",
      hermes_profile_id: profile.hermes_profile_name || "",
      event_class: "system",
      ontological_class: "bootstrap",
      timestamp: e.ts,
      delivered: false,
      decision: "system",
      policy_snapshot: { rate_limit_mode: "auto-gated", careful_distancing: false, max_proactive_per_day: 0 },
      source_refs: [],
      content_preview: `[bootstrap] ${e.step}: ${String(e.value ?? "").slice(0, 80)}`,
      raw_content_availability: "none",
      eligible_for_user_model: false,
      eligible_for_experience_analysis: false,
      related_inference_ids: [],
      related_correction_ids: [],
      initiator: "system",
      risk_level: "none",
      has_user_response: false,
      has_correction: false,
      has_boundary_risk: false,
      has_media: false,
    });
  }

  for (const e of deliveries) {
    if (!e.created_at) continue;
    const isDelivered = e.status === "sent" || e.status === "delivery_ready";
    events.push({
      event_id: `del_${idx++}`,
      subject_id: subjectId,
      gumi_instance_id: profile.hermes_profile_name || "",
      hermes_profile_id: profile.hermes_profile_name || "",
      event_class: "gumi_initiative",
      ontological_class: e.hermes_cron_job || e.event_type || "delivery",
      timestamp: e.created_at,
      delivered: isDelivered,
      decision: e.status || "unknown",
      policy_snapshot: { rate_limit_mode: "auto-gated", careful_distancing: false, max_proactive_per_day: 0 },
      source_refs: [],
      content_preview: `[${e.delivery_backend ?? "backend"}] ${e.status ?? ""} → ${e.target_display ?? ""}`,
      raw_content_availability: isDelivered ? "partial" : "none",
      eligible_for_user_model: false,
      eligible_for_experience_analysis: isDelivered,
      related_inference_ids: [],
      related_correction_ids: [],
      initiator: "gumi",
      risk_level: "none",
      has_user_response: false,
      has_correction: false,
      has_boundary_risk: false,
      has_media: false,
    });
  }

  for (const e of editEntries) {
    if (!e.ts) continue;
    events.push({
      event_id: `edit_${idx++}`,
      subject_id: subjectId,
      gumi_instance_id: profile.hermes_profile_name || "",
      hermes_profile_id: profile.hermes_profile_name || "",
      event_class: "researcher_action",
      ontological_class: e.step || "profile_edit",
      timestamp: e.ts,
      delivered: false,
      decision: "researcher",
      policy_snapshot: { rate_limit_mode: "auto-gated", careful_distancing: false, max_proactive_per_day: 0 },
      source_refs: [],
      content_preview: `[edit] ${e.step}: ${String(e.value ?? "").slice(0, 80)}`,
      raw_content_availability: "none",
      eligible_for_user_model: false,
      eligible_for_experience_analysis: false,
      related_inference_ids: [],
      related_correction_ids: [],
      initiator: "researcher",
      risk_level: "none",
      has_user_response: false,
      has_correction: false,
      has_boundary_risk: false,
      has_media: false,
    });
  }

  // Merge checkin_exchanges from subject relic.db (primary source of recent events)
  const subjectDbFile = path.join(subjectHome, "relic.db");
  if (fs.existsSync(subjectDbFile)) {
    type CeRow = {
      id: number; asked_at: string; reply_captured_at: string | null;
      question_text: string; reply_text: string | null; facet_id: string | null;
      facet_name: string | null; posture: string | null; observations_extracted: number;
    };
    const ceRows = querySubjectDb(subjectDbFile, `
      SELECT ce.id, ce.asked_at, ce.reply_captured_at, ce.question_text, ce.reply_text,
             ce.facet_id, f.name as facet_name, ce.posture, ce.observations_extracted
      FROM checkin_exchanges ce
      LEFT JOIN facets f ON ce.facet_id = f.id
      ORDER BY ce.asked_at ASC
    `) as CeRow[];

    for (const row of ceRows) {
      // Add the checkin send event
      events.push({
        event_id: `ce_ask_${row.id}`,
        subject_id: subjectId,
        gumi_instance_id: profile.hermes_profile_name || "",
        hermes_profile_id: profile.hermes_profile_name || "",
        event_class: "gumi_initiative",
        ontological_class: "checkin_question",
        timestamp: row.asked_at ?? "",
        delivered: true,
        decision: "DELIVER",
        policy_snapshot: { rate_limit_mode: "auto-gated", careful_distancing: false, max_proactive_per_day: 0 },
        source_refs: [],
        content_preview: `[checkin] ${row.facet_name ?? row.facet_id ?? "facet"} · ${String(row.question_text ?? "").slice(0, 80)}`,
        raw_content_availability: "none",
        eligible_for_user_model: false,
        eligible_for_experience_analysis: true,
        related_inference_ids: [],
        related_correction_ids: [],
        initiator: "gumi",
        risk_level: "none",
        has_user_response: Boolean(row.reply_text),
        has_correction: false,
        has_boundary_risk: false,
        has_media: false,
      });
      // Add reply event if present
      if (row.reply_text && row.reply_captured_at) {
        events.push({
          event_id: `ce_reply_${row.id}`,
          subject_id: subjectId,
          gumi_instance_id: profile.hermes_profile_name || "",
          hermes_profile_id: profile.hermes_profile_name || "",
          event_class: "system",
          ontological_class: "checkin_reply",
          timestamp: row.reply_captured_at,
          delivered: false,
          decision: "received",
          policy_snapshot: { rate_limit_mode: "auto-gated", careful_distancing: false, max_proactive_per_day: 0 },
          source_refs: [],
          content_preview: `[reply] ${row.facet_name ?? row.facet_id ?? "facet"} · obs_extracted=${row.observations_extracted ?? 0}`,
          raw_content_availability: "none",
          eligible_for_user_model: true,
          eligible_for_experience_analysis: true,
          related_inference_ids: [],
          related_correction_ids: [],
          initiator: "subject",
          risk_level: "none",
          has_user_response: true,
          has_correction: false,
          has_boundary_risk: false,
          has_media: false,
        });
      }
    }
  }

  // Deduplicate by event_id
  const seen = new Set(events.map((e) => e.event_id));

  events.sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  return {
    subject_id: subjectId,
    generated_at: new Date().toISOString(),
    stream: "live",
    events,
  };
}

// ---------------------------------------------------------------------------
// Chronicle integration
// ---------------------------------------------------------------------------

const SUBJECT_ID_RE = /^[a-zA-Z0-9_-]+$/;

type ChronicleRow = {
  event_id: string;
  event_type: string;
  event_category: string;
  timestamp: string;
  subject_id: string;
  source_module: string | null;
  actor_type: string | null;
  payload: string | null;
  payload_redacted: number;
  sensitivity: string | null;
  severity: string | null;
  hermes_profile_id: string | null;
};

function _chronicleEventClass(category: string): string {
  switch (category) {
    case "decision": return "gumi_initiative";
    case "agent":    return "gumi_initiative";
    case "researcher": return "researcher_action";
    default:         return "system";
  }
}

function _chronicleRiskLevel(sensitivity: string | null, severity: string | null): string {
  const sev = severity ?? "info";
  const sens = sensitivity ?? "safe";
  if (sens === "intimate" || sev === "critical") return "high";
  if (sens === "PII"      || sev === "error")    return "medium";
  if (sev === "warn")                             return "low";
  return "none";
}

function _chroniclePreview(row: ChronicleRow): string {
  let payloadHint = "";
  if (!row.payload_redacted && row.payload) {
    try {
      const p = JSON.parse(row.payload) as Record<string, unknown>;
      const parts: string[] = [];
      if (p.decision)      parts.push(`decision=${p.decision}`);
      if (p.reason_codes && Array.isArray(p.reason_codes)) parts.push(p.reason_codes.join(","));
      if (p.trigger)       parts.push(`trigger=${p.trigger}`);
      if (p.step)          parts.push(`step=${p.step}`);
      if (p.count !== undefined) parts.push(`count=${p.count}`);
      payloadHint = parts.join(" ").slice(0, 80);
    } catch { /* skip */ }
  }
  const src = row.source_module?.replace("relic.", "") ?? row.event_category;
  return `[${row.event_type}] ${src}${payloadHint ? " · " + payloadHint : ""}`;
}

function chronicleQuery(subjectId: string, limit = 500): EventStream["events"] {
  if (!SUBJECT_ID_RE.test(subjectId)) return [];
  const python = process.env.RELIC_PYTHON || "python3";
  try {
    const out = execFileSync(
      python,
      ["-m", "relic.chronicle.cli.main", "query",
       "--subject", subjectId,
       "--limit", String(limit),
       "--format", "jsonl",
       "--no-audit"],
      {
        encoding: "utf8",
        env: { ...process.env },
        timeout: 8000,
        maxBuffer: 16 * 1024 * 1024,
      }
    );
    const rows: ChronicleRow[] = out
      .split("\n")
      .filter(Boolean)
      .flatMap((l) => { try { return [JSON.parse(l) as ChronicleRow]; } catch { return []; } });

    return rows.map((row) => ({
      event_id: `chr_${row.event_id}`,
      subject_id: row.subject_id,
      gumi_instance_id: row.hermes_profile_id ?? "",
      hermes_profile_id: row.hermes_profile_id ?? "",
      event_class: _chronicleEventClass(row.event_category),
      ontological_class: row.event_type,
      timestamp: row.timestamp,
      delivered: false,
      decision: row.event_category,
      policy_snapshot: { rate_limit_mode: "auto-gated", careful_distancing: false, max_proactive_per_day: 0 },
      source_refs: [],
      content_preview: _chroniclePreview(row),
      raw_content_availability: row.payload_redacted ? "none" : "partial",
      eligible_for_user_model: false,
      eligible_for_experience_analysis: false,
      related_inference_ids: [],
      related_correction_ids: [],
      initiator: row.actor_type ?? row.source_module?.split(".").pop() ?? "system",
      risk_level: _chronicleRiskLevel(row.sensitivity, row.severity),
      has_user_response: false,
      has_correction: false,
      has_boundary_risk: false,
      has_media: false,
    }));
  } catch (err) {
    console.error("[chronicle] query failed:", (err as Error).message?.slice(0, 200));
    return [];
  }
}

export function getSubjectIntelligence(subjectId: string): SubjectIntelligenceData | null {
  if (getDataSource() !== "live") return subjectIntelligenceFixture;

  const profile = liveProfiles().find((p) => p.subject_id === subjectId);
  if (!profile?.relic_subject_home) return null;

  const subjectHome = profile.relic_subject_home;
  const dbPath = path.join(subjectHome, "relic.db");

  const baselineProfile = readJson<{
    researcher_coded_fields?: Record<string, { value?: unknown; origin?: string }>;
    self_report_fields?: Record<string, { value?: unknown; origin?: string }>;
  }>(path.join(subjectHome, "baseline_user_profile.json"));

  const rcf = baselineProfile?.researcher_coded_fields ?? {};
  const srf = baselineProfile?.self_report_fields ?? {};

  // ── Read full 60-facet model from relic.db (traits + facets tables) ─────────
  type TraitRow = {
    facet_id: string; value_position: number | null; confidence: number;
    observation_count: number; name: string; category: string;
    spectrum_low: string | null; spectrum_high: string | null; notes: string | null;
  };
  const traitRows = querySubjectDb(dbPath, `
    SELECT t.facet_id, t.value_position, t.confidence, t.observation_count,
           f.name, f.category, f.spectrum_low, f.spectrum_high, t.notes
    FROM traits t
    JOIN facets f ON t.facet_id = f.id
    ORDER BY f.category, f.name
  `) as TraitRow[];

  // Group traits by category into facet_groups
  const byCategory: Record<string, SubjectIntelligenceData["facet_groups"][number]["facets"]> = {};
  for (const row of traitRows) {
    const cat = (row.category ?? "other").replace(/_/g, " ");
    const label = cat.charAt(0).toUpperCase() + cat.slice(1);
    if (!byCategory[label]) byCategory[label] = [];
    const conf = typeof row.confidence === "number" ? row.confidence : 0;
    byCategory[label].push({
      facet: (row.name ?? row.facet_id).replace(/_/g, " "),
      position: typeof row.value_position === "number" ? row.value_position : 0.5,
      confidence: conf,
      confidence_label: conf >= 0.7 ? "high" : conf >= 0.4 ? "medium" : "low",
      observations: typeof row.observation_count === "number" ? row.observation_count : 0,
      left_anchor: row.spectrum_low ?? "low",
      right_anchor: row.spectrum_high ?? "high",
    });
  }

  const facet_groups: SubjectIntelligenceData["facet_groups"] = Object.entries(byCategory).map(
    ([group, facets]) => ({ group, facets })
  );
  const allFacets = facet_groups.flatMap((g) => g.facets);

  const facets_total = traitRows.length || subjectIntelligenceFixture.model_summary.facets_total;
  const facets_modeled = traitRows.filter(
    (r) => typeof r.value_position === "number" && r.observation_count > 0
  ).length;

  // ── Observations count from DB ───────────────────────────────────────────────
  const obsCountRows = querySubjectDb(dbPath, "SELECT COUNT(*) as cnt FROM observations");
  const seed_observations = Number((obsCountRows[0]?.cnt) ?? 0);
  const extraction_signals = traitRows.filter(r => r.observation_count > 0).length;

  // ── Hypotheses from DB ───────────────────────────────────────────────────────
  type HypRow = { id: number; hypothesis: string; confidence: number; status: string; created_at: string };
  const hypRows = querySubjectDb(dbPath, `
    SELECT id, hypothesis, confidence, status, created_at
    FROM hypotheses
    WHERE confidence > 0.5
    ORDER BY confidence DESC
    LIMIT 20
  `) as HypRow[];

  const hypotheses: SubjectIntelligenceData["hypotheses"] = hypRows.map((h) => {
    const conf = typeof h.confidence === "number" ? h.confidence : 0.5;
    return {
      title: String(h.hypothesis ?? "").slice(0, 80) + (String(h.hypothesis ?? "").length > 80 ? "…" : ""),
      summary: String(h.hypothesis ?? ""),
      confidence: conf,
      confidence_label: conf >= 0.7 ? "high" : conf >= 0.4 ? "medium" : "low",
      facets: [],
    };
  });

  // ── Top traits from high-confidence facets ───────────────────────────────────
  const topTraitFacets = [...allFacets]
    .filter((f) => f.confidence >= 0.5 && f.observations > 0)
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 6);
  const topTraits: string[] = topTraitFacets.map(
    (f) => `${f.facet}: ${f.position > 0.65 ? f.right_anchor : f.position < 0.35 ? f.left_anchor : "mid"} (${Math.round(f.confidence * 100)}%)`
  );

  // ── Behavioral summary ───────────────────────────────────────────────────────
  // Pull from top high-confidence traits notes for richer summary
  type NoteRow = { name: string; notes: string; confidence: number; value_position: number };
  const noteRows = querySubjectDb(dbPath, `
    SELECT f.name, t.notes, t.confidence, t.value_position
    FROM traits t
    JOIN facets f ON t.facet_id = f.id
    WHERE t.notes IS NOT NULL AND t.confidence > 0.5 AND t.value_position IS NOT NULL
    ORDER BY t.confidence DESC, t.observation_count DESC
    LIMIT 5
  `) as NoteRow[];
  // Filter and pick the best note segment per trait.
  // Notes are pipe-separated extraction outputs; the first segment is often the most recent
  // (and may be garbage if extracted from a technical/assistant context). Strategy:
  // - Split on "|", trim each segment
  // - Drop segments that look like file paths, URLs, code, or are < 20 chars
  // - Pick the first surviving segment; skip the trait entirely if none survive
  function _bestNote(raw: string): string | null {
    // Match file system paths, URLs, code fences, and SQL statement patterns.
    // Bare SQL keywords (SELECT, IN, AND) are intentionally NOT matched — they appear
    // in natural Italian/English prose. Instead match statement-level patterns only.
    const BAD = /\/home\/|\/tmp\/|https?:\/\/|```|`[^`]{10}|\.json\b|\.py\b|\.sh\b|\bpath\b.*\/|\bSELECT\b.{1,60}\bFROM\b|\bINSERT\s+INTO\b/i;
    const segs = String(raw).split("|").map((s) => s.trim()).filter((s) => s.length >= 20 && !BAD.test(s));
    return segs[0] ?? null;
  }
  const summaryParts: string[] = noteRows.flatMap((n) => {
    const note = _bestNote(String(n.notes ?? ""));
    if (!note) return [];
    const dir = (n.value_position ?? 0.5) > 0.6 ? "high" : (n.value_position ?? 0.5) < 0.4 ? "low" : "mid";
    const truncated = note.length > 120 ? note.slice(0, 120) + "…" : note;
    return [`${(n.name ?? "").replace(/_/g, " ")} [${dir}]: ${truncated}`];
  });
  if (rcf.communication_style?.value) summaryParts.unshift(`Communication style: ${rcf.communication_style.value}`);
  const summary = summaryParts.join("\n") || "Behavioral model populated from relic.db observations.";

  // ── Top confidence facets ────────────────────────────────────────────────────
  const topConfidence = [...allFacets]
    .filter((f) => f.observations > 0)
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 5);

  // ── Extraction sample ────────────────────────────────────────────────────────
  type ExSampleRow = { name: string; value_position: number; confidence: number; source_type: string; content: string };
  const exSampleRows = querySubjectDb(dbPath, `
    SELECT f.name, o.signal_position as value_position, o.signal_strength as confidence,
           o.source_type, o.content
    FROM observations o
    JOIN facets f ON o.facet_id = f.id
    WHERE o.signal_position IS NOT NULL
    ORDER BY o.signal_strength DESC
    LIMIT 5
  `) as ExSampleRow[];
  const extraction_sample = exSampleRows.map((r) => ({
    facet: (r.name ?? "").replace(/_/g, " "),
    direction: (r.value_position ?? 0.5) > 0.6 ? "positive" : (r.value_position ?? 0.5) < 0.4 ? "negative" : "neutral",
    strength: typeof r.confidence === "number" ? r.confidence : 0.5,
    source: r.source_type ?? "observation",
  }));

  // ── Artifacts ────────────────────────────────────────────────────────────────
  const artifacts: SubjectIntelligenceData["artifacts"] = [
    { name: "relic.db (traits)", kind: "model_snapshot", lineage: `${subjectId}/relic.db#traits` },
    { name: "relic.db (observations)", kind: "model_snapshot", lineage: `${subjectId}/relic.db#observations` },
    { name: "baseline_user_profile.json", kind: "baseline", lineage: `${subjectId}/baseline_user_profile` },
  ];
  if (fs.existsSync(path.join(subjectHome, "subject_baseline.json"))) {
    artifacts.push({ name: "subject_baseline.json", kind: "baseline", lineage: `${subjectId}/subject_baseline` });
  }

  return {
    subject_id: subjectId,
    generated_at: new Date().toISOString(),
    model_summary: {
      facets_modeled,
      facets_total,
      seed_observations,
      extraction_signals,
      hypotheses: hypotheses.length,
      summary,
    },
    top_traits: topTraits,
    active_goals: [],
    top_confidence_facets: topConfidence,
    hypotheses,
    facet_groups,
    transcript: [],
    extraction_sample,
    artifacts,
  };
}

// ── Chronicle data-layer functions ───────────────────────────────────────────

export interface ChronicleEventsResult {
  events: ChronicleEvent[];
  total: number;
}

export interface ChronicleDecisionsResult {
  decisions: ChronicleDecision[];
  total: number;
}

export interface ChronicleSnapshotsResult {
  snapshots: ChronicleSnapshot[];
  total: number;
}

export interface ChronicleProvenanceResult {
  edges: ChronicleProvenanceEdge[];
}

function tryJSON<T = unknown>(s: unknown, fallback: T): T {
  if (typeof s !== "string") return (s as T) ?? fallback;
  try { return JSON.parse(s) as T; } catch { return fallback; }
}

function normalizeLiveEvent(r: Record<string, unknown>): ChronicleEvent {
  const payload = tryJSON<Record<string, unknown>>(r.payload, {});
  const tagsRaw = tryJSON<unknown>(r.tags, []);
  const tags = Array.isArray(tagsRaw) ? tagsRaw.map(String) : [];
  const eventType = String(r.event_type ?? "");
  const summaryBits: string[] = [];
  if (eventType) summaryBits.push(eventType);
  const payloadPreview = Object.entries(payload).slice(0, 2)
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`).join(", ");
  if (payloadPreview) summaryBits.push(payloadPreview);
  return {
    event_id: String(r.event_id ?? ""),
    subject_id: String(r.subject_id ?? ""),
    timestamp: String(r.timestamp ?? ""),
    category: String(r.event_category ?? r.category ?? "unknown"),
    severity: ChronicleEventSchema.shape.severity.parse(r.severity ?? "info") as ChronicleEvent["severity"],
    sensitivity: ChronicleEventSchema.shape.sensitivity.parse(r.sensitivity ?? "internal") as ChronicleEvent["sensitivity"],
    actor: (r.actor_id as string) ?? (r.source_module as string) ?? null,
    summary: summaryBits.join(" · ") || eventType || "event",
    payload,
    tags,
  };
}

function normalizeLiveDecision(r: Record<string, unknown>): ChronicleDecision {
  const inputs = tryJSON<unknown>(r.observable_inputs, {});
  const outputs = tryJSON<unknown>(r.observable_outputs, {});
  const inputArr = Array.isArray(inputs) ? inputs.map(String)
    : (inputs && typeof inputs === "object") ? Object.keys(inputs as object) : [];
  const outputArr = Array.isArray(outputs) ? outputs.map(String)
    : (outputs && typeof outputs === "object") ? Object.keys(outputs as object) : [];
  const conf = r.confidence;
  return {
    decision_id: String(r.decision_id ?? ""),
    subject_id: String(r.subject_id ?? ""),
    timestamp: String(r.timestamp ?? ""),
    title: String(r.decision_kind ?? "decision"),
    rationale: String(r.rationale_summary ?? ""),
    confidence: typeof conf === "number" ? conf : 0,
    validation_status: ChronicleDecisionSchema.shape.validation_status.parse(r.validation_status ?? "pending") as ChronicleDecision["validation_status"],
    inputs: inputArr,
    outputs: outputArr,
    actor: (r.actor_id as string) ?? null,
  };
}

function normalizeLiveSnapshot(r: Record<string, unknown>): ChronicleSnapshot {
  const state = tryJSON<Record<string, unknown>>(r.state ?? r.payload, {});
  return {
    snapshot_id: String(r.snapshot_id ?? r.event_id ?? ""),
    subject_id: String(r.subject_id ?? ""),
    timestamp: String(r.timestamp ?? ""),
    label: (r.snapshot_type as string) ?? (r.label as string) ?? null,
    state,
    parent_snapshot_id: (r.parent_snapshot_id as string) ?? null,
    diff_summary: (r.diff_summary as string) ?? null,
  };
}

// Chronicle live functions: read from subject-specific relic.db
// (chronicle_events table not yet in global DB; subject DB has checkin_exchanges,
//  model_snapshots, and delivery_decision_log.jsonl for decisions)

function _subjectDbPath(subjectId: string): string | null {
  const profile = liveProfiles().find((p) => p.subject_id === subjectId);
  if (!profile?.relic_subject_home) return null;
  const p = path.join(profile.relic_subject_home, "relic.db");
  return fs.existsSync(p) ? p : null;
}

function chronicleLiveEvents(subjectId: string, filters?: ChronicleEventFilters) {
  const dbPath = _subjectDbPath(subjectId);
  if (!dbPath) return [];

  const limit = filters?.limit ?? 200;
  // Map checkin_exchanges to chronicle events
  type CeRow = {
    id: number; asked_at: string; reply_captured_at: string | null;
    question_text: string; reply_text: string | null; facet_id: string | null;
    facet_name: string | null; posture: string | null; observations_extracted: number;
  };
  const rows = querySubjectDb(dbPath, `
    SELECT ce.id, ce.asked_at, ce.reply_captured_at, ce.question_text, ce.reply_text,
           ce.facet_id, f.name as facet_name, ce.posture, ce.observations_extracted
    FROM checkin_exchanges ce
    LEFT JOIN facets f ON ce.facet_id = f.id
    ORDER BY ce.asked_at DESC
    LIMIT ${limit * 2}
  `) as CeRow[];

  const events: ChronicleEvent[] = rows.map((row) => {
    const ts = row.reply_captured_at ?? row.asked_at ?? "";
    const facetLabel = row.facet_name ?? row.facet_id ?? "unknown";
    const hasReply = Boolean(row.reply_text);
    const category = hasReply ? "agent" : "system";
    const summaryText = hasReply
      ? `checkin reply · ${facetLabel} · obs: ${row.observations_extracted ?? 0}`
      : `checkin sent · ${facetLabel}`;
    return {
      event_id: `ce_${row.id}`,
      subject_id: subjectId,
      timestamp: ts,
      category,
      severity: "info" as ChronicleEvent["severity"],
      sensitivity: "internal" as ChronicleEvent["sensitivity"],
      actor: "gumi",
      summary: summaryText,
      payload: {
        facet: facetLabel,
        posture: row.posture,
        has_reply: hasReply,
        question_preview: String(row.question_text ?? "").slice(0, 80),
      },
      tags: [facetLabel, row.posture ?? ""].filter(Boolean),
    };
  });

  return events;
}

function chronicleLiveDecisions(subjectId: string, filters?: ChronicleDecisionFilters) {
  const profile = liveProfiles().find((p) => p.subject_id === subjectId);
  if (!profile?.relic_subject_home) return [];

  const limit = filters?.limit ?? 100;
  type DelivEntry = {
    created_at?: string; status?: string; event_type?: string;
    delivery_backend?: string; hermes_cron_job?: string; target_display?: string;
  };
  const entries = readJsonLines<DelivEntry>(
    path.join(profile.relic_subject_home, "delivery_decision_log.jsonl")
  ).slice(0, limit * 2);

  return entries
    .filter((e) => e.created_at)
    .slice(0, limit)
    .map((e, i): ChronicleDecision => ({
      decision_id: `del_${i}`,
      subject_id: subjectId,
      timestamp: e.created_at ?? "",
      title: e.hermes_cron_job ?? e.event_type ?? "delivery",
      rationale: `status=${e.status ?? "?"} via ${e.delivery_backend ?? "?"} → ${e.target_display ?? "?"}`,
      confidence: e.status === "sent" || e.status === "delivery_ready" ? 0.9 : 0.4,
      validation_status: "pending" as ChronicleDecision["validation_status"],
      inputs: [e.hermes_cron_job ?? e.event_type ?? "trigger"].filter(Boolean),
      outputs: [e.target_display ?? e.delivery_backend ?? "output"].filter(Boolean),
      actor: "gumi",
    }));
}

function chronicleLiveSnapshots(subjectId: string, filters?: ChronicleSnapshotFilters) {
  const dbPath = _subjectDbPath(subjectId);
  if (!dbPath) return [];

  const limit = filters?.limit ?? 20;
  type SnapRow = {
    id: number; snapshot_at: string; total_observations: number;
    avg_confidence: number; coverage_pct: number; snapshot_data: string | null;
  };
  const rows = querySubjectDb(dbPath, `
    SELECT id, snapshot_at, total_observations, avg_confidence, coverage_pct, snapshot_data
    FROM model_snapshots
    ORDER BY snapshot_at DESC
    LIMIT ${limit}
  `) as SnapRow[];

  return rows.map((row): ChronicleSnapshot => ({
    snapshot_id: `snap_${row.id}`,
    subject_id: subjectId,
    timestamp: row.snapshot_at ?? "",
    label: `model_snapshot`,
    state: {
      total_observations: row.total_observations,
      avg_confidence: row.avg_confidence,
      coverage_pct: row.coverage_pct,
    },
    parent_snapshot_id: null,
    diff_summary: `obs=${row.total_observations} conf=${(row.avg_confidence ?? 0).toFixed(3)} cov=${(row.coverage_pct ?? 0).toFixed(1)}%`,
  }));
}

function chronicleLiveStats(subjectId: string): ChronicleStats | null {
  const dbPath = _subjectDbPath(subjectId);
  if (!dbPath) return null;

  type CountRow = { cnt: number };
  const ceCount = (querySubjectDb(dbPath, "SELECT COUNT(*) as cnt FROM checkin_exchanges") as CountRow[])[0]?.cnt ?? 0;
  const delCount = (() => {
    const profile = liveProfiles().find((p) => p.subject_id === subjectId);
    if (!profile?.relic_subject_home) return 0;
    return readJsonLines(path.join(profile.relic_subject_home, "delivery_decision_log.jsonl")).length;
  })();
  const snapCount = (querySubjectDb(dbPath, "SELECT COUNT(*) as cnt FROM model_snapshots") as CountRow[])[0]?.cnt ?? 0;
  const obsCount = (querySubjectDb(dbPath, "SELECT COUNT(*) as cnt FROM observations") as CountRow[])[0]?.cnt ?? 0;

  type FirstLastRow = { first_at: string | null; last_at: string | null };
  const dateRange = (querySubjectDb(dbPath, "SELECT MIN(asked_at) as first_at, MAX(asked_at) as last_at FROM checkin_exchanges") as FirstLastRow[])[0];

  return {
    subject_id: subjectId,
    total_events: ceCount,
    total_decisions: delCount,
    total_snapshots: snapCount,
    by_category: { checkin: ceCount, observations: obsCount },
    by_severity: { info: ceCount },
    by_sensitivity: { internal: ceCount },
    first_event_at: dateRange?.first_at ?? null,
    last_event_at: dateRange?.last_at ?? null,
  };
}

function chronicleLiveProvenance(subjectId: string) {
  // No provenance edges in subject DB yet; return empty
  return { edges: [] };
}

function applyEventFilters(events: ChronicleEvent[], filters?: ChronicleEventFilters) {
  let result = events;
  if (filters?.severity) result = result.filter((e) => e.severity === filters.severity);
  if (filters?.category) result = result.filter((e) => e.category === filters.category);
  if (filters?.sensitivity) result = result.filter((e) => e.sensitivity === filters.sensitivity);
  if (filters?.from) result = result.filter((e) => e.timestamp >= filters.from!);
  if (filters?.to) result = result.filter((e) => e.timestamp <= filters.to!);
  if (filters?.limit) result = result.slice(0, filters.limit);
  return result;
}

function applyDecisionFilters(decisions: ChronicleDecision[], filters?: ChronicleDecisionFilters) {
  let result = decisions;
  if (filters?.validation_status) result = result.filter((d) => d.validation_status === filters.validation_status);
  if (filters?.min_confidence !== undefined) result = result.filter((d) => d.confidence >= filters.min_confidence!);
  if (filters?.limit) result = result.slice(0, filters.limit);
  return result;
}

function applySnapshotFilters(snapshots: ChronicleSnapshot[], filters?: ChronicleSnapshotFilters) {
  let result = snapshots;
  if (filters?.label) result = result.filter((s) => s.label?.toLowerCase().includes(filters.label!.toLowerCase()));
  if (filters?.from) result = result.filter((s) => s.timestamp >= filters.from!);
  if (filters?.to) result = result.filter((s) => s.timestamp <= filters.to!);
  if (filters?.limit) result = result.slice(0, filters.limit);
  return result;
}

export function chronicleEvents(subjectId: string, filters?: ChronicleEventFilters): ChronicleEventsResult {
  if (getDataSource() === "live") {
    const liveEvents = chronicleLiveEvents(subjectId, filters);
    // Apply only non-limit client filters (limit already consumed by CLI)
    const { limit: _limit, ...clientFilters } = filters ?? {};
    const events = applyEventFilters(liveEvents, clientFilters);
    return { events, total: events.length };
  }
  const events = (chronicleEventsFixture.events ?? []) as ChronicleEvent[];
  const filtered = applyEventFilters(events, filters);
  return { events: filtered, total: events.length };
}

export function chronicleDecisions(subjectId: string, filters?: ChronicleDecisionFilters): ChronicleDecisionsResult {
  if (getDataSource() === "live") {
    const liveDecisions = chronicleLiveDecisions(subjectId, filters);
    const { limit: _limit, ...clientFilters } = filters ?? {};
    const decisions = applyDecisionFilters(liveDecisions, clientFilters);
    return { decisions, total: decisions.length };
  }
  const decisions = (chronicleDecisionsFixture.decisions ?? []) as ChronicleDecision[];
  const filtered = applyDecisionFilters(decisions, filters);
  return { decisions: filtered, total: decisions.length };
}

export function chronicleSnapshots(subjectId: string, filters?: ChronicleSnapshotFilters): ChronicleSnapshotsResult {
  if (getDataSource() === "live") {
    const liveSnapshots = chronicleLiveSnapshots(subjectId, filters);
    const { limit: _limit, ...clientFilters } = filters ?? {};
    const snapshots = applySnapshotFilters(liveSnapshots, clientFilters);
    return { snapshots, total: snapshots.length };
  }
  const snapshots = (chronicleSnapshotsFixture.snapshots ?? []) as ChronicleSnapshot[];
  const filtered = applySnapshotFilters(snapshots, filters);
  return { snapshots: filtered, total: snapshots.length };
}

export function chronicleStats(subjectId: string): ChronicleStats | null {
  if (getDataSource() === "live") return chronicleLiveStats(subjectId);
  return chronicleStatsFixture as ChronicleStats;
}

export function chronicleProvenance(subjectId: string): ChronicleProvenanceResult {
  if (getDataSource() === "live") return chronicleLiveProvenance(subjectId);
  return { edges: (chronicleProvenanceFixture.edges ?? []) as ChronicleProvenanceEdge[] };
}
