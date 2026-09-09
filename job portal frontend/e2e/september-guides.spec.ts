import { test, expect } from "@playwright/test";

for (const slug of ["pps-salary-scale-2026-pakistan", "bps-salary-chart-2026-pakistan", "new-pension-scheme-pakistan-2026", "fpsc-age-relaxation-2026", "14-vs-16-vs-18-years-education-pakistan"]) {
  test(`September guide content, SEO and responsive design: ${slug}`, async ({ page }) => {
    const response = await page.goto(`/blog/${slug}`);
    expect(response?.status()).toBe(200);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", new RegExp(`/blog/${slug}$`));
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", /\/blog\/.+\.png$/);
    const schema = JSON.parse(await page.locator('script[type="application/ld+json"]').first().textContent() || "{}");
    expect(schema["@type"]).toBe("BlogPosting");
    expect(schema.author["@type"]).toBe("Organization");
    const figure = page.locator(".blog-analysis-figure img");
    await expect(figure).toBeVisible();
    expect(await figure.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBe(1200);
    for (const width of [360, 820, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      await page.screenshot({ path: `test-results/${slug}-${width}.png`, fullPage: true });
    }
  });
}
