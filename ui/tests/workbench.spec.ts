import { test, expect } from "@playwright/test";
test.skip("workbench renders", async ({ page }) => {
  await page.goto("/workbench");
  await expect(page.getByRole("main")).toBeVisible();
});
