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
  if (path === "/api/filters") {
    return json(response, {
      source_types: [], sectors: ["govt", "private"], categories: ["Software Engineering"], cities: ["Lahore"],
      companies: [], employment_types: [], tags: ["Software Engineering"], job_types: ["government", "private"],
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
    });
  }
  if (path === "/api/admin/subscriptions/template") {
    return json(response, {
      subscriber_count: 7, active_subscriber_count: 6,
      subject_template: "Saved subject", body_template: "Saved body",
      last_digest_at: null, last_digest_status: null,
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
      cities: ["Karachi", "Lahore"], tags: ["Government"], keywords: null, created_at: "2026-07-01T00:00:00Z",
      company: "FPSC", location: "Pakistan", city: "Pakistan", province: null, employment_type: null,
      salary_min: null, salary_max: null, currency: "PKR", category: "Government",
      source_type: "govt", source_name: "FPSC", nationwide: true, applications_closed: true,
    }], total: 1, page: 1, page_size: 50, pages: 1 });
  }
  if (path === "/api/stats") {
    return json(response, { total_jobs: 1, open_for_apply: 0, by_source_type: { govt: 1 }, by_category: { Government: 1 }, by_city: { Pakistan: 1 }, by_job_type: { government: 1 }, last_updated: new Date().toISOString() });
  }
  if (path === "/api/jobs/closed-role") {
    return json(response, {
      id: "closed-role", slug: "closed-role", title: "Nationwide Closed Role",
      description: '<p>A nationwide job with a passed deadline.</p><img alt="R2 job image" src="https://files.pakistanjobsmarket.com/job-portal/closed-role/images/notice.png">', published_date: "2026-07-01T00:00:00Z",
      deadline_date: "2026-07-17T00:00:00", application_deadline: "2026-07-16T19:00:00Z",
      salary_range: null, source: "FPSC", reference_url: "https://fpsc.gov.pk/advertisement", application_url: "https://fpsc.gov.pk/apply",
      experience_required: null, education_required: null, skills: [], job_type: "government",
      cities: ["Karachi", "Lahore"], tags: ["Government"], keywords: null, created_at: "2026-07-01T00:00:00Z",
      company: "FPSC", location: "Pakistan", city: "Pakistan", province: null, employment_type: null,
      salary_min: null, salary_max: null, currency: "PKR", category: "Government",
      source_type: "govt", source_name: "FPSC", nationwide: true, applications_closed: true,
      application_email: null, source_url: null, attachments: [], qna: [], resources: [],
    });
  }
  const blogPost = {
    id: "blog-1", slug: "fpsc-preparation-guide", title: "FPSC Preparation Guide",
    excerpt: "A practical preparation guide for candidates in Pakistan.",
    content: "<h2>Build a study plan</h2><p><span data-testid=\"pasted-rich-text\" style=\"background-color: rgb(255, 255, 255); color: rgb(0, 0, 0)\">Use the syllabus and practice consistently.</span></p><p>https://example.com/this-is-a-deliberately-very-long-reference-that-must-wrap-inside-the-article-instead-of-being-cut-off-on-the-right-side</p><table style=\"width:1600px\"><tbody><tr><td>Wide legacy table content</td><td>Second column</td></tr></tbody></table>",
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
  if (path === "/api/admin/contact") return json(response, []);
  if (path === "/api/admin/analytics/realtime") {
    return json(response, {
      window_minutes: 5, active_visitors: 0, page_views: 0,
      generated_at: new Date().toISOString(), pages: [],
    });
  }
  if (path === "/api/admin/analytics") {
    return json(response, {
      month: new Date().toISOString().slice(0, 7), unique_visitors: 0,
      page_views: 0, daily: [], locations: [],
    });
  }
  if (path === "/api/admin/seo/dashboard") {
    return json(response, {
      on_page: {}, off_page: {}, performance: {}, jobs_with_seo: 0, pages_with_seo: 0,
      total_jobs: 0, total_pages: 0, issues: [], metrics: [], backlinks: [],
      keyword_ranks: [], url_ranks: [], social: {}, pagespeed: {}, authority: {},
    });
  }
  return json(response, { detail: `No mock for ${path}` }, 404);
});

server.listen(4010, "127.0.0.1");
