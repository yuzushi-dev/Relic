import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

import studyOverviewFixture from "../fixtures/researcher-workbench/study_overview.json";
import subjectOverviewFixture from "../fixtures/researcher-workbench/subject_overview_subj_001.json";
import subjectBaselineFixture from "../fixtures/researcher-workbench/subject_baseline_subj_001.json";
import eventStreamFixture from "../fixtures/researcher-workbench/event_stream_subj_001.json";
import subjectIntelligenceFixture from "../fixtures/researcher-workbench/subject_intelligence_subj_001.json";
import gumiProfileFixture from "../fixtures/researcher-workbench/gumi_profile_subj_001.json";

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

  return {
    subject_id: subjectId,
    agent_name: agentName,
    soul_md: hermesHome ? readText(path.join(hermesHome, "SOUL.md")) : null,
    world_md: hermesHome ? readText(path.join(hermesHome, "workspace", "gumi", "world.md")) : null,
    relationship_policy_md: hermesHome
      ? readText(path.join(hermesHome, "workspace", "gumi", "relationship_policy.md"))
      : null,
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

  // Merge Chronicle events (deduplicate by event_id)
  const chronicleEvents = chronicleQuery(subjectId);
  const seen = new Set(events.map((e) => e.event_id));
  for (const ce of chronicleEvents) {
    if (!seen.has(ce.event_id)) {
      events.push(ce);
      seen.add(ce.event_id);
    }
  }

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

  type ScoreEntry = {
    value?: number;
    confidence?: string;
    confidence_float?: number;
    observations?: number;
    spectrum_low?: string;
    spectrum_high?: string;
  };

  const subjectBaseline = readJson<{
    created_at?: string;
    last_checkin_update?: string;
    psychological?: Record<string, ScoreEntry>;
    interaction?: Record<string, ScoreEntry>;
    extended_facets?: Record<string, ScoreEntry>;
  }>(path.join(subjectHome, "subject_baseline.json"));

  const baselineProfile = readJson<{
    researcher_coded_fields?: Record<string, { value?: unknown; origin?: string }>;
    self_report_fields?: Record<string, { value?: unknown; origin?: string }>;
  }>(path.join(subjectHome, "baseline_user_profile.json"));

  function scoreToFacet(k: string, v: ScoreEntry, leftAnchor: string, rightAnchor: string): SubjectIntelligenceData["facet_groups"][number]["facets"][number] {
    const conf = v.confidence_float !== undefined
      ? v.confidence_float
      : (() => {
          const s = v.confidence ?? "low_initial";
          return s.startsWith("high") ? 0.8 : s.startsWith("medium") ? 0.5 : 0.25;
        })();
    return {
      facet: k.replace(/_/g, " "),
      position: v.value ?? 0.5,
      confidence: conf,
      confidence_label: conf >= 0.7 ? "high" : conf >= 0.4 ? "medium" : "low",
      observations: v.observations ?? 0,
      left_anchor: v.spectrum_low ?? leftAnchor,
      right_anchor: v.spectrum_high ?? rightAnchor,
    };
  }

  const psychFacets = Object.entries(subjectBaseline?.psychological ?? {})
    .filter(([, v]) => typeof v.value === "number")
    .map(([k, v]) => scoreToFacet(k, v, "low", "high"));

  const interactionFacets = Object.entries(subjectBaseline?.interaction ?? {})
    .filter(([, v]) => typeof v.value === "number")
    .map(([k, v]) => scoreToFacet(k, v, "low", "high"));

  // Group extended_facets by category prefix (e.g. "relational.x" → "relational")
  const extendedByCategory: Record<string, SubjectIntelligenceData["facet_groups"][number]["facets"]> = {};
  for (const [k, v] of Object.entries(subjectBaseline?.extended_facets ?? {})) {
    if (typeof v.value !== "number") continue;
    const cat = k.includes(".") ? k.split(".")[0] : "other";
    const label = cat.replace(/_/g, " ");
    if (!extendedByCategory[label]) extendedByCategory[label] = [];
    extendedByCategory[label].push(scoreToFacet(k, v, "low", "high"));
  }

  const facet_groups: SubjectIntelligenceData["facet_groups"] = [];
  if (psychFacets.length > 0) facet_groups.push({ group: "Psychological", facets: psychFacets });
  if (interactionFacets.length > 0) facet_groups.push({ group: "Interaction Preferences", facets: interactionFacets });
  for (const [cat, facets] of Object.entries(extendedByCategory)) {
    facet_groups.push({ group: cat.charAt(0).toUpperCase() + cat.slice(1), facets });
  }

  const allFacets = [...psychFacets, ...interactionFacets, ...Object.values(extendedByCategory).flat()];
  const topConfidence = [...allFacets].sort((a, b) => b.confidence - a.confidence).slice(0, 5).map(f => ({
    facet: f.facet, position: f.position, confidence: f.confidence,
    confidence_label: f.confidence_label, observations: f.observations,
    left_anchor: f.left_anchor, right_anchor: f.right_anchor,
  }));

  const rcf = baselineProfile?.researcher_coded_fields ?? {};
  const srf = baselineProfile?.self_report_fields ?? {};
  const topTraits: string[] = [
    rcf.communication_style?.value ? `communication: ${rcf.communication_style.value}` : "",
    rcf.attachment_style?.value ? `attachment: ${rcf.attachment_style.value}` : "",
    srf.gender_identity?.value ? String(srf.gender_identity.value) : "",
    srf.occupation_or_study?.value ? String(srf.occupation_or_study.value) : "",
    srf.contact_channel_preference?.value ? `channel: ${srf.contact_channel_preference.value}` : "",
    srf.language?.value ? `lang: ${srf.language.value}` : "",
  ].filter(Boolean).slice(0, 6) as string[];

  const summaryParts: string[] = [];
  if (rcf.communication_style?.value) summaryParts.push(`Communication: ${rcf.communication_style.value}`);
  if (rcf.attachment_style?.value) summaryParts.push(`Attachment: ${rcf.attachment_style.value}`);
  if (rcf.affect_regulation_notes?.value) summaryParts.push(String(rcf.affect_regulation_notes.value).slice(0, 120));
  const summary = summaryParts.join(". ") || "Live behavioral data collected from subject_baseline.json.";

  const artifacts: SubjectIntelligenceData["artifacts"] = [
    { name: "subject_baseline.json", kind: "baseline", lineage: `${subjectId}/subject_baseline` },
    { name: "baseline_user_profile.json", kind: "baseline", lineage: `${subjectId}/baseline_user_profile` },
  ];
  if (subjectBaseline?.extended_facets && Object.keys(subjectBaseline.extended_facets).length > 0) {
    artifacts.push({ name: "extended_facets (checkin-derived)", kind: "model_snapshot", lineage: `${subjectId}/subject_baseline#extended_facets` });
  }
  const dbPath = path.join(subjectHome, "relic.db");
  if (path.isAbsolute(dbPath) && fs.existsSync(dbPath)) {
    artifacts.push({ name: "relic.db", kind: "model_snapshot", lineage: `${subjectId}/relic.db` });
  }

  return {
    subject_id: subjectId,
    generated_at: subjectBaseline?.created_at ?? new Date().toISOString(),
    model_summary: {
      facets_modeled: allFacets.filter(f => f.observations > 0).length,
      facets_total: subjectIntelligenceFixture.model_summary.facets_total,
      seed_observations: Object.keys(rcf).length + Object.keys(srf).length,
      extraction_signals: allFacets.length,
      hypotheses: 0,
      summary,
    },
    top_traits: topTraits,
    active_goals: [],
    top_confidence_facets: topConfidence,
    hypotheses: [],
    facet_groups,
    transcript: [],
    extraction_sample: allFacets.slice(0, 5).map((f: SubjectIntelligenceData["facet_groups"][number]["facets"][number]) => ({
      facet: f.facet,
      direction: f.position > 0.6 ? "positive" : f.position < 0.4 ? "negative" : "neutral",
      strength: f.confidence,
      source: "subject_baseline",
    })),
    artifacts,
  };
}
