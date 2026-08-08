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
  test.setTimeout(120_000);
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

test("infrastructure analytics only shows active services and the payment-aware cost ledger", async ({
  page,
}) => {
  await page.goto("/admin/infrastructure");
  await expect(
    page.getByRole("heading", { name: "Infrastructure analytics", exact: true }),
  ).toBeVisible();

  for (const label of [
    "Current outstanding",
    "Current billed",
    "Current paid",
    "Recorded total",
    "Total outstanding",
    "Monthly cost history",
    "Backend API + newsletter retry",
    "PostgreSQL database",
    "Frontend hosting",
  ]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText("Paid", { exact: true })).toBeVisible();

  for (const removedLabel of [
    "Connection pool",
    "Signals",
    "Managed service limits",
    "Frontend quotas",
  ]) {
    await expect(page.getByText(removedLabel, { exact: true })).toHaveCount(0);
  }
});

test("a stale Next.js chunk is handled silently without refreshing the current page", async ({
  page,
}) => {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await page.evaluate(() => {
    (window as typeof window & { __preservedEditorMarker?: string }).__preservedEditorMarker =
      "keep-current-page";
  });
  await page.evaluate(() => {
    setTimeout(() => Promise.reject(new Error("ChunkLoadError: Loading chunk 123 failed")), 0);
  });
  await page.waitForTimeout(250);
  await expect(page.getByText("A website update is available.")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Update website" })).toHaveCount(0);
  await expect(page).toHaveURL(/\/admin$/);
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (window as typeof window & { __preservedEditorMarker?: string })
            .__preservedEditorMarker
      )
    )
    .toBe("keep-current-page");
});

test("a stale chunk during admin navigation completes the requested destination", async ({
  page,
}) => {
  await page.goto("/admin");
  await page.evaluate(() => {
    sessionStorage.setItem(
      "pakjobs-admin-navigation-target",
      `${window.location.origin}/admin/blog`
    );
    setTimeout(() => Promise.reject(new Error("ChunkLoadError: Loading chunk 456 failed")), 0);
  });
  await expect(page).toHaveURL(/\/admin\/blog$/);
  await expect(page.getByRole("heading", { name: "Blog posts" })).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() =>
        sessionStorage.getItem("pakjobs-admin-navigation-target")
      )
    )
    .toBeNull();
});

test("job and blog drafts survive refresh and can be edited or deleted", async ({
  page,
}) => {
  await page.goto("/admin/jobs/new");
  await page.getByLabel("Job title").fill("Recovered infrastructure role");
  const jobDescription = page.locator(".ql-editor").first();
  await jobDescription.fill("This description must survive an unexpected refresh.");
  await expect(page.getByTestId("editor-draft-status")).toContainText(
    "Draft auto-saved locally."
  );
  await page.reload();
  await expect(page.getByLabel("Job title")).toHaveValue(
    "Recovered infrastructure role"
  );
  await expect(page.locator(".ql-editor").first()).toContainText(
    "This description must survive an unexpected refresh."
  );
  await expect(page.getByTestId("editor-draft-status")).toContainText(
    "Recovered your auto-saved draft."
  );

  await page.goto("/admin/jobs");
  const jobDrafts = page.getByRole("region", { name: "Saved job drafts" });
  await expect(jobDrafts.getByText("Recovered infrastructure role")).toBeVisible();
  await expect(jobDrafts.getByText("Local draft")).toBeVisible();
  await jobDrafts.getByRole("link", { name: "Edit" }).click();
  await expect(page.getByLabel("Job title")).toHaveValue(
    "Recovered infrastructure role"
  );
  await page.goto("/admin/jobs");
  page.once("dialog", (dialog) => dialog.accept());
  await jobDrafts.getByRole("button", { name: "Delete" }).click();
  await expect(jobDrafts).toHaveCount(0);

  await page.goto("/admin/blog/new");
  await page.getByLabel("Blog title").fill("Recovered career guide");
  const blogContent = page.locator(".ql-editor").first();
  await blogContent.fill("This article content must also survive refresh.");
  await page.getByRole("link", { name: "← All posts" }).click();
  const immediateBlogDrafts = page.getByRole("region", {
    name: "Saved blog drafts",
  });
  await expect(immediateBlogDrafts.getByText("Recovered career guide")).toBeVisible();
  await expect(immediateBlogDrafts.getByText("Local draft")).toBeVisible();
  await immediateBlogDrafts.getByRole("link", { name: "Edit" }).click();
  await expect(page.getByLabel("Blog title")).toHaveValue("Recovered career guide");
  await expect(page.locator(".ql-editor").first()).toContainText(
    "This article content must also survive refresh."
  );
  await page.reload();
  await expect(page.getByLabel("Blog title")).toHaveValue("Recovered career guide");
  await expect(page.locator(".ql-editor").first()).toContainText(
    "This article content must also survive refresh."
  );
  await expect(page.getByTestId("editor-draft-status")).toContainText(
    "Recovered your auto-saved draft."
  );

  await page.goto("/admin/blog");
  const blogDrafts = page.getByRole("region", { name: "Saved blog drafts" });
  await expect(blogDrafts.getByText("Recovered career guide")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await blogDrafts.getByRole("button", { name: "Delete" }).click();
  await expect(blogDrafts).toHaveCount(0);
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
  await page.getByLabel("Add province or territory").selectOption("Punjab");
  await expect(page.getByRole("button", { name: "Remove Punjab" })).toBeVisible();
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

test("clipboard image paste uploads and renders through the media proxy", async ({ page }) => {
  await page.goto("/admin/jobs/new");
  const editor = page.locator(".ql-editor").first();
  await expect(editor).toBeVisible();
  await editor.evaluate((element) => {
    const binary = atob(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    );
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    const file = new File([bytes], "clipboard.png", { type: "image/png" });
    const clipboard = new DataTransfer();
    clipboard.items.add(file);
    element.dispatchEvent(
      new ClipboardEvent("paste", {
        bubbles: true,
        cancelable: true,
        clipboardData: clipboard,
      }),
    );
  });

  const image = editor.locator("img").first();
  await expect(image).toHaveAttribute(
    "src",
    "http://127.0.0.1:4010/api/media/r2/job-portal/pasted/images/clipboard.png",
  );
  await expect
    .poll(() => image.evaluate((element) => (element as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0);
});

test("toolbar upload and clipboard paste keep working in the same editor", async ({ page }) => {
  await page.goto("/admin/jobs/new");
  const editor = page.locator(".ql-editor").first();
  await expect(editor).toBeVisible();
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );

  const chooserPromise = page.waitForEvent("filechooser");
  await page.locator(".ql-toolbar .ql-image").first().click();
  const chooser = await chooserPromise;
  await chooser.setFiles({
    name: "toolbar-upload.png",
    mimeType: "image/png",
    buffer: png,
  });
  await expect(editor.locator("img")).toHaveCount(1);

  await editor.evaluate((element, bytes) => {
    const file = new File([Uint8Array.from(bytes)], "clipboard-after-upload.png", {
      type: "image/png",
    });
    const clipboard = new DataTransfer();
    clipboard.items.add(file);
    element.dispatchEvent(
      new ClipboardEvent("paste", {
        bubbles: true,
        cancelable: true,
        clipboardData: clipboard,
      }),
    );
  }, Array.from(png));

  await expect(editor.locator("img")).toHaveCount(2);
  await editor.click();
  await page.keyboard.type("Both image paths remain editable.");
  await expect(editor).toContainText("Both image paths remain editable.");
  for (const image of await editor.locator("img").all()) {
    await expect(image).toHaveAttribute(
      "src",
      "http://127.0.0.1:4010/api/media/r2/job-portal/pasted/images/clipboard.png",
    );
    await expect
      .poll(() => image.evaluate((element) => (element as HTMLImageElement).naturalWidth))
      .toBeGreaterThan(0);
  }
});

test("HTML and Markdown tables keep separate header cells in job and blog editors", async ({
  page,
}) => {
  const pasteTable = async (
    path: string,
    titleLabel: string,
    title: string,
    includeHtml: boolean,
  ) => {
    await page.goto(path);
    await page.getByLabel(titleLabel).fill(title);
    const editor = page.locator(".ql-editor").first();
    await expect(editor).toBeVisible();
    await editor.click();
    await editor.evaluate((element, hasHtml) => {
      const clipboard = new DataTransfer();
      if (hasHtml) {
        clipboard.setData(
          "text/html",
          [
            "<table>",
            "<thead><tr>",
            "<th>Region</th>",
            "<th>Requests/min</th>",
            "<th>Avg. latency</th>",
            "<th>Status</th>",
            "</tr></thead>",
            "<tbody>",
            "<tr><td>UAE North</td><td>1,250</td><td>85 ms</td><td>Healthy</td></tr>",
            "<tr><td>West Europe</td><td>980</td><td>120 ms</td><td>Healthy</td></tr>",
            "<tr><td>East US</td><td>720</td><td>190 ms</td><td>Healthy</td></tr>",
            "<tr><td>Southeast Asia</td><td>430</td><td>145 ms</td><td>Degraded</td></tr>",
            "</tbody>",
            "</table>",
          ].join(""),
        );
      }
      clipboard.setData(
        "text/plain",
        [
          "| Region | Requests/min | Avg. latency | Status |",
          "| --- | ---: | ---: | --- |",
          "| UAE North | 1,250 | 85 ms | Healthy |",
          "| West Europe | 980 | 120 ms | Healthy |",
          "| East US | 720 | 190 ms | Healthy |",
          "| Southeast Asia | 430 | 145 ms | Degraded |",
        ].join("\n"),
      );
      element.dispatchEvent(
        new ClipboardEvent("paste", {
          bubbles: true,
          cancelable: true,
          clipboardData: clipboard,
        }),
      );
    }, includeHtml);

    const table = editor.locator("table");
    await expect(table).toHaveCount(1);
    await expect(table.locator("tr")).toHaveCount(5);
    const headerCells = table.locator("tr").first().locator("th, td");
    await expect(headerCells).toHaveCount(4);
    await expect(headerCells).toHaveText([
      "Region",
      "Requests/min",
      "Avg. latency",
      "Status",
    ]);
    await expect(table.locator("tr").nth(1).locator("th, td")).toHaveText([
      "UAE North",
      "1,250",
      "85 ms",
      "Healthy",
    ]);
    await expect(table).toContainText("Southeast Asia");
    await expect(table).toContainText("Degraded");
    await expect(table).toHaveCSS("overflow-x", "auto");
    await expect(table.locator("td").first()).toHaveCSS("border-bottom-style", "solid");

    await expect(page.getByTestId("editor-draft-status")).toContainText(
      "Draft auto-saved locally.",
    );
    await page.reload();
    await expect(page.getByLabel(titleLabel)).toHaveValue(title);
    await expect(page.locator(".ql-editor").first().locator("table")).toHaveCount(1);
    await expect(
      page.locator(".ql-editor").first().locator("table tr").first().locator("th, td"),
    ).toHaveText(["Region", "Requests/min", "Avg. latency", "Status"]);
    await expect(page.locator(".ql-editor").first()).toContainText("Southeast Asia");
  };

  await pasteTable("/admin/jobs/new", "Job title", "Table paste job draft", true);
  await pasteTable("/admin/blog/new", "Blog title", "Table paste blog draft", false);
});

test("newsletter page shows subscription count and editable alert template", async ({ page }) => {
  await page.goto("/admin/seo");
  await expect(page.getByText("Daily job alert subscriptions")).toHaveCount(0);
  await page.goto("/admin/newsletter");
  await expect(page.getByRole("heading", { name: "Newsletter subscription" })).toBeVisible();
  await expect(page.getByText("6", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Email subject")).toHaveValue(/New Job Alert/);
});

test("keyword rankings scroll after twenty unique rows", async ({ page }) => {
  await page.goto("/admin/seo");
  const section = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Keyword rankings", exact: true }),
  });
  await expect(section.locator("tbody tr")).toHaveCount(21);
  await expect(section.locator(".overflow-y-auto")).toHaveCSS("overflow-y", "auto");
  await expect(section.getByRole("columnheader", { name: "Avg position" })).toBeVisible();
  await expect(section.getByRole("columnheader", { name: "Impressions" })).toBeVisible();
  await expect(section.getByRole("columnheader", { name: "CTR" })).toBeVisible();
  await expect(section.getByRole("columnheader", { name: "Page", exact: true })).toHaveCount(0);
});

test("SEO dashboard explains average position and hides duplicate backlinks", async ({ page }) => {
  await page.goto("/admin/seo");
  await expect(
    page.getByText(/Manual searches can differ by location, device, history, and time/),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "URL search performance" })).toBeVisible();
  const backlinks = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Backlinks", exact: true }),
  });
  await expect(
    backlinks.getByRole("link", { name: /linkedin\.com\/company\/pakistanjobsmarket/ }),
  ).toHaveCount(1);
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
  await expect(page.getByRole("textbox", { name: "LinkedIn URL" })).toHaveValue(
    "https://linkedin.com/company/pakistanjobsmarket",
  );
  await page.getByText("Beside logo", { exact: true }).click();
  await expect(page.getByRole("radio", { name: "Beside logo" })).toBeChecked();
  await page.getByRole("button", { name: "Save website settings" }).click();
  await expect(page.getByText("Website text, homepage SEO, and footer updated.")).toBeVisible();
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
