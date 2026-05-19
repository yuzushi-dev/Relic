// Gated live-mode test — skipped unless RELIC_LIVE=1 is set.
// Run with: RELIC_LIVE=1 RELIC_SUBJECT=subj_001 npx playwright test ...
describe.skipIf(process.env.RELIC_LIVE !== "1")("chronicle data layer (live)", () => {
  it("chronicleEvents returns array from real CLI", async () => {
    const { chronicleEvents } = await import("../workbench-data");
    const subjectId = process.env.RELIC_SUBJECT ?? "subj_001";
    const result = chronicleEvents(subjectId, { limit: 1 });
    expect(Array.isArray(result.events)).toBe(true);
  });

  it("chronicleDecisions returns array from real CLI", async () => {
    const { chronicleDecisions } = await import("../workbench-data");
    const subjectId = process.env.RELIC_SUBJECT ?? "subj_001";
    const result = chronicleDecisions(subjectId, { limit: 1 });
    expect(Array.isArray(result.decisions)).toBe(true);
  });

  it("chronicleSnapshots returns array from real CLI", async () => {
    const { chronicleSnapshots } = await import("../workbench-data");
    const subjectId = process.env.RELIC_SUBJECT ?? "subj_001";
    const result = chronicleSnapshots(subjectId, { limit: 1 });
    expect(Array.isArray(result.snapshots)).toBe(true);
  });

  it("chronicleStats returns stats from real CLI", async () => {
    const { chronicleStats } = await import("../workbench-data");
    const subjectId = process.env.RELIC_SUBJECT ?? "subj_001";
    const stats = chronicleStats(subjectId);
    if (stats) {
      expect(typeof stats.total_events).toBe("number");
    }
  });
});
