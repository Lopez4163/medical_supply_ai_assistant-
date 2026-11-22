import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  globalSetup: "./e2e-real/global-setup.ts",
  testDir: "./e2e-real",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  reporter: "list",
  timeout: 45_000,
  use: {
    baseURL: "http://localhost:3101",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium-real-api", use: { ...devices["Desktop Chrome"] } }],
});
