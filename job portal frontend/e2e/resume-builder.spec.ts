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
  await page.goto("/tools/resume-builder");
  await expect(page.getByRole("heading", { name: "Resume Builder", exact: true })).toBeVisible();
  await page.goto("/");
  await expect(resumeLink).toBeVisible();
  await resumeLink.click();
  await expect(page).toHaveURL(/\/tools\/resume-builder$/);
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
  // The PDF keeps the exact visual capture but must also expose a searchable
  // text layer so applicant-tracking systems do not receive an image only.
  expect(bytes.toString("latin1")).toContain("Mary Leannon");
  expect(bytes.toString("latin1")).toContain("University of Idaho");
  expect(bytes.toString("latin1")).toContain("Data Analyst");

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
  expect(documentXml.toLowerCase()).toContain("mary leannon");
  expect(documentXml).toContain("University of Idaho");
  expect(documentXml).toContain("Data Analyst");
  expect(documentXml).toContain("<w:numPr>");
  expect((documentXml.match(/<w:tbl>/g) ?? []).length).toBeGreaterThanOrEqual(10);
  expect(documentXml).toContain('<w:bottom w:val="single" w:color="222222"');
  expect(documentXml).toContain(
    '<w:gridCol w:w="7560"/><w:gridCol w:w="3212"/>'
  );
  expect(pageErrors).toEqual([]);
});

test("Resume Builder includes only the selected sections without discarding their data", async ({
  page,
}) => {
  await page.goto("/tools/resume-builder");
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

test("Resume Builder switches among four layouts and exports the selected design", async ({
  page,
}) => {
  await page.goto("/tools/resume-builder");
  const preview = page.getByTestId("resume-preview");
  const classic = page.getByRole("radio", { name: /Classic/ });

  await expect(classic).toBeChecked();
  await expect(preview).toHaveAttribute("data-template", "classic");
  await page.getByLabel("Full name").fill("Ayesha Khan");
  await page.getByLabel("Email").fill("ayesha@example.com");
  await page.getByLabel("Job title").first().fill("Product Designer");
  await page.getByLabel("Company").first().fill("Design Studio");
  await page.getByRole("textbox", { name: "Technical skills" }).fill(
    "Research, Figma, Prototyping, Design Systems"
  );

  const templates = [
    { label: /Editorial/, id: "editorial", color: "F5D400" },
    { label: /Evergreen/, id: "evergreen", color: "285A1C" },
    { label: /Modern/, id: "modern", color: "216C98" },
  ];

  for (const template of templates) {
    await page.getByRole("radio", { name: template.label }).check();
    await expect(preview).toHaveAttribute("data-template", template.id);
    await expect(preview).toContainText("Ayesha Khan");
    await expect(preview).toContainText("Product Designer");
    await expect(preview).toContainText("Figma");

    const docxPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download Resume as DOCX" }).click();
    const docx = await docxPromise;
    if (template.id === "modern" && process.env.RESUME_TEMPLATE_DOCX_OUTPUT) {
      await docx.saveAs(process.env.RESUME_TEMPLATE_DOCX_OUTPUT);
    }
    const docxPath = await docx.path();
    expect(docxPath).toBeTruthy();
    const archive = await JSZip.loadAsync(await readFile(docxPath!));
    const documentXml = await archive.file("word/document.xml")!.async("string");
    expect(documentXml.toLowerCase()).toContain("ayesha khan");
    expect(documentXml.toLowerCase()).toContain("product designer");
    expect(documentXml.toLowerCase()).toContain("design studio");
    expect(documentXml).toContain(template.color);
  }

  const pdfPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Resume as PDF" }).click();
  const pdf = await pdfPromise;
  if (process.env.RESUME_TEMPLATE_PDF_OUTPUT) {
    await pdf.saveAs(process.env.RESUME_TEMPLATE_PDF_OUTPUT);
  }
  const pdfPath = await pdf.path();
  expect(pdfPath).toBeTruthy();
  const pdfBytes = await readFile(pdfPath!);
  expect(pdf.suggestedFilename()).toBe("ayesha-khan-resume.pdf");
  expect(pdfBytes.subarray(0, 4).toString()).toBe("%PDF");
  expect(pdfBytes.length).toBeGreaterThan(20_000);
  expect(pdfBytes.toString("latin1")).toContain("Ayesha Khan");

  await classic.check();
  await expect(preview).toHaveAttribute("data-template", "classic");
  await expect(page.getByLabel("Full name")).toHaveValue("Ayesha Khan");
});

test("Resume Builder scores the current form and highlights ATS improvements", async ({
  page,
}) => {
  await page.goto("/tools/resume-builder");
  await expect(page.getByText(/Build an ATS-standard resume/i)).toBeVisible();

  await page.getByLabel("Full name").fill("Ayesha Khan");
  await page.getByLabel("Email").fill("ayesha.khan@example.com");
  await page.getByLabel("Address").fill("Lahore, Punjab");
  await page.getByLabel("Phone").fill("+92 300 1234567");
  await page.getByLabel("University / school").first().fill("University of the Punjab");
  await page.getByLabel("Location").first().fill("Lahore");
  await page.getByLabel("Degree / programme").first().fill("BS Computer Science");
  await page.getByLabel("Graduation year").first().fill("2025");
  await page.getByLabel("Relevant coursework").first().fill("Machine Learning, Statistics");
  await page.getByLabel("Job title").first().fill("Data Analyst");
  await page.getByLabel("Company").first().fill("Example Analytics");
  await page.getByLabel("Employment dates").first().fill("Jan 2025 - Present");
  await page.getByLabel("Achievements (one bullet per line)").first().fill(
    [
      "Automated weekly reporting and reduced preparation time by 40%.",
      "Built 12 dashboards used by sales and operations teams.",
      "Analyzed customer data and improved campaign conversion by 18%.",
      "Collaborated with 4 departments to standardize KPI definitions.",
    ].join("\n")
  );
  await page.getByLabel("Project title").fill("Graduate demand forecasting");
  await page.getByLabel("Dates").first().fill("2024");
  await page.getByLabel("Description").first().fill("Forecasted monthly graduate hiring demand.");
  await page.getByLabel("Technologies used").fill("Python, Pandas, scikit-learn");
  await page.getByLabel("Outcome").fill("Improved validation accuracy by 15%.");
  await page.getByRole("textbox", { name: "Technical skills" }).fill(
    "Python, SQL, Power BI, Excel, statistics, data visualization"
  );

  await page.getByRole("button", { name: "Check Resume ATS Score" }).click();
  const result = page.getByTestId("ats-score-result");
  await expect(result).toBeVisible();
  await expect(result.getByText("ATS readiness")).toBeVisible();
  await expect(result.getByText("Highest-impact improvements")).toBeVisible();
  const scoreLabel = await result.locator(".ats-score-ring").getAttribute("aria-label");
  expect(scoreLabel).not.toBeNull();
  expect(Number(scoreLabel!.match(/\d+/)?.[0])).toBeGreaterThanOrEqual(85);

  await page.getByLabel("Full name").fill("Ayesha Noor Khan");
  await expect(result).toContainText("Resume changed since this check");
});

test("job listings use the canonical deadline without shifting to the previous day", async ({
  page,
}) => {
  await page.goto("/archive");
  const job = page.locator("article").filter({ hasText: "Nationwide Closed Role" });
  await job.hover();
  await expect(job.getByText("Deadline: Jul 17", { exact: true })).toBeVisible();
  await expect(job.getByText("Deadline: Jul 16", { exact: true })).toHaveCount(0);

  await page.goto("/jobs/closed-role");
  await expect(page.getByText("Deadline: 17 Jul 2026", { exact: true })).toBeVisible();
});
