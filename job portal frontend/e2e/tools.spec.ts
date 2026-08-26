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
  await expect(page.getByText("2 Tools", { exact: false })).toBeVisible();
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
  await expect(page.getByRole("link", { name: "Tax & Salary Tools" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Tools for Students" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Pakistan Tax Calculator" })).toBeVisible();
  await expect(page.getByText("Tools coming soon")).toHaveCount(2);
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
