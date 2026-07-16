import { createServer } from "node:http";

const json = (response, value, status = 200) => {
  response.writeHead(status, {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Content-Type": "application/json",
  });
  response.end(JSON.stringify(value));
};

const server = createServer((request, response) => {
  if (request.method === "OPTIONS") return json(response, {});
  const path = new URL(request.url || "/", "http://127.0.0.1:4010").pathname;
  if (path === "/ready") return json(response, { status: "ready" });
  if (path === "/api/settings/branding") {
    return json(response, {
      site_name: "PakJobs",
      site_title: "PakJobs Jobs in Pakistan",
      site_header: "Latest government & private job openings in Pakistan",
      site_description: "Find current job opportunities across Pakistan.",
      footer_copyright: "Copyrights © {year} - PakistanJobs All rights reserved",
      logo_url: null,
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
    return json(response, { ok: true, status: "subscribed", message: "Your email has been subscribed to daily job alerts." });
  }
  if (path === "/api/subscriptions/unsubscribe") {
    return json(response, { ok: true, status: "unsubscribed", message: "You have been unsubscribed." });
  }
  if (path === "/api/admin/subscriptions") {
    return json(response, {
      subscriber_count: 7, active_subscriber_count: 6,
      subject_template: "Daily Job Alerts from {site_title} — {date}",
      body_template: "Dear Sir/Madam, jobs from {range_start} to {range_end}.",
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
  if (path === "/api/admin/subscriptions/send-digest") {
    return json(response, { status: "completed", window_start: new Date().toISOString(), window_end: new Date().toISOString(), jobs_count: 2, recipients_count: 6, sent_count: 6, failed_count: 0, message: "Sent 6 of 6 daily job alert emails." });
  }
  if (path === "/api/jobs") {
    return json(response, { items: [{
      id: "closed-role", slug: "closed-role", title: "Nationwide Closed Role",
      description: "A nationwide job with a passed deadline.", published_date: "2026-07-01T00:00:00Z",
      deadline_date: "2026-07-02T00:00:00Z", application_deadline: "2026-07-02T00:00:00Z",
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
      description: "<p>A nationwide job with a passed deadline.</p>", published_date: "2026-07-01T00:00:00Z",
      deadline_date: "2026-07-02T00:00:00Z", application_deadline: "2026-07-02T00:00:00Z",
      salary_range: null, source: "FPSC", reference_url: "https://fpsc.gov.pk/advertisement", application_url: "https://fpsc.gov.pk/apply",
      experience_required: null, education_required: null, skills: [], job_type: "government",
      cities: ["Karachi", "Lahore"], tags: ["Government"], keywords: null, created_at: "2026-07-01T00:00:00Z",
      company: "FPSC", location: "Pakistan", city: "Pakistan", province: null, employment_type: null,
      salary_min: null, salary_max: null, currency: "PKR", category: "Government",
      source_type: "govt", source_name: "FPSC", nationwide: true, applications_closed: true,
      application_email: null, source_url: null, attachments: [], qna: [], resources: [],
    });
  }
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
