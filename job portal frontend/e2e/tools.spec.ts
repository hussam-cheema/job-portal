import { expect, test } from "@playwright/test";

test("tools admin keeps the directory above the editor at desktop and tablet widths", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/login");
  const loginFields = page.getByRole("textbox");
  await loginFields.nth(0).fill("admin");
  await loginFields.nth(1).fill("e2e-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await page.goto("/admin/tools");

  await expect(page.getByRole("heading", { name: "Other Tools", exact: true })).toBeVisible();
  await expect(page.getByText("4 Categories", { exact: false })).toBeVisible();
  await expect(page.getByText("8 Tools", { exact: false })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Find a category or tool" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Basic information" })).toBeVisible();

  const directory = page.locator(".admin-tools-list");
  const editor = page.locator(".admin-tool-editor");
  const directoryBox = await directory.boundingBox();
  const editorBox = await editor.boundingBox();
  expect(directoryBox).not.toBeNull();
  expect(editorBox).not.toBeNull();
  expect(editorBox!.y).toBeGreaterThan(directoryBox!.y + directoryBox!.height - 2);

  await page.getByRole("searchbox", { name: "Find a category or tool" }).fill("CGPA");
  await expect(page.getByRole("button", { name: /^Tools for Students/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Tax & Salary Tools/ })).toHaveCount(0);

  await page.getByRole("button", { name: "+ New tool" }).click();
  await expect(page.getByRole("heading", { name: "Tool page" })).toBeVisible();
  await expect(page.getByLabel("Tool experience")).toHaveCount(0);
  await expect(page.getByText("New tools are created as fully editable content pages.", { exact: false })).toBeVisible();

  await page.setViewportSize({ width: 1100, height: 900 });
  const stackedDirectoryBox = await directory.boundingBox();
  const stackedEditorBox = await editor.boundingBox();
  expect(stackedDirectoryBox).not.toBeNull();
  expect(stackedEditorBox).not.toBeNull();
  expect(stackedEditorBox!.y).toBeGreaterThan(stackedDirectoryBox!.y + stackedDirectoryBox!.height - 2);
});

test("Other Tools navigation opens a dynamic four-branch directory", async ({ page }) => {
  await page.goto("/");
  const toolsLink = page.getByRole("link", { name: /Other Tools|Tools/ });
  await expect(toolsLink).toBeVisible();
  await toolsLink.click();
  await expect(page).toHaveURL(/\/tools$/);
  await expect(page.getByRole("heading", { name: "Other Tools" })).toBeVisible();
  await expect(page.getByText("TOOLS", { exact: true })).toBeVisible();
  const constellation = page.locator(".tools-constellation");
  await expect(constellation.getByRole("link", { name: "Tax & Salary Tools" })).toBeVisible();
  await expect(constellation.getByRole("link", { name: "Tools for Students" })).toBeVisible();
  await expect(constellation.getByRole("link", { name: "Pakistan Tax Calculator" })).toBeVisible();
  await expect(constellation.getByRole("link", { name: "Government Salary Calculator" })).toBeVisible();
  await expect(constellation.getByRole("link", { name: "Resume Builder" })).toHaveAttribute("href", "/tools/resume-builder");
  await expect(constellation.getByRole("link", { name: "Cover Letter Builder" })).toHaveAttribute("href", "/tools/cover-letter");
  await expect(constellation.locator('a[href="/tools/api"]')).toContainText("API");
  await expect(constellation.getByRole("link", { name: "DOCX and PDF Converter" })).toBeVisible();
  await expect(constellation.getByRole("link", { name: "Add Watermark to Image" })).toHaveAttribute("href", "/tools/add-watermark");
  await expect(page.getByText("Tools coming soon")).toHaveCount(0);
  const seoContent = page.locator(".tools-seo-content");
  await expect(seoContent.getByRole("heading", { name: "Free calculators and career tools for Pakistan" })).toBeVisible();
  await expect(seoContent.getByRole("link", { name: "latest jobs in Pakistan" })).toHaveAttribute("href", "/");
  await expect(seoContent.getByRole("link", { name: "career guides" })).toHaveAttribute("href", "/blog");
});

test("retired watermark remover is no longer listed or served", async ({ page }) => {
  await page.goto("/tools");
  await expect(page.getByRole("link", { name: "Remove Watermark from Image" })).toHaveCount(0);
  const response = await page.goto("/tools/remove-watermark");
  expect(response?.status()).toBe(404);
});

test("student tool shortcuts open the builders and student API", async ({ page }) => {
  await page.goto("/tools/categories/tools-for-students");
  const directory = page.locator(".tool-category-grid");
  const resume = directory.getByRole("link", { name: /Resume Builder/ });
  const coverLetter = directory.getByRole("link", { name: /Cover Letter Builder/ });
  const api = directory.locator('a[href="/tools/api"]');
  await expect(resume).toHaveAttribute("href", "/tools/resume-builder");
  await expect(coverLetter).toHaveAttribute("href", "/tools/cover-letter");
  await expect(api).toHaveAttribute("href", "/tools/api");
  await resume.click();
  await expect(page).toHaveURL(/\/tools\/resume-builder$/);
  await page.goto("/tools/categories/tools-for-students");
  await page.locator(".tool-category-grid").getByRole("link", { name: /Cover Letter Builder/ }).click();
  await expect(page).toHaveURL(/\/tools\/cover-letter$/);
});

test("student API verifies a subscribed email, reveals the key once, and documents usage", async ({ page }) => {
  await page.route("**/api/student-api/request-code", async (route) => {
    expect(route.request().postDataJSON()).toEqual({ email: "student@example.com" });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({
        status: "code_sent",
        message: "A six-digit verification code was sent to your subscribed email.",
        expires_in_seconds: 600,
        retry_after_seconds: 60,
      }),
    });
  });
  await page.route("**/api/student-api/verify-code", async (route) => {
    expect(route.request().postDataJSON()).toEqual({ email: "student@example.com", code: "123456" });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({
        status: "verified",
        message: "Email verified. Copy this API key now; it will not be shown again.",
        api_key: "pjm_live_test_key_for_browser_1234567890",
        key_prefix: "pjm_live_test_key_",
        quota_total: 50,
        requests_used: 0,
        requests_remaining: 50,
        documentation_url: "https://pakistanjobsmarket.com/tools/api",
      }),
    });
  });

  await page.goto("/tools/api");
  await expect(page.getByRole("heading", { name: "API", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Create your student API key" })).toBeVisible();
  await page.getByLabel("Newsletter email").fill("student@example.com");
  await page.getByRole("button", { name: "Email me a code" }).click();
  await expect(page.getByLabel("Six-digit verification code")).toBeVisible();
  await page.getByLabel("Six-digit verification code").fill("123456");
  await page.getByRole("button", { name: "Verify and create key" }).click();
  await expect(page.getByText("pjm_live_test_key_for_browser_1234567890")).toBeVisible();
  await expect(page.getByText("Requests left", { exact: true })).toBeVisible();
  await expect(page.getByText("50", { exact: true }).last()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Read jobs and blog posts" })).toBeVisible();
  await expect(page.getByText("/jobs/{slug}", { exact: true })).toBeVisible();
  await expect(page.getByText("X-API-Key", { exact: false }).first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "Create your student API key" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("document converter validates one file, reports progress, downloads, and is tracked by analytics", async ({ page }) => {
  const analyticsRequest = page.waitForRequest((request) =>
    request.url().endsWith("/api/analytics/visit")
      && request.method() === "POST"
      && request.postData()?.includes("/tools/docx-pdf-converter") === true,
  );
  await page.goto("/tools/docx-pdf-converter");
  await expect(page.getByRole("heading", { name: "DOCX and PDF Converter" })).toBeVisible();
  await analyticsRequest;

  const input = page.locator("#document-converter-file");
  await input.setInputFiles({ name: "malware.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ") });
  await expect(page.locator(".document-converter-message[role='alert']")).toContainText("not allowed");

  await input.setInputFiles({ name: "sample.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 mock") });
  await expect(page.getByLabel("Conversion direction")).toContainText("PDF");
  await expect(page.getByLabel("Conversion direction")).toContainText("DOCX");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Convert to DOCX" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("sample.docx");
  await expect(page.getByRole("progressbar", { name: "Conversion progress" })).toHaveAttribute("aria-valuenow", "100");
  await expect(page.getByText("Ready to download")).toBeVisible();
});

test("Pakistan salary tax calculator covers current and historic years", async ({ page }) => {
  await page.goto("/tools/pakistan-tax-calculator");
  await expect(page.getByRole("heading", { name: "Pakistan Tax Calculator" })).toBeVisible();
  await page.getByLabel("Monthly salary").fill("100000");
  await page.getByLabel("Tax year").selectOption("2026-2027");
  const calculator = page.getByTestId("tax-calculator");
  await expect(calculator.getByText("PKR 6,000", { exact: true })).toBeVisible();
  await expect(calculator.getByText("PKR 500", { exact: true })).toBeVisible();
  await expect(calculator.getByText("PKR 99,500", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Tax year").locator("option")).toHaveCount(13);
});

test("government salary calculator covers federal and organization-specific scales", async ({ page }) => {
  await page.goto("/tools/categories/tax-salary-tools");
  const categoryTools = page.locator(".tool-category-grid a");
  await expect(categoryTools.nth(0)).toContainText("Pakistan Tax Calculator");
  await expect(categoryTools.nth(1)).toContainText("Government Salary Calculator");
  await categoryTools.nth(1).click();

  const calculator = page.getByTestId("government-salary-calculator");
  await expect(page.getByRole("heading", { name: "Government Salary Calculator" })).toBeVisible();
  await expect(calculator.getByText("PKR 16,280", { exact: true })).toBeVisible();
  await expect(calculator.getByText("Basic pay (BPS 2026)")).toBeVisible();
  await expect(calculator.getByText("House rent allowance", { exact: true })).toBeVisible();
  await expect(calculator.getByText("Conveyance allowance", { exact: true })).toBeVisible();
  await expect(calculator.getByText("Medical allowance", { exact: true })).toBeVisible();

  await page.getByLabel("Pay scale").selectOption("PPS");
  await page.getByLabel("Government grade").selectOption("12");
  await page.getByLabel("Pay stage").selectOption("5");
  await expect(calculator.getByText("PKR 1,207,500", { exact: true }).first()).toBeVisible();
  await expect(calculator.getByText("no additional facility", { exact: false })).toBeVisible();

  await page.getByLabel("Pay scale").selectOption("EG");
  await expect(page.getByLabel("Government grade").locator("option")).toHaveCount(9);
  await page.getByLabel("Government grade").selectOption("9");
  await page.getByLabel("Official package amount").fill("250000");
  await expect(calculator.getByText("PKR 250,000", { exact: true }).first()).toBeVisible();
  await expect(calculator.getByText("EG is not a single nationwide monetary scale", { exact: false })).toBeVisible();
  await expect(calculator.getByRole("link", { name: /Senate of Pakistan/ })).toBeVisible();
});

test("CGPA calculator supports arbitrary subjects and semesters", async ({ page }) => {
  await page.goto("/tools/cgpa-calculator");
  await expect(page.getByRole("heading", { name: "CGPA Calculator" })).toBeVisible();
  await page.getByLabel("Subject 1 obtained GPA").fill("4");
  await page.getByLabel("Subject 2 obtained GPA").fill("3");
  await expect(page.getByText("3.50", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "Add another semester" }).click();
  await expect(page.getByText("Semester 2", { exact: true })).toBeVisible();
  await page.getByLabel("Semester 2 subject 1").fill("Mathematics");
  await page.getByLabel("Subject 1 obtained GPA").nth(1).fill("2");
  await expect(page.getByText("3.00", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "Add subject" }).last().click();
  await expect(page.getByLabel("Semester 2 subject 2")).toBeVisible();
});
