import { expect, test } from "@playwright/test";

test("public pages expose self-canonicals and private pages are noindex", async ({ page }) => {
  test.setTimeout(90_000);
  for (const path of [
    "/",
    "/about",
    "/contact",
    "/privacy",
    "/disclaimer",
    "/blog",
    "/cover-letter",
    "/resume-builder",
    "/jobs/closed-role",
    "/tags/government",
    "/categories/software-engineering",
  ]) {
    await page.goto(path);
    const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
    expect(canonical).toBeTruthy();
    expect(new URL(canonical!).pathname).toBe(path);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
      "content",
      /^index,\s*follow/i
    );
  }

  await page.goto("/admin");
  await expect(page.locator('meta[name="robots"]').first()).toHaveAttribute(
    "content",
    /noindex.*nofollow/i
  );
});

test("published CMS pages have a real public route and canonical metadata", async ({ page }) => {
  await page.goto("/p/custom-seo-page");

  await expect(page.getByRole("heading", { name: "Custom public page" })).toBeVisible();
  await expect(page).toHaveTitle(/Custom SEO title/);
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    "content",
    "Custom SEO description for the published CMS page."
  );
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    /\/p\/custom-seo-page$/
  );
});

test("Browse All exposes every public content family in initial HTML", async ({ request }) => {
  const response = await request.get("/browse");
  expect(response.ok()).toBeTruthy();
  const html = await response.text();

  for (const expected of [
    "All job posts",
    "All career guides",
    "Job categories",
    "Cities",
    "Provinces",
    'href="/jobs/closed-role"',
    'href="/blog/fpsc-preparation-guide"',
    'href="/categories/software-engineering"',
    'href="/companies/fpsc"',
    'href="/locations/lahore"',
    'href="/locations/punjab"',
    'href="/p/custom-seo-page"',
    'href="/resume-builder"',
    'href="/cover-letter"',
  ]) {
    expect(html).toContain(expected);
  }
  expect(html).toContain("max-h-[48rem]");
  expect(html).toContain("max-h-[42rem]");
});

test("homepage exposes complete job listings in initial HTML without JavaScript", async ({
  request,
}) => {
  const response = await request.get("/", {
    headers: {
      "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    },
  });
  expect(response.ok()).toBeTruthy();
  const html = await response.text();
  const normalizedHtml = html.replace(/<!--[\s\S]*?-->/g, "");

  for (const expected of [
    'href="/jobs/closed-role"',
    "Nationwide Closed Role",
    "A nationwide job with a passed deadline.",
    "Published:",
    "Deadline:",
    "Source: FPSC",
    "Category: Government",
    "Exp: Two years",
    "Edu: Bachelor&#x27;s degree",
    "Skills: Python, SQL",
    'href="https://fpsc.gov.pk/advertisement"',
    'href="https://fpsc.gov.pk/apply"',
    "Job reference",
    "Apply here",
    '"@type":"JobPosting"',
  ]) {
    expect(normalizedHtml).toContain(expected);
  }
  expect(normalizedHtml).not.toContain("h-96 animate-pulse");
});

test("legacy job identifiers permanently resolve to the stable canonical slug", async ({ page }) => {
  const response = await page.goto("/jobs/legacy-closed-role-id");
  expect(response?.status()).toBe(200);
  await expect(page).toHaveURL(/\/jobs\/closed-role$/);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    /\/jobs\/closed-role$/
  );
});

test("JobPosting schema omits intentional blanks and never invents address or salary data", async ({
  page,
}) => {
  await page.goto("/jobs/multi-location-role");
  const multiLocation = await page.evaluate(() => {
    const scripts = Array.from(
      document.querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"]')
    );
    return scripts
      .map((script) => JSON.parse(script.textContent || "{}"))
      .find((value) => value["@type"] === "JobPosting");
  });

  expect(multiLocation).toBeTruthy();
  expect(multiLocation).not.toHaveProperty("baseSalary");
  expect(multiLocation).not.toHaveProperty("employmentType");
  expect(multiLocation).not.toHaveProperty("validThrough");
  expect(multiLocation).not.toHaveProperty("educationRequirements");
  expect(multiLocation).not.toHaveProperty("experienceRequirements");
  expect(multiLocation.jobLocation).toEqual([
    {
      "@type": "Place",
      address: {
        "@type": "PostalAddress",
        addressLocality: "Karachi",
        addressRegion: "Sindh",
        addressCountry: "PK",
      },
    },
    {
      "@type": "Place",
      address: {
        "@type": "PostalAddress",
        addressLocality: "Lahore",
        addressRegion: "Sindh",
        addressCountry: "PK",
      },
    },
  ]);
  expect(JSON.stringify(multiLocation)).not.toContain("streetAddress");
  expect(JSON.stringify(multiLocation)).not.toContain("postalCode");

  await page.goto("/jobs/closed-role");
  const nationwide = await page.evaluate(() => {
    const scripts = Array.from(
      document.querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"]')
    );
    return scripts
      .map((script) => JSON.parse(script.textContent || "{}"))
      .find((value) => value["@type"] === "JobPosting");
  });

  expect(nationwide.jobLocation).toEqual([
    {
      "@type": "Place",
      address: { "@type": "PostalAddress", addressCountry: "PK" },
    },
  ]);
  expect(nationwide).not.toHaveProperty("baseSalary");
});

test("double-encoded entities render as readable text in listings and rich content", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("body")).toContainText("Bachelor's qualification required.");
  await expect(page.locator("body")).not.toContainText("&#39;");

  await page.goto("/jobs/closed-role");
  await expect(page.locator(".prose-job")).toContainText("Candidate's experience matters.");
  await expect(page.locator(".prose-job")).not.toContainText("&#39;");
});

test("job and blog pages expose post-specific social previews", async ({ page }) => {
  await page.goto("/jobs/closed-role");

  await expect(page.locator('meta[property="og:title"]')).toHaveCount(1);
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute(
    "content",
    "Nationwide Closed Role"
  );
  await expect(page.locator('meta[property="og:description"]')).toHaveAttribute(
    "content",
    "Apply for the Nationwide Closed Role with FPSC."
  );
  await expect(page.locator('meta[property="og:url"]')).toHaveAttribute(
    "content",
    /\/jobs\/closed-role$/
  );
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
    "content",
    "http://127.0.0.1:4010/api/media/r2/job-portal/closed-role/images/notice.png"
  );
  await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute(
    "content",
    "summary_large_image"
  );
  await expect(page.locator('meta[name="twitter:title"]')).toHaveAttribute(
    "content",
    "Nationwide Closed Role"
  );

  await page.goto("/blog/fpsc-preparation-guide");

  await expect(page.locator('meta[property="og:title"]')).toHaveCount(1);
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute(
    "content",
    "FPSC Preparation Guide"
  );
  await expect(page.locator('meta[property="og:url"]')).toHaveAttribute(
    "content",
    /\/blog\/fpsc-preparation-guide$/
  );
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
    "content",
    "https://files.pakistanjobsmarket.com/blog/fpsc-preparation.png"
  );
  await expect(page.locator('meta[name="twitter:title"]')).toHaveAttribute(
    "content",
    "FPSC Preparation Guide"
  );
});

test("sitemap advertises canonical content URLs and the legacy favicon resolves", async ({
  request,
}) => {
  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.ok()).toBeTruthy();
  const xml = await sitemap.text();

  expect(xml).toContain("<loc>http://localhost:3000/disclaimer</loc>");
  expect(xml).toContain("<loc>http://localhost:3000/cover-letter</loc>");
  expect(xml).toContain("<loc>http://localhost:3000/jobs/closed-role</loc>");
  expect(xml).toContain("<loc>http://localhost:3000/blog/fpsc-preparation-guide</loc>");
  expect(xml).toContain("<loc>http://localhost:3000/p/custom-seo-page</loc>");
  const locations = Array.from(xml.matchAll(/<loc>([^<]+)<\/loc>/g), (match) => match[1]);
  expect(locations.length).toBeGreaterThan(0);
  expect(locations.every((location) => new URL(location).hostname === "localhost")).toBeTruthy();

  const favicon = await request.get("/favicon.ico");
  expect(favicon.ok()).toBeTruthy();
  expect(favicon.headers()["content-type"]).toMatch(/^image\//);
  expect((await favicon.body()).byteLength).toBeGreaterThan(0);
});
