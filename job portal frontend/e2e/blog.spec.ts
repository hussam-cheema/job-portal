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
  const listingCard = page.getByTestId("blog-card");
  await expect(listingCard).toHaveCount(1);
  const cardAndViewport = await listingCard.evaluate((card) => ({
    cardWidth: card.getBoundingClientRect().width,
    viewportWidth: window.innerWidth,
  }));
  expect(cardAndViewport.cardWidth).toBeGreaterThan(cardAndViewport.viewportWidth * 0.7);
  await page.getByRole("link", { name: "FPSC Preparation Guide" }).click();
  await expect(page.getByRole("heading", { name: "FPSC Preparation Guide" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Share this post" })).toBeVisible();
  for (const network of ["WhatsApp", "Facebook", "X"]) {
    await expect(page.getByRole("link", { name: `Share on ${network}` })).toHaveAttribute("href", /fpsc-preparation-guide/);
  }
  const layout = await page.locator(".blog-content").evaluate((content) => {
    const article = content.closest("article");
    const contentRect = content.getBoundingClientRect();
    const articleRect = article?.getBoundingClientRect();
    return {
      contentRight: contentRect.right,
      articleRight: articleRect?.right || 0,
      overflowWrap: window.getComputedStyle(content).overflowWrap,
    };
  });
  expect(layout.contentRight).toBeLessThanOrEqual(layout.articleRight + 1);
  expect(layout.overflowWrap).toBe("anywhere");

  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
  const pastedText = page.locator('[data-testid="pasted-rich-text"]');
  await expect(pastedText).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  await expect(pastedText).not.toHaveCSS("color", "rgb(0, 0, 0)");
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
  await expect(page.locator(".ql-editor")).toContainText("Build a study plan");
  await expect(page.locator('textarea[placeholder="A concise summary shown in the blog listing"]')).toHaveValue(
    "A practical preparation guide for candidates in Pakistan."
  );
  await page.getByRole("button", { name: "Save post" }).first().click();
  await expect(page.getByText("Blog post updated successfully.")).toBeVisible();
});

test("an expired admin blog token is cleared and returns to login", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("pakjobs-admin-token", "expired-e2e-token");
    localStorage.setItem("pakjobs-admin-user", "e2e-admin");
  });
  await page.goto("/admin/blog");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Admin login" })).toBeVisible();
  await expect(page.getByText("Invalid token", { exact: true })).toHaveCount(0);
});
