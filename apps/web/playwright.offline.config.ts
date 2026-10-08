import { defineConfig, devices } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  testMatch: /offline(?:-export)?\.spec\.ts/,
  timeout: 60_000,
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit-phone", use: { ...devices["iPhone 13"] } },
  ],
});
