import { expect, test } from "@playwright/test";

test("national dashboard, chart interactions, archived edition and SEO", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Pakistan job market, in perspective.");
  const nav = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(nav.getByRole("link").first()).toHaveAttribute("href", "/dashboard");
  await expect(nav.getByRole("link", { name: "Admin Panel", exact: true })).toHaveCount(0);
  await expect(page.getByText("A monthly edition, not a monthly survey.")).toBeVisible();
  await expect(page.locator("#national-overview")).toContainText("5.4%");
  const listings = page.getByRole("region", { name: "Website-only supplementary statistics" });
  await expect(listings).toContainText("127 listings");
  await expect(listings).toContainText("18 listings");
  await listings.getByLabel("By publication month").selectOption("2026-08");
  await expect(listings).toContainText("84 listings");
  await expect(listings).toContainText("127 listings");
  await expect(listings).toContainText("56 government");
  await page.getByLabel("Trend indicator").selectOption("youth_unemployment");
  await expect(page.locator("#market-trends")).toContainText("11.30%");
  await page.getByText("View chart data", { exact: true }).click();
  await expect(page.locator("#market-trends table")).toContainText("2025");
  await page.getByText("View all 14 official indicators and downloadable source data").click();
  await expect(page.locator("#report-sources").getByRole("link", { name: "Source JSON", exact: true })).toHaveCount(14);
  await page.getByRole("navigation", { name: "Monthly report archive" }).getByRole("link", { name: /August 2026/ }).click();
  await expect(page).toHaveURL(/\/dashboard\/2026-08$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("August 2026");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/dashboard\/2026-08$/);
  const schema = JSON.parse(await page.locator('script[type="application/ld+json"]').first().textContent() || "{}");
  expect(schema["@type"]).toBe("Report");
  expect(schema.citation).toHaveLength(14);
  const sitemap = await (await page.request.get("/sitemap.xml")).text();
  expect(sitemap).toContain("/dashboard/2026-09");
});

test("admin shortcut is renamed without replacing the public Dashboard", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("pakjobs-admin-token", "e2e-token");
    localStorage.setItem("pakjobs-admin-user", "e2e-admin");
  });
  await page.goto("/dashboard");
  const nav = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(nav.getByRole("link", { name: "Admin Panel", exact: true })).toHaveAttribute("href", "/admin");
  await expect(nav.getByRole("link").first()).toHaveAttribute("href", "/dashboard");
});

for (const width of [320, 390, 768, 1024, 1100, 1440]) {
  test(`national report fits ${width}px with no header overlap`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/dashboard/2026-09");
    await expect(page.getByRole("heading", { name: "Employment by sector", exact: true })).toBeVisible();
    const audit = await page.evaluate(() => {
      const title = document.querySelector(".site-title")!.getBoundingClientRect();
      const nav = document.querySelector(".site-actions")!.getBoundingClientRect();
      const supplement = document.querySelector('[aria-label="Website-only supplementary statistics"]')!.getBoundingClientRect();
      const main = document.querySelector("main")!.getBoundingClientRect();
      return { overflow: document.documentElement.scrollWidth > innerWidth + 1, overlap: title.left < nav.right && title.right > nav.left && title.top < nav.bottom && title.bottom > nav.top, fraction: supplement.height / main.height };
    });
    expect(audit.overflow).toBe(false);
    expect(audit.overlap).toBe(false);
    expect(audit.fraction).toBeLessThan(.1);
    if (width === 390 || width === 1440) await page.screenshot({ path: `test-results/market-${width}.png`, fullPage: true });
  });
}

test("unpublished monthly editions return 404", async ({ page }) => {
  const response = await page.goto("/dashboard/2001-01");
  expect(response?.status()).toBe(404);
});

test("dark theme keeps charts and the expanded admin navigation usable", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("pakjobs-theme", "dark");
    localStorage.setItem("pakjobs-admin-token", "e2e-token");
  });
  await page.goto("/dashboard");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  for (const width of [320, 1100, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Admin Panel", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(await page.locator(".site-title").evaluate(el => el.scrollWidth <= el.clientWidth + 1 && el.scrollHeight <= el.clientHeight + 1)).toBe(true);
  }
  await page.screenshot({ path: "test-results/market-dark.png" });
});
