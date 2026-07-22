import { expect, test, type Page } from "@playwright/test";

const dashboardLinks = [
  ["Create job post", "/admin/jobs/new", "Create job post"],
  ["Create page", "/admin/pages/new", "Create page"],
  ["Create blog post", "/admin/blog/new", "Create blog post"],
  ["Manage jobs", "/admin/jobs", "Job posts"],
  ["Manage pages", "/admin/pages", "Pages"],
  ["Manage blog posts", "/admin/blog", "Blog posts"],
  ["Contact messages", "/admin/messages", "Contact messages"],
  ["Infrastructure analytics", "/admin/infrastructure", "Infrastructure analytics"],
  ["SEO monitor", "/admin/seo", "SEO command center"],
  ["Newsletter subscription", "/admin/newsletter", "Newsletter subscription"],
  ["Tags / categories", "/admin/taxonomy", "Tags / categories"],
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
  const adminContent = page.locator(".admin-content");
  for (const title of ["About Us", "Contact Us", "Privacy Policy", "Disclaimer"]) {
    await expect(adminContent.getByText(title, { exact: true })).toBeVisible();
  }
  await expect(adminContent.getByText("No pages yet. Create your first page.")).toHaveCount(0);
});

test("job form only offers predefined categories", async ({ page }) => {
  await page.goto("/admin/jobs/new");
  const categories = page.getByLabel("Select tags or categories");
  await expect(categories).toBeVisible();
  await categories.selectOption("Software Engineering");
  await categories.selectOption("Education");
  await expect(page.getByRole("button", { name: "Remove category Software Engineering" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove category Education" })).toBeVisible();
  await expect(page.getByPlaceholder("Add tag and press Enter")).toHaveCount(0);
  await expect(page.getByPlaceholder("Add city and press Enter")).toHaveCount(0);
  await page.getByLabel("Add city from predefined list").selectOption("Lahore");
  await expect(page.getByRole("button", { name: "Remove Lahore" })).toBeVisible();
});

test("existing R2 images load inside the job editor through the media proxy", async ({ page }) => {
  await page.goto("/admin/jobs/closed-role");
  const image = page.locator(".ql-editor img").first();
  await expect(image).toBeVisible();
  await expect(image).toHaveAttribute(
    "src",
    "http://127.0.0.1:4010/api/media/r2/job-portal/closed-role/images/notice.png",
  );
  await expect
    .poll(() => image.evaluate((element) => (element as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0);
});

test("newsletter page shows subscription count and editable alert template", async ({ page }) => {
  await page.goto("/admin/seo");
  await expect(page.getByText("Daily job alert subscriptions")).toHaveCount(0);
  await page.goto("/admin/newsletter");
  await expect(page.getByRole("heading", { name: "Newsletter subscription" })).toBeVisible();
  await expect(page.getByText("6", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Email subject")).toHaveValue(/New Job Alert/);
});

test("website title position is configurable from settings", async ({ page }) => {
  await page.goto("/admin/settings");
  await expect(page.getByRole("radiogroup", { name: "Website title position" })).toBeVisible();
  await expect(page.getByRole("radio", { name: "Center" })).toBeChecked();
  await expect(page.getByRole("heading", { name: "Homepage SEO" })).toBeVisible();
  await expect(page.getByLabel("Focus keyphrase")).toHaveValue("jobs in Pakistan");
  await expect(page.getByLabel("SEO title")).toHaveValue(
    "Jobs in Pakistan 2026 | Pakistan Jobs Market",
  );
  await expect(page.getByLabel("Meta description")).toHaveValue(
    "Find latest government and private jobs in Pakistan by city and category. Explore curated listings, deadlines, job alerts, resume tools and career guides.",
  );
  await expect(page.getByLabel("Meta keywords")).toHaveValue(
    "jobs in Pakistan, latest jobs in Pakistan, government jobs Pakistan, private jobs Pakistan, newspaper jobs, FPSC jobs, PPSC jobs, jobs by city, Pakistan Jobs Market",
  );
  await page.getByText("Beside logo", { exact: true }).click();
  await expect(page.getByRole("radio", { name: "Beside logo" })).toBeChecked();
});

test("modern header and admin workspace keep their responsive layout", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/admin/jobs");

  const header = page.locator(".site-header");
  const headerActions = page.locator(".site-actions");
  const sidebar = page.locator(".admin-nav");
  const content = page.locator(".admin-content");
  await expect(header).toBeVisible();
  await expect(headerActions).toHaveCSS("display", "flex");
  await expect(sidebar).toBeVisible();
  await expect(sidebar.locator(".admin-nav-icon")).toHaveCount(14);

  const headerBox = await header.boundingBox();
  const sidebarBox = await sidebar.boundingBox();
  const contentBox = await content.boundingBox();
  expect(headerBox?.height).toBeLessThan(100);
  expect(sidebarBox).not.toBeNull();
  expect(contentBox).not.toBeNull();
  expect((contentBox?.x || 0)).toBeGreaterThan((sidebarBox?.x || 0) + (sidebarBox?.width || 0));

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole("button", { name: "Open admin menu" })).toBeVisible();
  await expect(sidebar).toBeHidden();
  await page.getByRole("button", { name: "Open admin menu" }).click();
  await expect(sidebar).toBeVisible();
  await expect(page.locator("body")).toHaveCSS("overflow-x", "hidden");
});
