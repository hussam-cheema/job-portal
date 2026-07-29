import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import JSZip from "jszip";

test("Cover Letter follows Resume Builder and downloads PDF and editable DOCX", async ({
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
  const signatureName = page
    .getByTestId("cover-letter-preview")
    .locator(".cover-letter-signature strong");
  await expect(signatureName).toHaveText("(YOUR NAME)");
  await expect(signatureName).toHaveCSS("color", "rgb(0, 0, 0)");
  await page.getByLabel("Cover letter title").fill("Google Cover Letter");
  await expect(page.getByLabel("Subtitle")).toHaveCount(0);
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
  await expect(preview).not.toContainText("by CV Genius");
  await expect(preview).toContainText("31 August 2026");
  await expect(preview).toContainText("Dear Morgan,");
  await expect(preview).toContainText("I am applying for the Senior Software Engineer position.");
  await expect(preview).toContainText("Mary Leannon");
  await expect(signatureName).toHaveCSS("color", "rgb(0, 0, 0)");

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

  const docxButton = page.getByRole("button", { name: "Download Cover Letter as DOCX" });
  await expect(docxButton.locator("svg")).toBeVisible();
  await expect(docxButton).toBeEnabled();

  const docxDownloadPromise = page.waitForEvent("download");
  await docxButton.click();
  const docxDownload = await docxDownloadPromise;
  expect(docxDownload.suggestedFilename()).toBe("mary-leannon-cover-letter.docx");
  if (process.env.COVER_LETTER_DOCX_OUTPUT) {
    await docxDownload.saveAs(process.env.COVER_LETTER_DOCX_OUTPUT);
  }
  const docxPath = await docxDownload.path();
  expect(docxPath).toBeTruthy();
  const docxBytes = await readFile(docxPath!);
  expect(docxBytes.subarray(0, 4).toString("hex")).toBe("504b0304");
  expect(docxBytes.length).toBeGreaterThan(7_000);
  const archive = await JSZip.loadAsync(docxBytes);
  const documentXml = await archive.file("word/document.xml")!.async("string");
  expect(documentXml).toContain("Mary Leannon");
  expect(documentXml).toContain("GOOGLE COVER LETTER");
  expect(documentXml).not.toContain("by CV Genius");
  expect(documentXml).toContain("I am applying for the Senior Software Engineer position.");
  expect(documentXml).toContain("31 August 2026");
  expect((documentXml.match(/<w:tbl>/g) ?? []).length).toBeGreaterThanOrEqual(5);
  expect(documentXml).toContain(
    '<w:gridCol w:w="567"/><w:gridCol w:w="9864"/><w:gridCol w:w="567"/>'
  );
  expect(documentXml).toContain('w:lineRule="exact"');
  expect(documentXml).toContain('<w:top w:val="single" w:color="9B9B9B"');
  expect(pageErrors).toEqual([]);
});
