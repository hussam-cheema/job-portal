import { expect, test } from "@playwright/test";

test("blog navigation, filters, article, and share links work", async ({ page }) => {
  await page.goto("/");
  const blogButton = page.getByRole("link", { name: "Blog", exact: true });
  await expect(blogButton).toBeVisible();
  const order = await page.locator("header nav a").evaluateAll((links) => links.map((link) => link.textContent?.trim()));
  expect(order.indexOf("Blog")).toBeLessThan(order.findIndex((text) => text?.includes("Resume")));
  await blogButton.click();
  await expect(page).toHaveURL(/\/blog$/);
  await expect(page.getByRole("heading", { name: "Career guidance and job updates" })).toBeVisible();
  await expect(page.getByLabel("Search blog posts")).toBeVisible();
  await expect(page.getByLabel("Filter by category")).toContainText("Career Advice");
  await page.getByRole("link", { name: "FPSC Preparation Guide" }).click();
  await expect(page.getByRole("heading", { name: "FPSC Preparation Guide" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Share this post" })).toBeVisible();
  for (const network of ["WhatsApp", "Facebook", "X"]) {
    await expect(page.getByRole("link", { name: `Share on ${network}` })).toHaveAttribute("href", /fpsc-preparation-guide/);
  }
});

test("admin can access the blog list and rich editor with Yoast", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("pakjobs-admin-token", "e2e-token");
    localStorage.setItem("pakjobs-admin-user", "e2e-admin");
  });
  await page.goto("/admin/blog");
  await expect(page.getByText("FPSC Preparation Guide", { exact: true }).first()).toBeVisible();
  await page.getByRole("link", { name: "Edit" }).click();
  await expect(page.getByRole("heading", { name: "Edit blog post" })).toBeVisible();
  await expect(page.getByText("Yoast SEO", { exact: true })).toBeVisible();
  await expect(page.locator(".quill-wrap")).toBeVisible();
  await expect(page.locator('input[value="FPSC Preparation Guide"]').first()).toBeVisible();
});
