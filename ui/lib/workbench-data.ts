import fs from "node:fs";
import path from "node:path";

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
  return process.env.RELIC_UI_DATA_SOURCE === "live" ? "live" : "demo";
}

function relicHome() {
  return process.env.RELIC_HOME || path.join(process.cwd(), ".relic-live");
}

function readJson<T>(filePath: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8")) as T;
  } catch {
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
  } catch {
    return [];
  }
}

function liveProfiles() {
  const subjectsDir = path.join(relicHome(), "subjects");
  try {
    return fs
      .readdirSync(subjectsDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => readJson<LiveSubjectProfile>(path.join(subjectsDir, entry.name, "subject_profile.json")))
      .filter((profile): profile is LiveSubjectProfile => Boolean(profile?.subject_id));
  } catch {
    return [];
  }
}

function readCronData(profile: LiveSubjectProfile): LiveCronData {
  const subjectHome = profile.relic_subject_home ?? "";
  const hermesHome = profile.hermes_home ?? "";

  // Active cron families from install manifest written during bootstrap
  const cronManifest = subjectHome
    ? readJson<{ families?: string[] }>(path.join(subjectHome, "gumi_cron_manifest.json"))
    : null;
  const active_families = cronManifest?.families ?? [];

  // Pending proactive: entries in checkin_decision_log.jsonl where decision is not [SILENT]
  let pending_proactive_count = 0;
  let last_initiative_at: string | null = null;
  if (hermesHome) {
    const logPath = path.join(hermesHome, "workspace", "gumi", "cron", "checkin_decision_log.jsonl");
    type CheckinEntry = { status?: string; decision?: string; timestamp?: string; created_at?: string };
    const entries = readJsonLines<CheckinEntry>(logPath);
    for (const entry of entries) {
      const isPending =
        entry.status === "pending_review" ||
        entry.status === "warranted" ||
        (entry.decision && entry.decision !== "[SILENT]" && entry.decision !== "silent");
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

export function getEventStream(_subjectId: string): EventStream | null {
  return getDataSource() === "live" ? null : eventStreamFixture;
}

export function getSubjectIntelligence(_subjectId: string): SubjectIntelligenceData | null {
  return getDataSource() === "live" ? null : subjectIntelligenceFixture;
}
