/**
 * Layer 4 Artifact Gate
 *
 * Relic's four-layer architecture (whitepaper §5.3) injects only
 * `PORTRAIT.md` into agent bootstrap. Every other artifact - Layer 3
 * specialist outputs (schemas, defenses, CAPS, appraisal, attachment,
 * idiolect, LIWC, stress), Layer 2 traits/observations dumps, or the
 * inspection-only `PROFILE.md` - stays off the bootstrap surface.
 *
 * Extending the whitelist is a governance decision and must be a
 * deliberate edit here, not an ad-hoc path in a hook. The companion
 * test `tests/test_artifact_gate.py` enforces the invariant.
 *
 * Related: `docs/adr/001-layer4-artifact-gate.md`.
 */

export const INJECTABLE_ARTIFACTS: readonly string[] = ["PORTRAIT.md"];

/**
 * Returns true iff `filename` is permitted at bootstrap. Matching is on
 * the basename only - callers must not pass absolute paths with
 * directory components that could be spoofed.
 */
export function isInjectableArtifact(filename: string): boolean {
  if (!filename || typeof filename !== "string") return false;
  const base = filename.split("/").pop() ?? "";
  return INJECTABLE_ARTIFACTS.includes(base);
}
