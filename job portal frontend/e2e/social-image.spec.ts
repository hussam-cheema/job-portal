import { expect, test } from "@playwright/test";

test("public route families include a usable Open Graph image in initial HTML", async ({ request }) => {
  test.setTimeout(120_000);
  for (const path of ["/", "/tools", "/dashboard", "/dashboard/2026-09", "/about", "/jobs-by-cities", "/categories/software-engineering", "/p/custom-seo-page", "/jobs/closed-role", "/blog"]) {
    const response = await request.get(path);
    expect(response.ok(), path).toBeTruthy();
    const html = await response.text();
    const image = html.match(/<meta property="og:image" content="([^"]+)"/);
    expect(image, path).not.toBeNull();
    expect(new URL(image![1]).protocol, path).toMatch(/^https?:$/);
    const firstImage = html.match(/<img\b[^>]*>/)?.[0];
    expect(firstImage, path).toContain('loading="eager"');
    expect(firstImage, path).toContain('fetchPriority="high"');
  }
});
