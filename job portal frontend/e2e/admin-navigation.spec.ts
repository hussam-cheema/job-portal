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
    const documentMarker = `admin-document-${linkName}`;
    await page.evaluate((marker) => {
      (window as typeof window & { __adminDocumentMarker?: string }).__adminDocumentMarker = marker;
    }, documentMarker);
    await page.locator(".admin-content").getByRole("link", { name: linkName, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${expectedPath.replaceAll("/", "\\/")}$`));
    await expect
      .poll(() =>
        page.evaluate(
          () => (window as typeof window & { __adminDocumentMarker?: string }).__adminDocumentMarker,
        ),
      )
      .toBe(documentMarker);
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

test("a stale Next.js chunk triggers one automatic recovery", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  const recoveryNavigation = page.waitForEvent("framenavigated", (frame) => frame === page.mainFrame());
  await page.evaluate(() => {
    sessionStorage.removeItem("pakjobs-chunk-recovery:/admin");
    setTimeout(() => Promise.reject(new Error("ChunkLoadError: Loading chunk 123 failed")), 0);
  });
  await recoveryNavigation;

  const recoveryTimestamp = await page.evaluate(() =>
    Number(sessionStorage.getItem("pakjobs-chunk-recovery:/admin") || "0"),
  );
  expect(recoveryTimestamp).toBeGreaterThan(0);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText(/Application error: a client-side exception/i)).toHaveCount(0);
});

test("core CMS pages are visible in the dashboard", async ({ page }) => {
  await page.goto("/admin/pages");
  for (const title of ["About Us", "Contact Us", "Privacy Policy", "Disclaimer"]) {
    await expect(page.getByText(title, { exact: true })).toBeVisible();
  }
  await expect(page.getByText("No pages yet. Create your first page.")).toHaveCount(0);
});
