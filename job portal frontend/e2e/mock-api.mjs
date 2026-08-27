import { createServer } from "node:http";

const mockSiteOrigin = (process.env.MOCK_SITE_ORIGIN || "http://localhost:3000").replace(/\/$/, "");

const directoryPageValues = {
  city: ["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Peshawar", "Quetta"],
  province: ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Islamabad Capital Territory", "Gilgit-Baltistan"],
  category: ["Software Engineering", "Accounting", "Education", "Engineering", "Healthcare", "Marketing"],
  organization: ["FPSC", "NADRA", "PPSC", "NTS", "Pakistan Army", "Ministry of Education"],
  newspaper: ["Daily Jang", "Dawn", "Express", "Nawa-i-Waqt", "The Nation", "The News"],
};

const slugify = (value) => value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
const directoryPages = Object.entries(directoryPageValues).flatMap(([pageType, values]) =>
  values.map((taxonomyValue) => {
    const slug = slugify(taxonomyValue);
    const title = ["city", "province", "newspaper"].includes(pageType)
      ? `Jobs in ${taxonomyValue}`
      : `${taxonomyValue} Jobs`;
    return {
      id: `${pageType}-${slug}`,
      slug,
      title,
      content: `<p>Managed content for ${title}.</p>`,
      page_type: pageType,
      taxonomy_value: taxonomyValue,
      is_published: true,
    };
  }),
);

const taxonomyTerms = [
  { id: "term-software", kind: "category", name: "Software Engineering", slug: "software-engineering", is_active: true },
  { id: "term-education", kind: "category", name: "Education", slug: "education", is_active: true },
  { id: "city-lahore", kind: "city", name: "Lahore", slug: "lahore", is_active: true },
  { id: "city-karachi", kind: "city", name: "Karachi", slug: "karachi", is_active: true },
];

const toolCategories = [
  {
    id: "tool-category-tax", slug: "tax-salary-tools", title: "Tax & Salary Tools",
    content: "<p>Practical calculators for Pakistan salary and tax planning.</p>", icon_key: "coins",
    color_index: 1, sort_order: 0, is_published: true,
    tools: [{ id: "tool-tax", category_id: "tool-category-tax", slug: "pakistan-tax-calculator", title: "Pakistan Tax Calculator", content: "<p>Estimate salary tax.</p>", tool_kind: "tax_calculator", sort_order: 0, is_published: true }],
  },
  {
    id: "tool-category-students", slug: "tools-for-students", title: "Tools for Students",
    content: "<p>Student calculators.</p>", icon_key: "graduation", color_index: 2, sort_order: 1, is_published: true,
    tools: [{ id: "tool-cgpa", category_id: "tool-category-students", slug: "cgpa-calculator", title: "CGPA Calculator", content: "<p>Calculate CGPA.</p>", tool_kind: "cgpa_calculator", sort_order: 0, is_published: true }],
  },
  { id: "tool-category-images", slug: "image-editing-tools", title: "Image Editing Tools", content: "", icon_key: "image", color_index: 3, sort_order: 2, is_published: true, tools: [] },
  {
    id: "tool-category-documents", slug: "document-tools", title: "Document Tools", content: "", icon_key: "document", color_index: 4, sort_order: 3, is_published: true,
    tools: [{ id: "tool-converter", category_id: "tool-category-documents", slug: "docx-pdf-converter", title: "DOCX and PDF Converter", content: "<p>Convert documents.</p>", tool_kind: "document_converter", sort_order: 0, is_published: true }],
  },
];
const toolPages = toolCategories.flatMap((category) => category.tools);

const adminJobs = Array.from({ length: 53 }, (_, index) => {
  const number = index + 1;
  const suffix = String(number).padStart(2, "0");
  return {
    id: `admin-job-${suffix}`,
    slug: `admin-job-${suffix}`,
    title: `Editable Job Post ${suffix}`,
    description: "Admin pagination test job.",
    published_date: `2026-08-${String(21 - (index % 20)).padStart(2, "0")}T00:00:00Z`,
    deadline_date: null,
    job_type: number % 2 ? "government" : "private",
    source_type: number % 2 ? "govt" : "private",
    source: "Test Organization",
    cities: [number % 2 ? "Lahore" : "Karachi"],
    provinces: [],
    tags: [],
    skills: [],
    applications_closed: false,
  };
});

const json = (response, value, status = 200) => {
  response.writeHead(status, {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Conversion-Token",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Content-Type": "application/json",
  });
  response.end(JSON.stringify(value));
};

const readJson = async (request) => {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {};
};

const server = createServer(async (request, response) => {
  if (request.method === "OPTIONS") return json(response, {});
  const requestUrl = new URL(request.url || "/", "http://127.0.0.1:4010");
  const path = requestUrl.pathname;
  const authorization = request.headers.authorization || "";
  if (path.startsWith("/api/admin/blog") && authorization === "Bearer expired-e2e-token") {
    return json(response, { detail: "Invalid token" }, 401);
  }
  if (path.startsWith("/api/media/r2/")) {
    const onePixelPng = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      "base64",
    );
    response.writeHead(200, {
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=31536000, immutable",
      "Content-Type": "image/png",
    });
    response.end(onePixelPng);
    return;
  }
  if (path === "/ready") return json(response, { status: "ready" });
  if (path === "/api/auth/login" && request.method === "POST") {
    return json(response, { access_token: "e2e-token", username: "e2e-admin" });
  }
  if (path === "/api/settings/branding") {
    return json(response, {
      site_name: "Pakistan Jobs Market",
      site_title: "Pakistan Jobs Market",
      site_title_alignment: "center",
      site_title_header: "Pakistan Jobs Market",
      site_header: "Latest government & private job openings in Pakistan",
      site_description: "Discover current government and private jobs across Pakistan, search opportunities by city and category, get instant job alerts, and use practical career tools.",
      footer_copyright: "Copyrights © {year} - Pakistan Jobs Market. All rights reserved.",
      homepage_focus_keyword: "jobs in Pakistan",
      homepage_meta_title: "Jobs in Pakistan 2026 | Pakistan Jobs Market",
      homepage_meta_description: "Find latest government and private jobs in Pakistan by city and category. Explore curated listings, deadlines, job alerts, resume tools and career guides.",
      homepage_meta_keywords: "jobs in Pakistan, latest jobs in Pakistan, government jobs Pakistan, private jobs Pakistan, newspaper jobs, FPSC jobs, PPSC jobs, jobs by city, Pakistan Jobs Market",
      logo_url: "/pakistan-jobs-market-logo.png",
    });
  }
  if (path === "/api/admin/tools") {
    return json(response, { categories: toolCategories, tools: toolPages });
  }
  if (path === "/api/tools") return json(response, toolCategories);
  if (path === "/api/tools/document-converter/jobs" && request.method === "POST") {
    return json(response, {
      job_id: "e2e-conversion",
      access_token: "e2e-conversion-token",
      status: "queued",
      progress: 25,
      stage: "Queued securely",
      input_format: "pdf",
      output_format: "docx",
      output_filename: "sample.docx",
      estimated_seconds_remaining: 2,
      error: null,
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 900_000).toISOString(),
    }, 202);
  }
  if (path === "/api/tools/document-converter/jobs/e2e-conversion/download") {
    response.writeHead(200, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "X-Conversion-Token",
      "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Content-Disposition": 'attachment; filename="sample.docx"',
    });
    response.end(Buffer.from("mock converted document"));
    return;
  }
  if (path === "/api/tools/document-converter/jobs/e2e-conversion") {
    return json(response, {
      job_id: "e2e-conversion",
      status: "completed",
      progress: 100,
      stage: "Ready to download",
      input_format: "pdf",
      output_format: "docx",
      output_filename: "sample.docx",
      estimated_seconds_remaining: 0,
      error: null,
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 900_000).toISOString(),
    });
  }
  if (path.startsWith("/api/tools/categories/")) {
    const slug = path.split("/").pop();
    const category = toolCategories.find((item) => item.slug === slug);
    return category ? json(response, category) : json(response, { detail: "Tool category not found" }, 404);
  }
  if (path.startsWith("/api/tools/")) {
    const slug = path.split("/").pop();
    const tool = toolPages.find((item) => item.slug === slug);
    return tool ? json(response, tool) : json(response, { detail: "Tool not found" }, 404);
  }
  if (path.startsWith("/api/seo/tool_category/") || path.startsWith("/api/seo/tool/")) {
    return json(response, { meta_title: null, meta_description: null, meta_keywords: null });
  }
  if (path === "/api/admin/settings/branding" && request.method === "PUT") {
    return json(response, {
      site_name: "Pakistan Jobs Market",
      site_title: "Pakistan Jobs Market",
      site_title_alignment: "beside_logo",
      site_title_header: "Pakistan Jobs Market",
      site_header: "Latest government & private job openings in Pakistan",
      site_description: "Discover current government and private jobs across Pakistan, search opportunities by city and category, get instant job alerts, and use practical career tools.",
      footer_copyright: "Copyrights © {year} - Pakistan Jobs Market. All rights reserved.",
      homepage_focus_keyword: "jobs in Pakistan",
      homepage_meta_title: "Jobs in Pakistan 2026 | Pakistan Jobs Market",
      homepage_meta_description: "Find latest government and private jobs in Pakistan by city and category. Explore curated listings, deadlines, job alerts, resume tools and career guides.",
      homepage_meta_keywords: "jobs in Pakistan, latest jobs in Pakistan, government jobs Pakistan, private jobs Pakistan, newspaper jobs, FPSC jobs, PPSC jobs, jobs by city, Pakistan Jobs Market",
      logo_url: "/pakistan-jobs-market-logo.png",
    });
  }
  if (path === "/api/settings/social" || path === "/api/admin/seo/social") {
    return json(response, {
      facebook_url: "https://facebook.com/pakistanjobsmarket",
      youtube_url: "",
      x_url: "",
      linkedin_url: "https://linkedin.com/company/pakistanjobsmarket",
    });
  }
  if (path === "/api/admin/upload") {
    return json(response, {
      id: null,
      public_url: "https://files.pakistanjobsmarket.com/job-portal/pasted/images/clipboard.png",
      file_type: "image/png",
      file_size: 68,
      original_name: "clipboard.png",
      is_inline_image: true,
      s3_path: "job-portal/pasted/images/clipboard.png",
    });
  }
  if (path === "/api/filters") {
    return json(response, {
      source_types: [], sectors: ["govt", "private"],
      categories: ["Software Engineering", "Accounting", "Education", "Engineering", "Healthcare", "Marketing"],
      cities: ["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Peshawar", "Quetta"],
      provinces: ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Islamabad Capital Territory", "Gilgit-Baltistan"],
      companies: ["FPSC", "NADRA", "PPSC", "NTS", "Pakistan Army", "Ministry of Education"],
      newspapers: ["Daily Jang", "Dawn", "Express", "Nawa-i-Waqt", "The Nation", "The News"],
      employment_types: [], tags: ["Software Engineering"], job_types: ["government", "private"],
    });
  }
  if (path === "/api/sitemap-data") {
    return json(response, {
      urls: [
        { loc: `${mockSiteOrigin}/jobs/closed-role`, changefreq: "weekly", priority: 0.8 },
        { loc: `${mockSiteOrigin}/jobs/multi-location-role`, changefreq: "weekly", priority: 0.8 },
        { loc: `${mockSiteOrigin}/blog/fpsc-preparation-guide`, changefreq: "weekly", priority: 0.7 },
        { loc: `${mockSiteOrigin}/p/custom-seo-page`, changefreq: "monthly", priority: 0.5 },
        { loc: `${mockSiteOrigin}/categories/software-engineering`, changefreq: "weekly", priority: 0.6 },
        { loc: `${mockSiteOrigin}/tags/government`, changefreq: "weekly", priority: 0.5 },
        { loc: `${mockSiteOrigin}/locations/lahore`, changefreq: "weekly", priority: 0.6 },
        { loc: `${mockSiteOrigin}/locations/punjab`, changefreq: "weekly", priority: 0.6 },
        { loc: `${mockSiteOrigin}/companies/fpsc`, changefreq: "weekly", priority: 0.6 },
        { loc: `${mockSiteOrigin}/newspapers/dawn`, changefreq: "weekly", priority: 0.6 },
        { loc: `${mockSiteOrigin}/qualifications/bachelors`, changefreq: "weekly", priority: 0.5 },
        { loc: `${mockSiteOrigin}/blog/categories/career-advice`, changefreq: "weekly", priority: 0.5 },
        { loc: `${mockSiteOrigin}/blog/tags/fpsc`, changefreq: "weekly", priority: 0.4 },
      ],
    });
  }
  if (path === "/api/site-directory") {
    return json(response, {
      generated_at: new Date().toISOString(),
      jobs: [
        {
          id: "closed-role", slug: "closed-role", title: "Nationwide Closed Role",
          published_date: "2026-07-01T00:00:00Z", deadline_date: "2026-07-17T00:00:00Z",
          applications_closed: true, organization: "FPSC", newspaper: "Dawn", category: "Government",
          salary_range: null, education_required: "Bachelor's degree",
          experience_required: "Two years", job_type: "government",
          cities: ["Karachi", "Lahore"], provinces: ["Sindh"], tags: ["Government"],
        },
        {
          id: "multi-location-role", slug: "multi-location-role", title: "Multi Location Role",
          published_date: "2026-07-02T00:00:00Z", deadline_date: null,
          applications_closed: false, organization: "FPSC", newspaper: "", category: "Software Engineering",
          salary_range: null, education_required: null,
          experience_required: null, job_type: "government",
          cities: ["Karachi", "Lahore"], provinces: ["Punjab", "Sindh"], tags: ["Software Engineering"],
        },
      ],
      blogs: [{
        id: "blog-1", slug: "fpsc-preparation-guide", title: "FPSC Preparation Guide",
        published_at: "2026-07-18T12:00:00Z", category: "Career Advice",
        tags: ["FPSC", "Exam Preparation"],
      }],
      pages: [
        { id: "about", slug: "about", title: "About Us", path: "/about" },
        { id: "custom-seo-page-id", slug: "custom-seo-page", title: "Custom public page", path: "/p/custom-seo-page" },
      ],
      taxonomies: {
        job_categories: [
          { name: "Government", slug: "government", count: 1 },
          { name: "Software Engineering", slug: "software-engineering", count: 1 },
        ],
        job_tags: [{ name: "Government", slug: "government", count: 1 }],
        cities: [{ name: "Lahore", slug: "lahore", count: 2 }],
        provinces: [{ name: "Punjab", slug: "punjab", count: 1 }],
        organizations: [{ name: "FPSC", slug: "fpsc", count: 2 }],
        newspapers: [{ name: "Dawn", slug: "dawn", count: 1 }],
        qualifications: [{ name: "Bachelors", slug: "bachelors", count: 1 }],
        blog_categories: [{ name: "Career Advice", slug: "career-advice", count: 1 }],
        blog_tags: [{ name: "FPSC", slug: "fpsc", count: 1 }],
      },
    });
  }
  if (["/api/taxonomy", "/api/admin/taxonomy", "/api/cities", "/api/admin/cities"].includes(path) && request.method === "GET") {
    const kind = path.endsWith("cities") ? "city" : "category";
    return json(
      response,
      taxonomyTerms.filter((term) => term.kind === kind && (path.startsWith("/api/admin/") || term.is_active)),
    );
  }
  if (path === "/api/admin/taxonomy" && request.method === "POST") {
    const payload = await readJson(request);
    const name = String(payload.name || "").trim();
    const created = {
      id: `term-${payload.kind || "category"}-${slugify(name)}`,
      kind: payload.kind || "category",
      name,
      slug: slugify(payload.slug || name),
      is_active: payload.is_active !== false,
    };
    taxonomyTerms.push(created);
    return json(response, created);
  }
  if (path.startsWith("/api/admin/taxonomy/")) {
    const id = path.split("/").pop();
    const index = taxonomyTerms.findIndex((term) => term.id === id);
    if (index < 0) return json(response, { detail: "Taxonomy term not found" }, 404);
    if (request.method === "DELETE") {
      taxonomyTerms.splice(index, 1);
      return json(response, { ok: true, id });
    }
    if (request.method === "PUT") {
      const payload = await readJson(request);
      taxonomyTerms[index] = { ...taxonomyTerms[index], ...payload };
      return json(response, taxonomyTerms[index]);
    }
  }
  if (path === "/api/subscriptions") {
    return json(response, { ok: true, status: "subscribed", message: "Your email has been subscribed to new job alerts." });
  }
  if (path === "/api/subscriptions/unsubscribe") {
    return json(response, { ok: true, status: "unsubscribed", message: "You have been unsubscribed." });
  }
  if (path === "/api/admin/subscriptions") {
    return json(response, {
      subscriber_count: 7, active_subscriber_count: 6,
      subject_template: "New Job Alert: {job_title} — {site_title}",
      body_template: "Dear Sir/Madam, a new job was published on {site_title}.",
      last_digest_at: null, last_digest_status: null,
      last_digest_job_id: null, last_digest_job_title: null,
      last_digest_recipients_count: 0, last_digest_sent_count: 0,
      last_digest_failed_count: 0, last_digest_error: null,
      delivery_provider: "resend", delivery_ready: true,
      delivery_configuration_message: "Resend HTTPS delivery is configured.",
    });
  }
  if (path === "/api/admin/subscriptions/template") {
    return json(response, {
      subscriber_count: 7, active_subscriber_count: 6,
      subject_template: "Saved subject", body_template: "Saved body",
      last_digest_at: null, last_digest_status: null,
      last_digest_job_id: null, last_digest_job_title: null,
      last_digest_recipients_count: 0, last_digest_sent_count: 0,
      last_digest_failed_count: 0, last_digest_error: null,
      delivery_provider: "resend", delivery_ready: true,
      delivery_configuration_message: "Resend HTTPS delivery is configured.",
    });
  }
  if (path === "/api/jobs") {
    return json(response, { items: [{
      id: "closed-role", slug: "closed-role", title: "Nationwide Closed Role",
      description: "A nationwide job with a passed deadline. Bachelor&amp;#39;s qualification required.", published_date: "2026-07-01T00:00:00Z",
      // Canonical deadline_date must win over the legacy alias. The alias
      // deliberately represents the previous UTC day to guard the Pakistan
      // timezone regression reported in production.
      deadline_date: "2026-07-17T00:00:00", application_deadline: "2026-07-16T19:00:00Z",
      salary_range: null, source: "FPSC", newspaper: "Dawn", reference_url: "https://fpsc.gov.pk/advertisement", application_url: "https://fpsc.gov.pk/apply",
      experience_required: "Two years", education_required: "Bachelor's degree", skills: ["Python", "SQL"], job_type: "government",
      cities: ["Karachi", "Lahore"], provinces: ["Sindh"], tags: ["Government"], keywords: null, created_at: "2026-07-01T00:00:00Z",
      company: "FPSC", location: "Pakistan", city: "Pakistan", province: null, employment_type: null,
      salary_min: null, salary_max: null, currency: "PKR", category: "Government",
      source_type: "govt", source_name: "FPSC", nationwide: true, applications_closed: true,
    }, {
      id: "multi-location-role", slug: "multi-location-role", title: "Multi Location Role",
      description: "A role available in more than one city.", published_date: "2026-07-02T00:00:00Z",
      deadline_date: null, application_deadline: null, salary_range: null, source: "FPSC", newspaper: "",
      reference_url: null, application_url: null, experience_required: null,
      education_required: null, skills: [], job_type: "government",
      cities: ["Karachi", "Lahore"], provinces: ["Sindh"], tags: ["Government"],
      keywords: null, created_at: "2026-07-02T00:00:00Z", company: "FPSC",
      location: "Sindh, Karachi, Lahore", city: "Karachi", province: "Sindh",
      employment_type: null, salary_min: null, salary_max: null, currency: "PKR",
      category: "Government", source_type: "govt", source_name: "FPSC",
      nationwide: false, applications_closed: false,
    }], total: 2, page: 1, page_size: 30, pages: 1 });
  }
  if (path === "/api/admin/jobs" && request.method === "GET") {
    const page = Math.max(1, Number(requestUrl.searchParams.get("page") || 1));
    const pageSize = Math.max(1, Number(requestUrl.searchParams.get("page_size") || 25));
    const start = (page - 1) * pageSize;
    return json(response, {
      items: adminJobs.slice(start, start + pageSize),
      total: adminJobs.length,
      page,
      page_size: pageSize,
      pages: Math.ceil(adminJobs.length / pageSize),
    });
  }
  if (path === "/api/stats") {
    return json(response, { total_jobs: 1, open_for_apply: 0, by_source_type: { govt: 1 }, by_category: { Government: 1 }, by_city: { Pakistan: 1 }, by_job_type: { government: 1 }, last_updated: new Date().toISOString() });
  }
  if (path === "/api/admin/jobs/closed-role/fetch-qna" && request.method === "POST") {
    return json(response, {
      items: [
        {
          id: "qna-e2e-1",
          job_id: "closed-role",
          question: "What is the written-test format?",
          answer: "The written test begins with an MCQ stage.",
          source: "mixed",
          youtube_url: "https://www.youtube.com/watch?v=qna-e2e-video",
          youtube_title: "FPSC written test preparation",
        },
      ],
      count: 1,
      elapsed_seconds: 4.2,
      error: null,
      videos_compared: 5,
      videos_scanned: 1,
      matched_videos: [{
        title: "FPSC written test preparation",
        url: "https://www.youtube.com/watch?v=qna-e2e-video",
        similarity_percent: 91.4,
        has_transcript: true,
        comment_threads: 12,
      }],
    });
  }
  if (path === "/api/jobs/closed-role" || path === "/api/jobs/legacy-closed-role-id") {
    return json(response, {
      id: "closed-role", slug: "closed-role", title: "Nationwide Closed Role",
      description: '<h2><span style="background-color:rgb(255,255,255);color:rgb(0,0,0)">Role overview</span></h2><p>Candidate&amp;#39;s experience matters.</p><p>https://example.com/this-is-a-deliberately-long-reference-that-must-wrap-inside-the-job-description-on-small-screens</p><ol><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Build resilient pipelines</li><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Monitor platform performance</li></ol><ul><li>Standard HTML bullet</li></ul><table><tbody><tr><td><strong>Job ID</strong></td><td><strong>Position</strong></td></tr><tr><td>PDA-J0149</td><td>Recruitment Manager</td></tr><tr><td>PDA-J0150</td><td>AI Associate</td></tr></tbody></table><img alt="R2 job image" src="https://files.pakistanjobsmarket.com/job-portal/closed-role/images/notice.png">', published_date: "2026-07-01T00:00:00Z",
      deadline_date: "2026-07-17T00:00:00", application_deadline: "2026-07-16T19:00:00Z",
      salary_range: null, source: "FPSC", newspaper: "Dawn", reference_url: "https://fpsc.gov.pk/advertisement", application_url: "https://fpsc.gov.pk/apply",
      experience_required: null, education_required: null, skills: [], job_type: "government",
      cities: ["Karachi", "Lahore"], provinces: ["Sindh"], tags: ["Government"], keywords: null, created_at: "2026-07-01T00:00:00Z",
      company: "FPSC", location: "Pakistan", city: "Pakistan", province: null, employment_type: null,
      salary_min: null, salary_max: null, currency: "PKR", category: "Government",
      source_type: "govt", source_name: "FPSC", nationwide: true, applications_closed: true,
      application_email: null, source_url: null, attachments: [], qna: [], resources: [],
    });
  }
  if (path === "/api/seo/job/closed-role") {
    return json(response, {
      meta_title: "Nationwide Closed Role | Pakistan Jobs Market",
      meta_description: "Apply for the Nationwide Closed Role with FPSC.",
      meta_keywords: "Nationwide Closed Role, FPSC jobs",
      og_title: "Nationwide Closed Role",
      og_description: "Apply for the Nationwide Closed Role with FPSC.",
      og_image: null,
    });
  }
  if (path === "/api/jobs/multi-location-role") {
    return json(response, {
      id: "multi-location-role", slug: "multi-location-role", title: "Multi Location Role",
      description: '<h2><span style="background-color:rgb(255,255,255);color:rgb(0,0,0)">Role overview</span></h2><p>Candidate&amp;#39;s experience matters.</p><p>https://example.com/this-is-a-deliberately-long-reference-that-must-wrap-inside-the-job-description-on-small-screens</p><ol><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Build resilient pipelines</li><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Monitor platform performance</li></ol><ul><li>Standard HTML bullet</li></ul><table><tbody><tr><td><strong>Job ID</strong></td><td><strong>Position</strong></td></tr><tr><td>PDA-J0149</td><td>Recruitment Manager</td></tr><tr><td>PDA-J0150</td><td>AI Associate</td></tr></tbody></table><img alt="R2 job image" src="https://files.pakistanjobsmarket.com/job-portal/closed-role/images/notice.png">',
      published_date: "2026-07-01T00:00:00Z", deadline_date: null, application_deadline: null,
      salary_range: null, source: "FPSC", newspaper: "", reference_url: null, application_url: null,
      experience_required: null, education_required: null, skills: [], job_type: "government",
      cities: ["Karachi", "Lahore"], provinces: ["Sindh"], tags: ["Government"],
      keywords: null, created_at: "2026-07-01T00:00:00Z", company: "FPSC",
      location: "Sindh, Karachi, Lahore", city: "Karachi", province: "Sindh",
      employment_type: null, salary_min: null, salary_max: null, currency: "PKR",
      category: "Government", source_type: "govt", source_name: "FPSC",
      nationwide: false, applications_closed: false, application_email: null,
      source_url: null, attachments: [], qna: [], resources: [],
    });
  }
  const blogPost = {
    id: "blog-1", slug: "fpsc-preparation-guide", title: "FPSC Preparation Guide",
    excerpt: "A practical preparation guide for candidates in Pakistan.",
    content: "<h2>Build a study plan</h2><p><span data-testid=\"pasted-rich-text\" style=\"background-color: rgb(255, 255, 255); color: rgb(0, 0, 0)\">Use the syllabus and practice consistently.</span></p><img alt=\"FPSC preparation\" src=\"https://files.pakistanjobsmarket.com/blog/fpsc-preparation.png\"><p>https://example.com/this-is-a-deliberately-very-long-reference-that-must-wrap-inside-the-article-instead-of-being-cut-off-on-the-right-side</p><table style=\"width:1600px\"><thead><tr><th>Exam stage</th><th>Preparation focus</th></tr></thead><tbody><tr><td>Screening test</td><td>Past papers and the official syllabus</td></tr><tr><td>Interview</td><td>Role knowledge and current affairs</td></tr></tbody></table>",
    author: "Pakistan Jobs Market Editorial Team", category: "Career Advice",
    tags: ["FPSC", "Exam Preparation"], is_published: true,
    published_at: "2026-07-18T12:00:00Z", created_at: "2026-07-18T12:00:00Z",
    updated_at: "2026-07-18T12:00:00Z",
  };
  if (path === "/api/blog") return json(response, { items: [blogPost], total: 1, page: 1, page_size: 12, pages: 1 });
  if (path === "/api/blog/filters") return json(response, { categories: ["Career Advice"], tags: ["FPSC", "Exam Preparation"] });
  if (path === "/api/blog/fpsc-preparation-guide") return json(response, blogPost);
  if (path === "/api/admin/blog") return json(response, { items: [blogPost], total: 1, page: 1, page_size: 25, pages: 1 });
  if (path === "/api/admin/blog/blog-1" && request.method === "PUT") {
    return json(response, { ...blogPost, updated_at: new Date().toISOString() });
  }
  if (path === "/api/admin/blog/blog-1") return json(response, blogPost);
  if (path === "/api/seo/blog/blog-1") return json(response, { entity_type: "blog", entity_id: "blog-1", focus_keyword: "FPSC preparation", meta_title: "FPSC Preparation Guide", meta_description: blogPost.excerpt, meta_keywords: "FPSC, exam preparation" });
  if (path === "/api/admin/seo/yoast/analyze") return json(response, { seo_score: 82, readability_score: 78, seo_status: "good", readability_status: "good", word_count: 10, checks: [], snippet: { title: "FPSC Preparation Guide", description: blogPost.excerpt, url: "/blog/fpsc-preparation-guide" } });
  if (path === "/api/admin/pages") {
    return json(response, [
      { id: "about", slug: "about", title: "About Us", content: "<p>About</p>", page_type: "standard", taxonomy_value: null, is_published: true },
      { id: "contact", slug: "contact", title: "Contact Us", content: "<p>Contact</p>", page_type: "standard", taxonomy_value: null, is_published: true },
      { id: "privacy", slug: "privacy", title: "Privacy Policy", content: "<p>Privacy</p>", page_type: "standard", taxonomy_value: null, is_published: true },
      { id: "disclaimer", slug: "disclaimer", title: "Disclaimer", content: "<p>Disclaimer</p>", page_type: "standard", taxonomy_value: null, is_published: true },
      { id: "jobs-by-cities", slug: "jobs-by-cities", title: "Jobs by Cities", content: "<p>Browse jobs by city.</p>", page_type: "standard", taxonomy_value: null, is_published: true },
      { id: "jobs-by-provinces", slug: "jobs-by-provinces", title: "Jobs by Provinces", content: "<p>Browse jobs by province.</p>", page_type: "standard", taxonomy_value: null, is_published: true },
      { id: "jobs-by-categories", slug: "jobs-by-categories", title: "Jobs by Category", content: "<p>Browse jobs by category.</p>", page_type: "standard", taxonomy_value: null, is_published: true },
      { id: "jobs-by-organizations", slug: "jobs-by-organizations", title: "Jobs by Organization", content: "<p>Browse jobs by organization.</p>", page_type: "standard", taxonomy_value: null, is_published: true },
      { id: "jobs-by-newspapers", slug: "jobs-by-newspapers", title: "Jobs by Newspaper", content: "<p>Browse jobs by newspaper.</p>", page_type: "standard", taxonomy_value: null, is_published: true },
      ...directoryPages,
    ]);
  }
  if (path === "/api/pages/directory-links") {
    return json(response, directoryPages.map((page) => ({
      id: page.id,
      slug: page.slug,
      title: page.title,
      page_type: page.page_type,
      taxonomy_value: page.taxonomy_value,
    })));
  }
  if (path.startsWith("/api/pages/directory/")) {
    const [, , , , requestedType, requestedSlug] = path.split("/");
    const page = directoryPages.find((entry) =>
      entry.slug === requestedSlug &&
      (requestedType === "location"
        ? ["city", "province"].includes(entry.page_type)
        : entry.page_type === requestedType),
    );
    return page ? json(response, page) : json(response, { detail: "Directory page not found" }, 404);
  }
  if (path.startsWith("/api/pages/jobs-by-")) {
    const slug = path.split("/").pop();
    const title = slug.split("-").slice(2).join(" ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    return json(response, { id: slug, slug, title: `Jobs by ${title}`, content: `<p>Browse jobs by ${title.toLowerCase()}.</p>`, page_type: "standard", taxonomy_value: null, is_published: true });
  }
  if (path === "/api/pages/custom-seo-page") {
    return json(response, {
      id: "custom-seo-page-id",
      slug: "custom-seo-page",
      title: "Custom public page",
      content: "<p>A published CMS page that is safe for search indexing.</p>",
      page_type: "standard",
      taxonomy_value: null,
      is_published: true,
      created_at: "2026-07-28T00:00:00Z",
      updated_at: "2026-07-28T00:00:00Z",
    });
  }
  if (path === "/api/seo/page/custom-seo-page-id") {
    return json(response, {
      meta_title: "Custom SEO title",
      meta_description: "Custom SEO description for the published CMS page.",
      meta_keywords: "custom page, Pakistan jobs",
      og_title: "Custom social title",
      og_description: "Custom social description.",
      og_image: null,
    });
  }
  if (path === "/api/admin/contact") return json(response, []);
  if (path === "/api/admin/analytics/realtime") {
    return json(response, {
      window_minutes: 5, active_visitors: 3, page_views: 3,
      generated_at: new Date().toISOString(), pages: [], locations: [
        { country: "Pakistan", region: "Punjab", city: "Lahore", visitors: 2, last_seen: new Date().toISOString() },
        { country: "United States", region: "Oregon", city: "Boardman", visitors: 1, last_seen: new Date().toISOString() },
      ],
    });
  }
  if (path === "/api/admin/analytics") {
    return json(response, {
      month: new Date().toISOString().slice(0, 7), unique_visitors: 3,
      timezone: "Asia/Karachi", generated_at: new Date().toISOString(),
      page_views: 3, daily: [], locations: [
        { country: "Pakistan", region: "Punjab", city: "Lahore", visitors: 2, page_views: 2 },
        { country: "United States", region: "Oregon", city: "Boardman", visitors: 1, page_views: 1 },
      ],
    });
  }
  if (path === "/api/admin/infrastructure") {
    return json(response, {
      collected_at: new Date().toISOString(), refresh_after_seconds: 30,
      storage: [
        { id: "r2", name: "Object storage", provider: "Cloudflare R2", used_bytes: 1048576, total_bytes: 10737418240, utilization_percent: 0.01, object_count: 12, status: "healthy", source: "mock", detail: "R2 test usage." },
        { id: "database", name: "Database storage", provider: "Azure PostgreSQL", used_bytes: 2097152, total_bytes: 34359738368, utilization_percent: 0.01, object_count: null, status: "healthy", source: "mock", detail: "Database test usage." },
      ],
      compute: [
        { id: "backend", name: "Backend API", provider: "Railway Serverless", runtime_model: "Serverless", cpu_used_percent: 4, cpu_allocated_cores: 0.5, memory_used_bytes: 134217728, memory_allocated_bytes: 1073741824, memory_used_percent: 12.5, min_replicas: 0, max_replicas: 1, uptime_seconds: 300, status: "healthy", detail: "Backend test usage." },
      ],
      database_connections: { used: 1, total: 10, utilization_percent: 10, status: "healthy", detail: "Connection test usage." },
      quotas: [
        { id: "frontend_assets", name: "Frontend app size", provider: "Azure Static Web Apps Free", used: 42, total: 250, unit: "MB", utilization_percent: 16.8, status: "healthy", detail: "Mock app size." },
        { id: "frontend_bandwidth", name: "Frontend bandwidth", provider: "Azure Static Web Apps Free", used: 3, total: 100, unit: "GB/month", utilization_percent: 3, status: "healthy", detail: "Mock bandwidth." },
      ],
      provider_billing: [
        { id: "railway", provider: "Railway", plan: "Free", subscription_fee_usd: 0, included_credit_usd: 1, current_usage_usd: 0.42, current_amount_due_usd: 0, projected_usage_usd: 0.88, projected_amount_due_usd: 0, billing_period_start: "2026-08-01T00:00:00Z", billing_period_end: "2026-09-01T00:00:00Z", next_charge_at: null, configured: true, status: "healthy", source: "Railway Usage", detail: "No $5 is currently owed. Upgrade to Hobby only if the Free resource credit is exhausted." },
        { id: "neon", provider: "Neon", plan: "Free", subscription_fee_usd: 0, included_credit_usd: 0, current_usage_usd: 0.42, current_amount_due_usd: 0.42, projected_usage_usd: 11.2, projected_amount_due_usd: 0.42, billing_period_start: "2026-08-01T00:00:00Z", billing_period_end: "2026-09-01T00:00:00Z", next_charge_at: null, configured: true, status: "warning", source: "Neon project details API", detail: "Month-to-date Neon billing from the provider API." },
        { id: "resend", provider: "Resend", plan: "Free", subscription_fee_usd: 0, included_credit_usd: 0, current_usage_usd: 0, current_amount_due_usd: 0, projected_usage_usd: 0, projected_amount_due_usd: 0, billing_period_start: "2026-08-01T00:00:00Z", billing_period_end: "2026-09-01T00:00:00Z", next_charge_at: null, configured: true, status: "healthy", source: "Resend quota headers", detail: "Free includes 3,000 monthly emails and 100 daily." },
        { id: "r2", provider: "Cloudflare R2", plan: "Standard", subscription_fee_usd: 0, included_credit_usd: 0, current_usage_usd: 0.18, current_amount_due_usd: 0.18, projected_usage_usd: 0.18, projected_amount_due_usd: 0.18, billing_period_start: "2026-08-01T00:00:00Z", billing_period_end: "2026-09-01T00:00:00Z", next_charge_at: null, configured: true, status: "healthy", source: "Cloudflare GraphQL", detail: "R2 egress is free; storage and Class A/B operations are metered." },
        { id: "azure", provider: "Microsoft Azure", plan: "Pay as you go", subscription_fee_usd: 0, included_credit_usd: 0, current_usage_usd: 2.35, current_amount_due_usd: 2.35, projected_usage_usd: 2.35, projected_amount_due_usd: 2.35, billing_period_start: "2026-08-01T00:00:00Z", billing_period_end: "2026-09-01T00:00:00Z", next_charge_at: null, configured: true, status: "healthy", source: "Azure Cost Management", detail: "All Azure services combined for the current month." },
      ],
      cost_drivers: [
        { id: "railway_usage_credit", provider: "Railway", service: "Backend API + newsletter retry", plan: "Free", metric: "Resource usage credit", used: 0.42, included: 1, remaining: 0.58, unit: "USD", utilization_percent: 42, projected_month_end: 0.88, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 5, status: "healthy", source: "Railway Usage", detail: "CPU, RAM, volume storage, and network egress consume the credit." },
        { id: "railway_network", provider: "Railway", service: "Backend API + newsletter retry", plan: "Free", metric: "Network egress", used: 2.75, included: null, remaining: null, unit: "GB", utilization_percent: null, projected_month_end: 5.5, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 0.05, status: "healthy", source: "Railway usage variables", detail: "Outbound network traffic generated by the backend." },
        { id: "neon_compute", provider: "Neon", service: "PostgreSQL database", plan: "Free", metric: "Compute", used: 65.53, included: 100, remaining: 34.47, unit: "CU-hours", utilization_percent: 65.5, projected_month_end: 92, current_cost_usd: 0, projected_cost_usd: 9.75, next_paid_increment_usd: 9.75, status: "healthy", source: "Neon project details API", detail: "Free allowance; Launch reference is $0.106/CU-hour." },
        { id: "neon_storage", provider: "Neon", service: "PostgreSQL database", plan: "Free", metric: "Database storage", used: 0.04, included: 0.5, remaining: 0.46, unit: "GB", utilization_percent: 8, projected_month_end: 0.04, current_cost_usd: 0, projected_cost_usd: 0.01, next_paid_increment_usd: 0.01, status: "healthy", source: "Neon project details API", detail: "Free allowance; Launch reference is $0.35/GB-month." },
        { id: "neon_history", provider: "Neon", service: "PostgreSQL database", plan: "Free", metric: "History data changes", used: 0, included: 1, remaining: 1, unit: "GB", utilization_percent: 0, projected_month_end: 0, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 0, status: "healthy", source: "Neon project details API", detail: "Free history is limited to six hours or 1 GB of changes." },
        { id: "neon_network", provider: "Neon", service: "PostgreSQL database", plan: "Free", metric: "Public network transfer", used: 4.26, included: 5, remaining: 0.74, unit: "GB", utilization_percent: 85.2, projected_month_end: 6, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 0, status: "warning", source: "Neon project details API", detail: "Free compute pauses at 5 GB unless the plan is upgraded." },
        { id: "neon_branches", provider: "Neon", service: "PostgreSQL database", plan: "Free", metric: "Active branches", used: 2, included: 10, remaining: 8, unit: "branches", utilization_percent: 20, projected_month_end: null, current_cost_usd: 0, projected_cost_usd: null, next_paid_increment_usd: 0.002, status: "healthy", source: "Neon project details API", detail: "Launch includes 10 branches, then charges approximately $0.002 per additional branch-hour." },
        { id: "resend_monthly_emails", provider: "Resend", service: "Transactional email", plan: "Free", metric: "Monthly emails", used: 320, included: 3000, remaining: 2680, unit: "emails/month", utilization_percent: 10.7, projected_month_end: 700, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 20, status: "healthy", source: "Resend quota headers", detail: "Inbound and outbound recipient counts affect the quota." },
        { id: "resend_daily_emails", provider: "Resend", service: "Transactional email", plan: "Free", metric: "Daily emails", used: 12, included: 100, remaining: 88, unit: "emails/day", utilization_percent: 12, projected_month_end: null, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 20, status: "healthy", source: "Resend quota headers", detail: "The daily quota resets independently of the monthly quota." },
        { id: "r2_storage", provider: "Cloudflare R2", service: "Object storage", plan: "Standard", metric: "Stored data snapshot", used: 0.001, included: 10, remaining: 9.999, unit: "GB-month", utilization_percent: 0.01, projected_month_end: 0.001, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 0.015, status: "healthy", source: "R2 S3 API", detail: "Billing averages the daily peak storage over the month; egress is free." },
        { id: "r2_class_a", provider: "Cloudflare R2", service: "Object storage", plan: "Standard", metric: "Class A operations", used: 1200, included: 1000000, remaining: 998800, unit: "requests/month", utilization_percent: 0.1, projected_month_end: 2500, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 4.5, status: "healthy", source: "Cloudflare GraphQL", detail: "The next million Class A operations costs $4.50." },
        { id: "r2_class_b", provider: "Cloudflare R2", service: "Object storage", plan: "Standard", metric: "Class B operations", used: 8200, included: 10000000, remaining: 9991800, unit: "requests/month", utilization_percent: 0.08, projected_month_end: 16000, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 0.36, status: "healthy", source: "Cloudflare GraphQL", detail: "The next ten million Class B operations cost $0.36." },
        { id: "azure_bandwidth", provider: "Microsoft Azure", service: "Static Web Apps frontend", plan: "Free", metric: "Frontend bandwidth", used: 3, included: 100, remaining: 97, unit: "GB/month", utilization_percent: 3, projected_month_end: 6, current_cost_usd: 0, projected_cost_usd: 0, next_paid_increment_usd: 0.2, status: "healthy", source: "Azure quota", detail: "Free stops at its quota; Standard bandwidth overage is $0.20/GB." },
      ],
      costs: {
        currency: "USD", basis: "monthly_estimate", source: "mock",
        monthly_budget_usd: 25, tracked_monthly_estimate_usd: 0,
        current_month_cost_usd: 0, current_month_paid_usd: 0,
        current_outstanding_usd: 0, recorded_total_usd: 12.3,
        recorded_paid_usd: 12.3, recorded_outstanding_usd: 0,
        forecast_monthly_cost_usd: 0, budget_utilization_percent: 0,
        unconfigured_services: 0, detail: "Test estimate.",
        items: [
          { id: "railway", name: "Backend API + newsletter retry", provider: "Railway Free", monthly_estimate_usd: 0, configured: true, detail: "No $5 currently owed." },
          { id: "neon", name: "PostgreSQL database", provider: "Neon Free", monthly_estimate_usd: 0, configured: true, detail: "Mock Neon cost." },
          { id: "resend", name: "Transactional email", provider: "Resend Free", monthly_estimate_usd: 0, configured: true, detail: "Mock Resend cost." },
          { id: "azure_static_web_apps", name: "Frontend hosting", provider: "Azure Static Web Apps Free", monthly_estimate_usd: 0, configured: true, detail: "Mock frontend cost." },
        ],
        history: [
          { month: "2026-07", total_usd: 12.3, paid_usd: 12.3, outstanding_usd: 0, provider_costs: { "Microsoft Azure": 12.3 }, source: "manual invoice backfill", estimated: false, available: true },
          { month: "2026-08", total_usd: 0, paid_usd: 0, outstanding_usd: 0, provider_costs: { Railway: 0, Neon: 0, Resend: 0, "Microsoft Azure": 0, "Cloudflare R2": 0 }, source: "stored monthly snapshot", estimated: true, available: true },
        ],
      },
      alerts: [{ severity: "healthy", title: "All measured resources are within target", detail: "No measured resource crossed the warning threshold." }],
    });
  }
  if (path === "/api/admin/seo/dashboard") {
    return json(response, {
      on_page: {}, off_page: {}, performance: {}, jobs_with_seo: 0, pages_with_seo: 0,
      total_jobs: 0, total_pages: 0, issues: [], metrics: [],
      gsc: {
        connected: true,
        period_start: "2026-06-29",
        period_end: "2026-07-26",
        data_source: "Google Search Console Search Analytics API",
        position_note: "Average position is not a live or fixed result.",
      },
      backlinks: [
        {
          id: "backlink-original",
          source_url: "https://www.linkedin.com/company/pakistanjobsmarket/",
          target_url: "https://pakistanjobsmarket.com/",
          domain: "www.linkedin.com",
          anchor_text: "linkedin_url",
        },
        {
          id: "backlink-duplicate",
          source_url: "https://www.linkedin.com/company/pakistanjobsmarket",
          target_url: "https://pakistanjobsmarket.com",
          domain: "www.linkedin.com",
          anchor_text: "linkedin_url",
        },
      ],
      keyword_ranks: Array.from({ length: 21 }, (_, index) => ({
        id: `keyword-${index}`,
        keyword: `unique keyword ${index}`,
        url: `https://pakistanjobsmarket.com/jobs/role-${index}`,
        position: index + 1,
        average_position: index + 1,
        clicks: index,
        impressions: index + 10,
        ctr: index / (index + 10),
        url_count: index === 0 ? 3 : 1,
      })),
      url_ranks: [{
        url: "https://pakistanjobsmarket.com/jobs/role-0",
        entity_type: "job",
        average_position: 8.5,
        clicks: 1,
        impressions: 12,
        ctr: 1 / 12,
      }],
      social: {}, pagespeed: {}, authority: {},
    });
  }
  return json(response, { detail: `No mock for ${path}` }, 404);
});

server.listen(4010, "127.0.0.1");
