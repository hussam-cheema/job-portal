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
  const adsense = page.locator(
    'head script[src*="pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"]'
  );
  await expect(adsense).toHaveCount(1);
  await expect(adsense).toHaveAttribute(
    "src",
    "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1209296651546868"
  );
  await expect(adsense).toHaveAttribute("crossorigin", "anonymous");
  await expect(adsense).toHaveAttribute("async", "");
  await expect(page.locator('meta[name="google-adsense-account"]')).toHaveAttribute(
    "content",
    "ca-pub-1209296651546868"
  );
  await expect(page.locator('meta[name="impact-site-verification"]')).toHaveAttribute(
    "value",
    "db9798fc-f9b2-4459-8ec6-570e00181eae"
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
  const homepageH1 = page.locator("main h1");
  await expect(homepageH1).toHaveCount(1);
  await expect(homepageH1).toHaveText("Pakistan Jobs Market");
  await expect(homepageH1).toHaveCSS("text-align", "center");
  await expect(page.locator("main h1 + h2")).toHaveCSS("text-align", "center");
  await expect(page.locator("main h1 + h2 + p")).toHaveCSS("text-align", "center");
  await expect(
    page.getByRole("heading", {
      name: "Latest government & private job openings in Pakistan",
      exact: true,
      level: 2,
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

test("AdSense ads.txt is published at the site root", async ({ request }) => {
  const response = await request.get("/ads.txt");
  expect(response.ok()).toBeTruthy();
  expect(response.headers()["content-type"]).toMatch(/^text\/plain/);
  expect((await response.text()).trim()).toBe(
    "google.com, pub-1209296651546868, DIRECT, f08c47fec0942fa0"
  );
});

test("privacy policy contains required AdSense disclosures without loading the ad tag", async ({ page }) => {
  await page.goto("/privacy");

  await expect(
    page.locator(".prose-job p").filter({ hasText: "Effective date:" })
  ).toContainText("5 September 2026");
  await expect(page.getByRole("heading", { name: "Student API access" })).toBeVisible();
  await expect(page.getByText("Readable codes and full keys are not stored", { exact: false })).toBeVisible();
  await expect(page.getByText("Third-party vendors, including Google, use cookies")).toBeVisible();
  await expect(page.getByRole("link", { name: "Google Ads Settings" })).toHaveAttribute(
    "href",
    "https://adssettings.google.com/"
  );
  await expect(page.getByRole("link", { name: "YourAdChoices opt-out page" })).toHaveAttribute(
    "href",
    "https://www.aboutads.info/choices/"
  );
  await expect(page.getByRole("link", { name: "Google Privacy Policy" })).toHaveAttribute(
    "href",
    "https://policies.google.com/privacy"
  );
  await expect(
    page.locator('script[src*="pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"]')
  ).toHaveCount(0);
  await expect(page.locator('meta[name="google-adsense-account"]')).toHaveAttribute(
    "content",
    "ca-pub-1209296651546868"
  );
});
