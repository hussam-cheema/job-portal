import { expect, test } from "@playwright/test";

test("job rich text headings, location tags, and overflow render correctly", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("pakjobs-theme", "dark"));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/jobs/multi-location-role");

  const description = page.locator(".prose-job");
  const heading = description.getByRole("heading", { name: "Role overview" });
  const paragraph = description.locator("p").first();
  await expect(heading).toBeVisible();
  await expect(page.getByRole("link", { name: "Karachi", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Lahore", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sindh", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "LinkedIn", exact: true })).toHaveAttribute(
    "href",
    "https://linkedin.com/company/pakistanjobsmarket",
  );

  const headingFontSize = await heading.evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).fontSize),
  );
  const paragraphFontSize = await paragraph.evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).fontSize),
  );
  expect(headingFontSize).toBeGreaterThan(paragraphFontSize);
  await expect(heading.locator("span")).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");

  const viewportWidth = await page.evaluate(() => document.documentElement.clientWidth);
  const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(documentWidth).toBeLessThanOrEqual(viewportWidth);
  const bounds = await description.boundingBox();
  expect(bounds).not.toBeNull();
  expect((bounds?.x || 0) + (bounds?.width || 0)).toBeLessThanOrEqual(viewportWidth);
});

test("job listings show every selected city and province", async ({ page }) => {
  await page.goto("/");
  const card = page.getByRole("article").filter({ hasText: "Multi Location Role" });
  await expect(card.getByRole("link", { name: "Karachi", exact: true })).toBeVisible();
  await expect(card.getByRole("link", { name: "Lahore", exact: true })).toBeVisible();
  await expect(card.getByRole("link", { name: "Sindh", exact: true })).toBeVisible();
});
