import { expect, test } from "@playwright/test";

test("public branding, homepage text, footer, and disclaimer navigation render", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  await expect(page).toHaveTitle("Jobs in Pakistan 2026 | Pakistan Jobs Market");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    "content",
    "Find latest government and private jobs in Pakistan by city and category. Explore curated listings, deadlines, job alerts, resume tools and career guides.",
  );
  await expect(page.locator('meta[name="keywords"]')).toHaveAttribute(
    "content",
    /jobs in Pakistan.*government jobs Pakistan.*private jobs Pakistan/,
  );
  await expect(page.locator("header").getByText("Pakistan Jobs Market", { exact: true })).toBeVisible();
  const headerLogo = page.locator("header img");
  const tabIcon = page.locator('link[rel="icon"]').first();
  await expect(headerLogo).toHaveAttribute("src", /pakistan-jobs-market-logo\.png/);
  await expect(tabIcon).toHaveAttribute("href", /pakistan-jobs-market-logo\.png/);
  const [headerLogoPath, tabIconPath] = await Promise.all([
    headerLogo.evaluate((element: HTMLImageElement) => new URL(element.src).pathname),
    tabIcon.evaluate((element: HTMLLinkElement) => new URL(element.href).pathname),
  ]);
  expect(tabIconPath).toBe(headerLogoPath);
  await expect(page.locator("main h1")).toHaveCSS("text-align", "center");
  await expect(page.locator("main h1 + p")).toHaveCSS("text-align", "center");
  await expect(
    page.getByRole("heading", {
      name: "Latest government & private job openings in Pakistan",
      exact: true,
    })
  ).toBeVisible();
  await expect(page.getByText("Pakistan jobs", { exact: true })).toHaveCount(0);
  await expect(page.locator("footer")).toContainText(
    `Copyrights © ${new Date().getFullYear()} - Pakistan Jobs Market. All rights reserved.`
  );
  await expect(page.locator("footer").getByRole("link", { name: "Disclaimer" })).toHaveAttribute(
    "href",
    "/disclaimer"
  );
  expect(pageErrors).toEqual([]);
});

test("job description R2 images render through the public API media route", async ({ page }) => {
  await page.goto("/jobs/closed-role");
  const image = page.getByRole("img", { name: "R2 job image" });

  await expect(image).toHaveAttribute(
    "src",
    "http://127.0.0.1:4010/api/media/r2/job-portal/closed-role/images/notice.png",
  );
  await expect
    .poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth))
    .toBeGreaterThan(0);
});
