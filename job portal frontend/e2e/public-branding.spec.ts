import { expect, test } from "@playwright/test";

test("public branding, homepage text, footer, and disclaimer navigation render", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  await expect(page.locator("header").getByText("PakJobs Jobs in Pakistan", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Latest government & private job openings in Pakistan",
      exact: true,
    })
  ).toBeVisible();
  await expect(page.getByText("Pakistan jobs", { exact: true })).toHaveCount(0);
  await expect(page.locator("footer")).toContainText(
    `Copyrights © ${new Date().getFullYear()} - PakistanJobs All rights reserved`
  );
  await expect(page.locator("footer").getByRole("link", { name: "Disclaimer" })).toHaveAttribute(
    "href",
    "/disclaimer"
  );
  expect(pageErrors).toEqual([]);
});
