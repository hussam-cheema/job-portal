import { expect, test, type Page } from "@playwright/test";

const dashboardLinks = [
  ["Create job post", "/admin/jobs/new", "Create job post"],
  ["Create page", "/admin/pages/new", "Create page"],
  ["Manage jobs", "/admin/jobs", "Job posts"],
  ["Manage pages", "/admin/pages", "Pages"],
  ["Contact messages", "/admin/messages", "Contact messages"],
  ["SEO monitor", "/admin/seo", "SEO command center"],
] as const;

async function authenticate(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("pakjobs-admin-token", "e2e-token");
    localStorage.setItem("pakjobs-admin-user", "e2e-admin");
  });
}

test.beforeEach(async ({ page }) => {
  await authenticate(page);
});

test("every dashboard link loads without a client exception", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  for (const [linkName, expectedPath, expectedText] of dashboardLinks) {
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await page.locator(".admin-content").getByRole("link", { name: linkName, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${expectedPath.replaceAll("/", "\\/")}$`));
    await expect(page.getByText(expectedText, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/Application error: a client-side exception/i)).toHaveCount(0);
  }

  expect(pageErrors).toEqual([]);
});

test("all remaining admin navigation pages render", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  for (const [path, heading] of [
    ["/admin/analytics", "Site analytics"],
    ["/admin/settings", "Settings"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await expect(page.getByText(/Application error: a client-side exception/i)).toHaveCount(0);
  }

  expect(pageErrors).toEqual([]);
});
