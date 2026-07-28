import { expect, test } from "@playwright/test";

test("public pages expose self-canonicals and private pages are noindex", async ({ page }) => {
  for (const path of [
    "/",
    "/about",
    "/contact",
    "/privacy",
    "/disclaimer",
    "/blog",
    "/cover-letter",
    "/resume-builder",
    "/jobs/closed-role",
    "/tags/government",
    "/categories/software-engineering",
  ]) {
    await page.goto(path);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
    expect(canonical).toBeTruthy();
    expect(new URL(canonical!).pathname).toBe(path);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
      "content",
      /^index,\s*follow/i
    );
  }

  await page.goto("/admin");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
    "content",
    /noindex.*nofollow/i
  );
});

test("published CMS pages have a real public route and canonical metadata", async ({ page }) => {
  await page.goto("/p/custom-seo-page");

  await expect(page.getByRole("heading", { name: "Custom public page" })).toBeVisible();
  await expect(page).toHaveTitle(/Custom SEO title/);
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    "content",
    "Custom SEO description for the published CMS page."
  );
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    /\/p\/custom-seo-page$/
  );
});

test("sitemap advertises canonical content URLs and the legacy favicon resolves", async ({
  request,
}) => {
  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.ok()).toBeTruthy();
  const xml = await sitemap.text();

  expect(xml).toContain("<loc>http://localhost:3000/disclaimer</loc>");
  expect(xml).toContain("<loc>http://localhost:3000/cover-letter</loc>");
  const locations = Array.from(xml.matchAll(/<loc>([^<]+)<\/loc>/g), (match) => match[1]);
  expect(locations.length).toBeGreaterThan(0);
  expect(locations.every((location) => new URL(location).hostname === "localhost")).toBeTruthy();

  const favicon = await request.get("/favicon.ico");
  expect(favicon.ok()).toBeTruthy();
  expect(favicon.headers()["content-type"]).toMatch(/^image\//);
  expect((await favicon.body()).byteLength).toBeGreaterThan(0);
});
