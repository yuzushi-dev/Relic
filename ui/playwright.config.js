const port = process.env.RELIC_UI_TEST_PORT || "4144";
const baseURL = `http://localhost:${port}`;

/** @type {import('@playwright/test').DefineConfig} */
module.exports = {
  testDir: "./tests",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `npx next dev -p ${port}`,
    url: baseURL,
    reuseExistingServer: process.env.RELIC_UI_TEST_REUSE_SERVER === "true",
    timeout: 30000,
  },
};
