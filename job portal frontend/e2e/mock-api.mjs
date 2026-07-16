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
      source_types: [], sectors: ["govt", "private"], categories: [], cities: ["Lahore"],
      companies: [], employment_types: [], tags: [], job_types: ["government", "private"],
    });
  }
  if (path === "/api/jobs") {
    return json(response, { items: [], total: 0, page: 1, page_size: 50, pages: 0 });
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
