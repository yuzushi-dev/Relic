import { test, expect } from "@playwright/test";

const SUBJECT = "subj_001";

test("chronicle overview renders stats panel", async ({ page }) => {
  await page.goto(`/dashboard/subjects/${SUBJECT}/chronicle`);
  await expect(page.getByTestId("stats-panel")).toBeVisible({ timeout: 15000 });
});

test("events page filters by severity via URL", async ({ page }) => {
  await page.goto(`/dashboard/subjects/${SUBJECT}/chronicle/events?severity=warning`);
  const rows = page.getByTestId("events-table").locator("tbody tr");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("User correction");
});

test("events filter control updates URL", async ({ page }) => {
  await page.goto(`/dashboard/subjects/${SUBJECT}/chronicle/events`);
  await page.getByLabel("severity").selectOption("error");
  await expect(page).toHaveURL(/severity=error/);
  await expect(page.getByTestId("events-table").locator("tbody tr")).toHaveCount(1);
});

test("decisions page filters by status", async ({ page }) => {
  await page.goto(
    `/dashboard/subjects/${SUBJECT}/chronicle/decisions?validation_status=validated`,
  );
  await expect(page.getByTestId("decisions-list").locator(":scope > .ris-panel")).toHaveCount(5);
});

test("snapshots page shows diff entries", async ({ page }) => {
  await page.goto(`/dashboard/subjects/${SUBJECT}/chronicle/snapshots`);
  await expect(page.getByTestId("snapshots-list")).toBeVisible({ timeout: 10000 });
});

test("Chronicle nav shows Overview link", async ({ page }) => {
  await page.goto(`/dashboard/subjects/${SUBJECT}/chronicle`);
  const overviewLink = page.getByRole("link", { name: "Overview", exact: true });
  await expect(overviewLink).toBeVisible();
});
