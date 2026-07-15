import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : [
        {
          command: "node e2e/mock-api.mjs",
          url: "http://127.0.0.1:4010/ready",
          reuseExistingServer: !process.env.CI,
        },
        {
          command:
            "INTERNAL_API_URL=http://127.0.0.1:4010 NEXT_PUBLIC_API_URL=http://127.0.0.1:4010 npm run start -- -p 3100",
          url: baseURL,
          reuseExistingServer: !process.env.CI,
        },
      ],
});
