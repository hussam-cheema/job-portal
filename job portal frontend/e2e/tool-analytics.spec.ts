import { expect, test } from "@playwright/test";

test("admin sees monthly metrics for every tool, including zero-use tools", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("pakjobs-admin-token", "e2e-token");
    localStorage.setItem("pakjobs-admin-user", "e2e-admin");
  });
  await page.goto("/admin/tools-analytics");
  await expect(page.getByRole("heading", { name: "Tools Analytics", exact: true })).toBeVisible();
  await expect(page.getByTestId("tool-analytics-row")).toHaveCount(8);
  await expect(page.getByText("Pakistan Tax Calculator", { exact: true })).toBeVisible();
  await expect(page.getByText("DOCX and PDF Converter", { exact: true })).toBeVisible();
  await expect(page.getByText("Add Watermark to Image", { exact: true })).toBeVisible();
  await expect(page.getByText(/New tools appear here automatically/)).toBeVisible();
  const month = page.getByLabel("Month · Pakistan time");
  await month.fill("2026-08");
  await expect(page.getByText("August 2026 · Asia/Karachi")).toBeVisible();
  await expect(page.locator(".admin-nav").getByRole("link", { name: "Tools Analytics" })).toHaveClass(/active/);
});

test("tool opens and first meaningful interaction send separate analytics events", async ({ page }) => {
  const events: Array<{ event_type: string; visitor_id: string }> = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/tools/pakistan-tax-calculator/usage")) {
      events.push(request.postDataJSON());
    }
  });
  await page.goto("/tools/pakistan-tax-calculator");
  await expect.poll(() => events.some((event) => event.event_type === "open")).toBe(true);
  const salaryInput = page.getByRole("spinbutton", { name: /monthly salary/i }).first();
  await salaryInput.fill("100000");
  await expect.poll(() => events.some((event) => event.event_type === "interaction")).toBe(true);
  await salaryInput.fill("120000");
  expect(events.filter((event) => event.event_type === "interaction")).toHaveLength(1);
  expect(events[0].visitor_id).toBeTruthy();
});

test("tool analytics remains readable on phone and tablet widths", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("pakjobs-admin-token", "e2e-token");
    localStorage.setItem("pakjobs-admin-user", "e2e-admin");
  });
  for (const width of [320, 820]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/admin/tools-analytics");
    await expect(page.getByRole("heading", { name: "Tools Analytics", exact: true })).toBeVisible();
    await expect(page.getByTestId("tool-analytics-row")).toHaveCount(8);
    const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(documentWidth).toBeLessThanOrEqual(width);
  }
});
