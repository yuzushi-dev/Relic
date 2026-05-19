/** @type {import('@playwright/test').DefineConfig} */
module.exports = {
  testDir: "./tests",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:4144",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npx next dev -p 4144",
    url: "http://localhost:4144",
    reuseExistingServer: true,
    timeout: 30000,
  },
};
