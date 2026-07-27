import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import JSZip from "jszip";

test("Resume Builder downloads the populated resume as PDF and editable DOCX", async ({
  page,
}) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  const header = page.locator("header");
  const resumeLink = header.getByRole("link", { name: "Resume Builder" });
  const themeToggle = header.getByRole("button", { name: /mode|theme/i });
  await expect(resumeLink).toBeVisible();
  await expect(themeToggle).toBeVisible();

  const linkBox = await resumeLink.boundingBox();
  const toggleBox = await themeToggle.boundingBox();
  expect(linkBox).not.toBeNull();
  expect(toggleBox).not.toBeNull();
  expect(linkBox!.x).toBeLessThan(toggleBox!.x);

  // Warm the lazily compiled route before exercising client-side navigation;
  // parallel dev-server compilation can otherwise dominate the navigation
  // timeout without reflecting production behavior.
  await page.goto("/resume-builder");
  await expect(page.getByRole("heading", { name: "Resume Builder", exact: true })).toBeVisible();
  await page.goto("/");
  await expect(resumeLink).toBeVisible();
  await resumeLink.click();
  await expect(page).toHaveURL(/\/resume-builder$/);
  await expect(page.getByRole("heading", { name: "Resume Builder", exact: true })).toBeVisible();

  await page.getByLabel("Full name").fill("Mary Leannon");
  await page.getByLabel("Email").fill("maryleannon@mail.com");
  await page.getByLabel("Address").fill("Zieme Crossing Suite 106, Halvorsonbury, Idaho");
  await page.getByLabel("Phone").fill("+1-123-456-7890");
  await page.getByLabel("University / school").first().fill("University of Idaho");
  await page.getByLabel("Degree / programme").first().fill("Bachelor of Science in Data Analytics");
  await page.getByLabel("Job title").first().fill("Data Analyst");
  await page.getByLabel("Company").first().fill("Example Company");

  const preview = page.getByTestId("resume-preview");
  await expect(preview.getByRole("heading", { name: "Mary Leannon" })).toBeVisible();
  await expect(preview).toContainText("University of Idaho");
  await expect(preview).toContainText("Data Analyst");

  const previewFitsWithoutScrolling = await page
    .getByTestId("resume-preview-shell")
    .evaluate((shell) => {
      const paper = shell.querySelector<HTMLElement>("[data-testid='resume-preview']");
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

  const downloadButton = page.getByRole("button", { name: "Download Resume as PDF" });
  await expect(downloadButton.locator("svg")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await downloadButton.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("mary-leannon-resume.pdf");
  if (process.env.RESUME_PDF_OUTPUT) {
    await download.saveAs(process.env.RESUME_PDF_OUTPUT);
  }
  const path = await download.path();
  expect(path).toBeTruthy();
  const bytes = await readFile(path!);
  expect(bytes.subarray(0, 4).toString()).toBe("%PDF");
  expect(bytes.length).toBeGreaterThan(20_000);

  const docxButton = page.getByRole("button", { name: "Download Resume as DOCX" });
  await expect(docxButton.locator("svg")).toBeVisible();
  await expect(docxButton).toBeEnabled();

  const docxDownloadPromise = page.waitForEvent("download");
  await docxButton.click();
  const docxDownload = await docxDownloadPromise;
  expect(docxDownload.suggestedFilename()).toBe("mary-leannon-resume.docx");
  if (process.env.RESUME_DOCX_OUTPUT) {
    await docxDownload.saveAs(process.env.RESUME_DOCX_OUTPUT);
  }
  const docxPath = await docxDownload.path();
  expect(docxPath).toBeTruthy();
  const docxBytes = await readFile(docxPath!);
  expect(docxBytes.subarray(0, 4).toString("hex")).toBe("504b0304");
  expect(docxBytes.length).toBeGreaterThan(8_000);
  const archive = await JSZip.loadAsync(docxBytes);
  const documentXml = await archive.file("word/document.xml")!.async("string");
  expect(documentXml).toContain("Mary Leannon");
  expect(documentXml).toContain("University of Idaho");
  expect(documentXml).toContain("Data Analyst");
  expect(documentXml).toContain("<w:numPr>");
  expect(pageErrors).toEqual([]);
});

test("Resume Builder includes only the selected sections without discarding their data", async ({
  page,
}) => {
  await page.goto("/resume-builder");
  const preview = page.getByTestId("resume-preview");
  const projectsToggle = page.getByRole("checkbox", { name: /^University projects/ });
  const languagesToggle = page.getByRole("checkbox", { name: "Language skills" });

  await page.getByLabel("Project title").fill("Student forecasting project");
  await page.getByRole("textbox", { name: "Language skills" }).fill("English and Urdu");
  await expect(projectsToggle).toBeChecked();
  await expect(languagesToggle).toBeChecked();

  await projectsToggle.uncheck();
  await languagesToggle.uncheck();
  await expect(page.getByTestId("resume-projects-form")).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Language skills" })).toHaveCount(0);
  await expect(preview.getByRole("heading", { name: "University Projects" })).toHaveCount(0);
  await expect(preview).not.toContainText("Language Skills:");
  await expect(preview.getByRole("heading", { name: "Activities" })).toBeVisible();

  await projectsToggle.check();
  await languagesToggle.check();
  await expect(page.getByLabel("Project title")).toHaveValue("Student forecasting project");
  await expect(page.getByRole("textbox", { name: "Language skills" })).toHaveValue(
    "English and Urdu"
  );

  await projectsToggle.uncheck();
  await languagesToggle.uncheck();
  const docxDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Resume as DOCX" }).click();
  const docxDownload = await docxDownloadPromise;
  const docxPath = await docxDownload.path();
  expect(docxPath).toBeTruthy();
  const archive = await JSZip.loadAsync(await readFile(docxPath!));
  const documentXml = await archive.file("word/document.xml")!.async("string");
  expect(documentXml).not.toContain("University Projects");
  expect(documentXml).not.toContain("Language Skills");
  expect(documentXml).toContain("Activities");
});

test("job listings use the canonical deadline without shifting to the previous day", async ({
  page,
}) => {
  await page.goto("/");
  const job = page.locator("article").filter({ hasText: "Nationwide Closed Role" });
  await job.hover();
  await expect(job.getByText("Deadline: Jul 17", { exact: true })).toBeVisible();
  await expect(job.getByText("Deadline: Jul 16", { exact: true })).toHaveCount(0);

  await page.goto("/jobs/closed-role");
  await expect(page.getByText("Deadline: 17 Jul 2026", { exact: true })).toBeVisible();
});
