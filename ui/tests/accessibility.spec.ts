import { test, expect } from "@playwright/test";
test.skip("focus rings are visible", async ({ page }) => {
  await page.goto("/workbench");
  await page.keyboard.press("Tab");
  const ring = await page.evaluate(() => getComputedStyle(document.activeElement!).outlineStyle);
  expect(["solid", "auto"]).toContain(ring);
});
