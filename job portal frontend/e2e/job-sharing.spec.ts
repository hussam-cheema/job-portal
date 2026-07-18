import { expect, test } from "@playwright/test";

test("a job can be shared without social API credentials", async ({ page }) => {
  await page.goto("/jobs/closed-role");

  await expect(page.getByRole("heading", { name: "Share this job" })).toBeVisible();

  const whatsapp = page.getByRole("link", { name: "Share on WhatsApp" });
  const facebook = page.getByRole("link", { name: "Share on Facebook" });
  const x = page.getByRole("link", { name: "Share on X" });

  await expect(whatsapp).toHaveAttribute("href", /^https:\/\/wa\.me\/\?text=/);
  await expect(facebook).toHaveAttribute(
    "href",
    /^https:\/\/www\.facebook\.com\/sharer\/sharer\.php\?u=/
  );
  await expect(x).toHaveAttribute("href", /^https:\/\/x\.com\/intent\/post\?/);

  for (const link of [whatsapp, facebook, x]) {
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", /noopener/);
    await expect(link).toHaveAttribute("href", /closed-role/);
  }

  await expect(page.getByRole("link", { name: /Messenger/i })).toHaveCount(0);
});
