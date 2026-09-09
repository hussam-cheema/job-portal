import { expect, test } from "@playwright/test";

test("experience accepts ranges on create and preserves them after editing and reloading", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("pakjobs-admin-token", "e2e-token");
    localStorage.setItem("pakjobs-admin-user", "e2e-admin");
  });
  await page.goto("/admin/jobs/new");
  const experience = page.getByLabel("Experience required", { exact: true });
  await expect(experience).toHaveAttribute("type", "text");
  await experience.fill("2-4");
  await expect(experience).toHaveValue("2-4");
  await expect(experience).not.toHaveAttribute("max", "100");

  let savedExperience = "3 year(s)";
  let sentExperience: unknown;
  await page.route("**/api/jobs/closed-role", async (route) => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...await response.json(), experience_required: savedExperience } });
  });
  await page.route("**/api/admin/jobs/closed-role", async (route) => {
    sentExperience = route.request().postDataJSON().experience_required;
    savedExperience = `${sentExperience} year(s)`;
    await route.fulfill({ json: { id: "closed-role" } });
  });
  await page.goto("/admin/jobs/closed-role");
  await expect(experience).toHaveValue("3");
  await experience.fill("2-4");
  await page.getByRole("button", { name: "Save job", exact: true }).click();
  await expect(page.getByText("Job post updated successfully.")).toBeVisible();
  expect(sentExperience).toBe("2-4");
  await page.reload();
  await expect(experience).toHaveValue("2-4");
  await page.setViewportSize({ width: 360, height: 800 });
  await experience.scrollIntoViewIfNeeded();
  const bounds = await experience.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(360);
});
