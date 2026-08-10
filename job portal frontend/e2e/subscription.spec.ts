import { expect, test } from "@playwright/test";

test("public new-job alert form validates and subscribes an email", async ({ page }) => {
  await page.goto("/");
  const email = page.getByLabel("Email address");
  await email.fill("invalid");
  await page.getByRole("button", { name: "Subscribe" }).click();
  await expect(page.getByText("Enter a valid email address.")).toBeVisible();
  await email.fill("reader@gmail.com");
  await page.getByRole("button", { name: "Subscribe" }).click();
  await expect(page.getByText("Your email has been subscribed to new job alerts.")).toBeVisible();
});

test("subscription network failures are handled and shown to the user", async ({ page }) => {
  await page.route("**/api/subscriptions", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Subscription service is temporarily unavailable." }),
    });
  });
  await page.goto("/");
  await page.getByLabel("Email address").fill("reader@gmail.com");
  await page.getByRole("button", { name: "Subscribe" }).click();
  await expect(page.getByText("Subscription service is temporarily unavailable.")).toBeVisible();
});

test("unsubscribe link removes a newsletter subscription", async ({ page }) => {
  await page.goto("/unsubscribe?token=personal-token");
  await expect(page.getByText("You have been unsubscribed.")).toBeVisible();
});

test("nationwide expired jobs show Pakistan and Applications Closed on list and detail", async ({ page }) => {
  await page.goto("/");
  const card = page.getByRole("article").filter({ hasText: "Nationwide Closed Role" });
  await expect(card.getByText(/FPSC · Pakistan/)).toBeVisible();
  await expect(card.getByText("Applications Closed", { exact: true })).toBeVisible();
  await card.getByRole("link", { name: "Nationwide Closed Role" }).click();
  await expect(page.getByRole("heading", { name: "Nationwide Closed Role" })).toBeVisible();
  await expect(page.getByText("Applications Closed", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "https://fpsc.gov.pk/advertisement" })).toHaveAttribute("href", "https://fpsc.gov.pk/advertisement");
  await expect(page.getByRole("link", { name: "https://fpsc.gov.pk/apply" })).toHaveCount(0);
});

test("homepage category selector contains only controlled categories", async ({ page }) => {
  await page.goto("/");
  const categories = page.getByLabel("Category");
  await expect(categories.locator("option")).toHaveText(["All categories", "Software Engineering"]);
  await expect(categories.locator('option[value="Lahore"]')).toHaveCount(0);
  await expect(categories.locator('option[value="Government"]')).toHaveCount(0);
  await expect(categories.locator('option[value="Private"]')).toHaveCount(0);
});
