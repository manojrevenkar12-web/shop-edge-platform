import { defineConfig } from "@playwright/test";

const PORT = 8094;

export default defineConfig({
  testDir: "e2e",
  timeout: 45_000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    viewport: { width: 1360, height: 900 },
    // CI installs Playwright's Chromium; elsewhere a local Chrome can be named.
    launchOptions: process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME } : {},
  },
  webServer: {
    // the committed reports and the built dashboard, served by the API
    command: `cd .. && python -m uvicorn sep.service.api:app --port ${PORT}`,
    url: `http://localhost:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 90_000,
  },
  reporter: [["list"]],
});
