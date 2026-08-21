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
    "/jobs-by-cities",
    "/jobs-by-provinces",
    "/jobs-by-categories",
    "/jobs-by-organizations",
    "/jobs-by-newspapers",
    "/newspapers/dawn",
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
    'href="/newspapers/dawn"',
    'href="/jobs-by-cities"',
    'href="/jobs-by-provinces"',
    'href="/jobs-by-categories"',
    'href="/jobs-by-organizations"',
    'href="/jobs-by-newspapers"',
    'href="/p/custom-seo-page"',
    'href="/resume-builder"',
    'href="/cover-letter"',
  ]) {
    expect(html).toContain(expected);
  }
  expect(html).toContain("max-h-[48rem]");
  expect(html).toContain("max-h-[42rem]");
});

test("homepage discovery section and every directory link resolve", async ({ page, request }) => {
  await page.goto("/");
  const discovery = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Find jobs your way" }),
  });
  for (const heading of [
    "Jobs by Cities",
    "Jobs by Provinces",
    "Jobs by Category",
    "Jobs by Organization",
    "Jobs by Newspaper",
  ]) {
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
  for (const label of [
    "More cities…",
    "More provinces…",
    "More categories…",
    "More organizations…",
    "More newspapers…",
  ]) {
    await expect(page.getByRole("link", { name: label })).toBeVisible();
  }
  await expect(discovery.locator("article")).toHaveCount(5);
  for (const card of await discovery.locator("article").all()) {
    await expect(card.locator("li > a")).toHaveCount(6);
  }
  await expect(
    discovery.getByRole("link", { name: "Jobs in Lahore", exact: true })
  ).toHaveAttribute("href", "/locations/lahore");
  await expect(
    discovery.getByRole("link", { name: "Jobs in The Nation", exact: true })
  ).toHaveCount(1);
  await expect(
    discovery.getByRole("link", { name: "Jobs in The Nation", exact: true })
  ).toHaveAttribute("href", "/newspapers/the-nation");

  const expectedDirectoryLinks: Record<string, string> = {
    "/jobs-by-cities": "/locations/lahore",
    "/jobs-by-provinces": "/locations/punjab",
    "/jobs-by-categories": "/categories/software-engineering",
    "/jobs-by-organizations": "/companies/fpsc",
    "/jobs-by-newspapers": "/newspapers/dawn",
  };
  for (const [directoryPath, expectedLink] of Object.entries(expectedDirectoryLinks)) {
    const response = await request.get(directoryPath);
    expect(response.status(), directoryPath).toBe(200);
    expect(await response.text()).toContain(`href="${expectedLink}"`);
  }

  for (const [path, content] of [
    ["/locations/lahore", "Managed content for Jobs in Lahore"],
    ["/newspapers/the-nation", "Managed content for Jobs in The Nation"],
  ] as const) {
    const response = await request.get(path);
    expect(response.status(), path).toBe(200);
    expect(await response.text()).toContain(content);
  }
});

test("all internal links emitted by the new discovery directories avoid 404s", async ({ request }) => {
  const sourcePages = [
    "/",
    "/jobs-by-cities",
    "/jobs-by-provinces",
    "/jobs-by-categories",
    "/jobs-by-organizations",
    "/jobs-by-newspapers",
  ];
  const links = new Set<string>();
  for (const sourcePath of sourcePages) {
    const response = await request.get(sourcePath);
    expect(response.status(), sourcePath).toBe(200);
    const html = await response.text();
    for (const match of html.matchAll(/href="([^"#]+)"/g)) {
      const url = new URL(match[1], "http://localhost:3000");
      if (url.origin === "http://localhost:3000") links.add(`${url.pathname}${url.search}`);
    }
  }
  for (const href of links) {
    const response = await request.get(href);
    expect(response.status(), href).not.toBe(404);
  }
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
    "Deadline:",
    "Required Education:",
    "Required Experience:",
    '"@type":"JobPosting"',
    '"datePosted":"2026-07-01T00:00:00Z"',
    '"industry":"Government"',
    '"skills":"Python, SQL"',
    '"educationRequirements":"Bachelor\'s degree"',
    '"experienceRequirements":"Two years"',
    '"hiringOrganization":{"@type":"Organization","name":"FPSC"}',
  ]) {
    expect(normalizedHtml).toContain(expected);
  }
  expect(normalizedHtml).not.toContain("h-96 animate-pulse");
});

test("homepage hover excludes descriptions and shows four optional facts in order", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.locator(".stat-card")).toHaveCount(5);
  await expect(page.locator(".stat-card").nth(2)).toContainText("1");
  await expect(page.locator(".stat-card").nth(2)).toContainText("Closed jobs");

  const completeCard = page.locator("article.job-card").filter({
    hasText: "Nationwide Closed Role",
  });
  await completeCard.hover();

  const overview = completeCard.locator(".job-card-expand");
  await expect(overview).toBeVisible();
  await expect(completeCard.locator(".job-card-overview-description")).toHaveCount(0);
  await expect(completeCard).not.toContainText("A nationwide job with a passed deadline.");
  await expect(overview.locator(".job-card-overview-detail")).toHaveText([
    "Newspaper: Dawn",
    "Required Education: Bachelor's degree",
    "Required Experience: Two years",
    "Deadline: Jul 17",
  ]);
  await expect(overview).not.toContainText("Published:");
  await expect(overview).not.toContainText("Source:");
  await expect(overview).not.toContainText("Category:");
  await expect(overview).not.toContainText("Skills:");
  await expect(overview).not.toContainText("Job reference");
  await expect(overview).not.toContainText("Apply here");

  const optionalCard = page.locator("article.job-card").filter({ hasText: "Multi Location Role" });
  await optionalCard.hover();
  await expect(optionalCard).not.toContainText("A role available in more than one city.");
  await expect(optionalCard.locator(".job-card-expand")).toHaveCount(0);
});

test("job listing cards stay metadata-only across every public directory", async ({ page }) => {
  const listingRoutes = [
    "/locations/lahore",
    "/locations/punjab",
    "/categories/software-engineering",
    "/tags/software-engineering",
    "/companies/fpsc",
    "/newspapers/dawn",
    "/qualifications/bachelors",
    "/browse",
  ];

  for (const route of listingRoutes) {
    await page.goto(route);
    const card = page.locator("article.job-card").filter({
      hasText: "Nationwide Closed Role",
    });
    await expect(card, route).toBeVisible();
    // Move away first because consecutive directory pages place the first card
    // at the same coordinates; otherwise the browser may not emit mouseenter
    // for the newly rendered card beneath an unchanged pointer.
    await page.locator("h1").hover();
    await card.hover();

    const overview = card.locator(".job-card-expand");
    await expect(overview, route).toBeVisible();
    await expect(card, route).not.toContainText(
      "A nationwide job with a passed deadline.",
    );
    await expect(card.locator(".job-card-overview-description"), route).toHaveCount(0);
    await expect(overview.locator(".job-card-overview-detail"), route).toHaveText([
      "Newspaper: Dawn",
      "Required Education: Bachelor's degree",
      "Required Experience: Two years",
      "Deadline: Jul 17",
    ]);
  }
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

test("double-encoded entities render as readable text in rich content", async ({ page }) => {
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
