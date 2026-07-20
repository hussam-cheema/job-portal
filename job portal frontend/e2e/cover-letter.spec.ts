import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("Cover Letter follows Resume Builder and downloads the populated A4 letter as a PDF", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  const header = page.locator("header");
  const resumeLink = header.getByRole("link", { name: "Resume Builder" });
  const coverLetterLink = header.getByRole("link", { name: "Cover Letter" });
  const themeToggle = header.getByRole("button", { name: /mode|theme/i });
  await expect(resumeLink).toBeVisible();
  await expect(coverLetterLink).toBeVisible();
  await expect(themeToggle).toBeVisible();
  const resumeBox = await resumeLink.boundingBox();
  const coverBox = await coverLetterLink.boundingBox();
  const toggleBox = await themeToggle.boundingBox();
  expect(resumeBox).not.toBeNull();
  expect(coverBox).not.toBeNull();
  expect(toggleBox).not.toBeNull();
  expect(resumeBox!.x).toBeLessThan(coverBox!.x);
  expect(coverBox!.x).toBeLessThan(toggleBox!.x);

  await page.goto("/cover-letter");
  await expect(page.getByRole("heading", { name: "Cover Letter", exact: true })).toBeVisible();
  await page.getByLabel("Cover letter title").fill("Google Cover Letter");
  await page.getByLabel("Subtitle").fill("by CV Genius");
  await page.getByLabel("Full name").fill("Mary Leannon");
  await page.getByLabel("Phone").fill("07123 456 789");
  await page.getByLabel("Email").fill("mary@example.com");
  await page.getByLabel("Address", { exact: true }).fill("26 Springfield Road, London, N39 6CU");
  await page.getByLabel("Letter date").fill("2026-08-31");
  await page.getByLabel("Contact person's name").fill("Alex Morgan");
  await page.getByLabel("Company name").fill("Google");
  await page.getByLabel("Company address").fill("1 Company Street\nLondon");
  await page.getByLabel("Contact person's surname").fill("Morgan");
  await page.getByLabel("Opening paragraph").fill("I am applying for the Senior Software Engineer position.");
  await page.getByLabel("Sign-off").fill("Yours sincerely,");

  const preview = page.getByTestId("cover-letter-preview");
  await expect(preview.getByRole("heading", { name: "GOOGLE COVER LETTER" })).toBeVisible();
  await expect(preview).toContainText("31 August 2026");
  await expect(preview).toContainText("Dear Morgan,");
  await expect(preview).toContainText("I am applying for the Senior Software Engineer position.");
  await expect(preview).toContainText("Mary Leannon");

  const previewFitsWithoutScrolling = await page
    .getByTestId("cover-letter-preview-shell")
    .evaluate((shell) => {
      const paper = shell.querySelector<HTMLElement>("[data-testid='cover-letter-preview']");
      if (!paper) return false;
      const shellBox = shell.getBoundingClientRect();
      const paperBox = paper.getBoundingClientRect();
      const style = window.getComputedStyle(shell);
      return (
        style.overflowX === "hidden" &&
        style.overflowY === "hidden" &&
        paperBox.width <= shellBox.width &&
        paperBox.height <= shellBox.height
      );
    });
  expect(previewFitsWithoutScrolling).toBe(true);

  const downloadButton = page.getByRole("button", { name: "Download Cover Letter as PDF" });
  await expect(downloadButton.locator("svg")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await downloadButton.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("mary-leannon-cover-letter.pdf");
  const path = await download.path();
  expect(path).toBeTruthy();
  const bytes = await readFile(path!);
  expect(bytes.subarray(0, 4).toString()).toBe("%PDF");
  expect(bytes.length).toBeGreaterThan(15_000);
  expect(pageErrors).toEqual([]);
});
