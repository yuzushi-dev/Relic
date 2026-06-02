import { expect, test } from "@playwright/test";

test("desktop workbench uses RIS status chrome and compact rail", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/dashboard");

  await expect(page.getByTestId("ris-status-bar")).toBeVisible();
  await expect(page.getByTestId("ris-status-bar")).toContainText("LIVE");
  await expect(page.getByAltText("Relic")).toBeVisible();

  const rail = page.getByTestId("ris-nav-rail");
  await expect(rail).toBeVisible();
  await expect.poll(async () => (await rail.boundingBox())?.width).toBe(64);

  await expect
    .poll(() =>
      page.evaluate(() =>
        getComputedStyle(document.documentElement).getPropertyValue("--ris-bg").trim(),
      ),
    )
    .toBe("#0a0c0e");
});

test("subject scoped screens expose the RIS subject context", async ({ page }) => {
  await page.goto("/dashboard/subjects/subj_001/baseline");

  const subjectNav = page.getByRole("navigation", { name: "Subject navigation" });
  await expect(subjectNav).toBeVisible();
  await expect(subjectNav).toContainText("SUBJECT");
  await expect(subjectNav).toContainText("SCOPED");
});

test("mobile workbench exposes the RIS bottom navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/dashboard");

  const nav = page.getByTestId("ris-mobile-nav");
  await expect(nav).toBeVisible();
  await expect(nav).toContainText("Study");
  await expect(nav).toContainText("Subject");
  await expect(nav).toContainText("Chronicle");
  await expect(nav).toContainText("Gumi");
});
