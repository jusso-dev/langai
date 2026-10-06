import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 360_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    actionTimeout: 20_000,
    baseURL: process.env.LANGAI_E2E_URL || "http://127.0.0.1:3100",
    // No traces/videos: credentials and private dictionary content must not become CI artifacts.
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
