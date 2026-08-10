import { createServer } from "node:http";

const json = (response, value, status = 200) => {
  response.writeHead(status, {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Content-Type": "application/json",
  });
  response.end(JSON.stringify(value));
};

const server = createServer((request, response) => {
  if (request.method === "OPTIONS") return json(response, {});
  const path = new URL(request.url || "/", "http://127.0.0.1:4010").pathname;
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
  if (path === "/api/admin/settings/branding" && request.method === "PUT") {
    return json(response, {
      site_name: "Pakistan Jobs Market",
      site_title: "Pakistan Jobs Market",
      site_title_alignment: "beside_logo",
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
      source_types: [], sectors: ["govt", "private"], categories: ["Software Engineering"],
      cities: ["Lahore"], provinces: ["Punjab"],
      companies: [], employment_types: [], tags: ["Software Engineering"], job_types: ["government", "private"],
    });
  }
  if (path === "/api/sitemap-data") {
    return json(response, {
      urls: [
        { loc: "http://localhost:3000/jobs/closed-role", changefreq: "weekly", priority: 0.8 },
        { loc: "http://localhost:3000/jobs/multi-location-role", changefreq: "weekly", priority: 0.8 },
        { loc: "http://localhost:3000/blog/fpsc-preparation-guide", changefreq: "weekly", priority: 0.7 },
        { loc: "http://localhost:3000/p/custom-seo-page", changefreq: "monthly", priority: 0.5 },
        { loc: "http://localhost:3000/categories/software-engineering", changefreq: "weekly", priority: 0.6 },
        { loc: "http://localhost:3000/tags/government", changefreq: "weekly", priority: 0.5 },
        { loc: "http://localhost:3000/locations/lahore", changefreq: "weekly", priority: 0.6 },
        { loc: "http://localhost:3000/locations/punjab", changefreq: "weekly", priority: 0.6 },
        { loc: "http://localhost:3000/companies/fpsc", changefreq: "weekly", priority: 0.6 },
        { loc: "http://localhost:3000/qualifications/bachelors", changefreq: "weekly", priority: 0.5 },
        { loc: "http://localhost:3000/blog/categories/career-advice", changefreq: "weekly", priority: 0.5 },
        { loc: "http://localhost:3000/blog/tags/fpsc", changefreq: "weekly", priority: 0.4 },
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
          applications_closed: true, organization: "FPSC", category: "Government",
          cities: ["Karachi", "Lahore"], provinces: ["Sindh"], tags: ["Government"],
        },
        {
          id: "multi-location-role", slug: "multi-location-role", title: "Multi Location Role",
          published_date: "2026-07-02T00:00:00Z", deadline_date: null,
          applications_closed: false, organization: "FPSC", category: "Software Engineering",
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
        qualifications: [{ name: "Bachelors", slug: "bachelors", count: 1 }],
        blog_categories: [{ name: "Career Advice", slug: "career-advice", count: 1 }],
        blog_tags: [{ name: "FPSC", slug: "fpsc", count: 1 }],
      },
    });
  }
  if (path === "/api/taxonomy" || path === "/api/admin/taxonomy") {
    return json(response, [
      { id: "term-software", kind: "category", name: "Software Engineering", slug: "software-engineering", is_active: true },
      { id: "term-education", kind: "category", name: "Education", slug: "education", is_active: true },
    ]);
  }
  if (path.startsWith("/api/admin/taxonomy/")) {
    return json(response, { id: path.split("/").pop(), kind: "category", name: "Software Engineering", slug: "software-engineering", is_active: false });
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
      description: "A nationwide job with a passed deadline.", published_date: "2026-07-01T00:00:00Z",
      // Canonical deadline_date must win over the legacy alias. The alias
      // deliberately represents the previous UTC day to guard the Pakistan
      // timezone regression reported in production.
      deadline_date: "2026-07-17T00:00:00", application_deadline: "2026-07-16T19:00:00Z",
      salary_range: null, source: "FPSC", reference_url: "https://fpsc.gov.pk/advertisement", application_url: "https://fpsc.gov.pk/apply",
      experience_required: null, education_required: null, skills: [], job_type: "government",
      cities: ["Karachi", "Lahore"], provinces: ["Sindh"], tags: ["Government"], keywords: null, created_at: "2026-07-01T00:00:00Z",
      company: "FPSC", location: "Pakistan", city: "Pakistan", province: null, employment_type: null,
      salary_min: null, salary_max: null, currency: "PKR", category: "Government",
      source_type: "govt", source_name: "FPSC", nationwide: true, applications_closed: true,
    }, {
      id: "multi-location-role", slug: "multi-location-role", title: "Multi Location Role",
      description: "A role available in more than one city.", published_date: "2026-07-02T00:00:00Z",
      deadline_date: null, application_deadline: null, salary_range: null, source: "FPSC",
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
  if (path === "/api/stats") {
    return json(response, { total_jobs: 1, open_for_apply: 0, by_source_type: { govt: 1 }, by_category: { Government: 1 }, by_city: { Pakistan: 1 }, by_job_type: { government: 1 }, last_updated: new Date().toISOString() });
  }
  if (path === "/api/jobs/closed-role" || path === "/api/jobs/legacy-closed-role-id") {
    return json(response, {
      id: "closed-role", slug: "closed-role", title: "Nationwide Closed Role",
      description: '<h2><span style="background-color:rgb(255,255,255);color:rgb(0,0,0)">Role overview</span></h2><p>https://example.com/this-is-a-deliberately-long-reference-that-must-wrap-inside-the-job-description-on-small-screens</p><ol><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Build resilient pipelines</li><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Monitor platform performance</li></ol><ul><li>Standard HTML bullet</li></ul><table><tbody><tr><td><strong>Job ID</strong></td><td><strong>Position</strong></td></tr><tr><td>PDA-J0149</td><td>Recruitment Manager</td></tr><tr><td>PDA-J0150</td><td>AI Associate</td></tr></tbody></table><img alt="R2 job image" src="https://files.pakistanjobsmarket.com/job-portal/closed-role/images/notice.png">', published_date: "2026-07-01T00:00:00Z",
      deadline_date: "2026-07-17T00:00:00", application_deadline: "2026-07-16T19:00:00Z",
      salary_range: null, source: "FPSC", reference_url: "https://fpsc.gov.pk/advertisement", application_url: "https://fpsc.gov.pk/apply",
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
      description: '<h2><span style="background-color:rgb(255,255,255);color:rgb(0,0,0)">Role overview</span></h2><p>https://example.com/this-is-a-deliberately-long-reference-that-must-wrap-inside-the-job-description-on-small-screens</p><ol><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Build resilient pipelines</li><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>Monitor platform performance</li></ol><ul><li>Standard HTML bullet</li></ul><table><tbody><tr><td><strong>Job ID</strong></td><td><strong>Position</strong></td></tr><tr><td>PDA-J0149</td><td>Recruitment Manager</td></tr><tr><td>PDA-J0150</td><td>AI Associate</td></tr></tbody></table><img alt="R2 job image" src="https://files.pakistanjobsmarket.com/job-portal/closed-role/images/notice.png">',
      published_date: "2026-07-01T00:00:00Z", deadline_date: null, application_deadline: null,
      salary_range: null, source: "FPSC", reference_url: null, application_url: null,
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
      { id: "about", slug: "about", title: "About Us", content: "<p>About</p>", is_published: true },
      { id: "contact", slug: "contact", title: "Contact Us", content: "<p>Contact</p>", is_published: true },
      { id: "privacy", slug: "privacy", title: "Privacy Policy", content: "<p>Privacy</p>", is_published: true },
      { id: "disclaimer", slug: "disclaimer", title: "Disclaimer", content: "<p>Disclaimer</p>", is_published: true },
    ]);
  }
  if (path === "/api/pages/custom-seo-page") {
    return json(response, {
      id: "custom-seo-page-id",
      slug: "custom-seo-page",
      title: "Custom public page",
      content: "<p>A published CMS page that is safe for search indexing.</p>",
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
      window_minutes: 5, active_visitors: 0, page_views: 0,
      generated_at: new Date().toISOString(), pages: [], locations: [],
    });
  }
  if (path === "/api/admin/analytics") {
    return json(response, {
      month: new Date().toISOString().slice(0, 7), unique_visitors: 0,
      page_views: 0, daily: [], locations: [],
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
      quotas: [],
      costs: {
        currency: "USD", basis: "monthly_estimate", source: "mock",
        monthly_budget_usd: 25, tracked_monthly_estimate_usd: 5,
        current_month_cost_usd: 5, current_month_paid_usd: 0,
        current_outstanding_usd: 5, recorded_total_usd: 17.3,
        recorded_paid_usd: 12.3, recorded_outstanding_usd: 5,
        forecast_monthly_cost_usd: null, budget_utilization_percent: 20,
        unconfigured_services: 0, detail: "Test estimate.",
        items: [
          { id: "railway", name: "Backend API + newsletter retry", provider: "Railway Hobby", monthly_estimate_usd: 5, configured: true, detail: "Mock Railway cost." },
          { id: "neon", name: "PostgreSQL database", provider: "Neon Free", monthly_estimate_usd: 0, configured: true, detail: "Mock Neon cost." },
          { id: "azure_static_web_apps", name: "Frontend hosting", provider: "Azure Static Web Apps Free", monthly_estimate_usd: 0, configured: true, detail: "Mock frontend cost." },
        ],
        history: [
          { month: "2026-07", total_usd: 12.3, paid_usd: 12.3, outstanding_usd: 0, provider_costs: { "Microsoft Azure": 12.3 }, source: "manual invoice backfill", estimated: false, available: true },
          { month: "2026-08", total_usd: 5, paid_usd: 0, outstanding_usd: 5, provider_costs: { Railway: 5, Neon: 0, "Microsoft Azure": 0, "Cloudflare R2": 0 }, source: "stored monthly snapshot", estimated: true, available: true },
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
