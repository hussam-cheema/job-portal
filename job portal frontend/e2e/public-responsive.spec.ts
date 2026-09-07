import { expect, test, type Page } from "@playwright/test";

const viewports = [
  { name: "narrow phone", width: 320, height: 740 },
  { name: "small phone", width: 360, height: 800 },
  { name: "tablet portrait", width: 820, height: 1180 },
  { name: "tablet landscape", width: 1024, height: 768 },
  { name: "desktop", width: 1440, height: 900 },
] as const;

const adminPaths = [
  "/admin",
  "/admin/jobs",
  "/admin/jobs/new",
  "/admin/jobs/closed-role",
  "/admin/blog",
  "/admin/blog/new",
  "/admin/pages",
  "/admin/pages/new",
  "/admin/messages",
  "/admin/analytics",
  "/admin/infrastructure",
  "/admin/seo",
  "/admin/newsletter",
  "/admin/taxonomy",
  "/admin/cities",
  "/admin/tools",
  "/admin/settings",
] as const;

type LayoutAudit = {
  documentWidth: number;
  viewportWidth: number;
  headerCollision: boolean;
  offenders: Array<{
    element: string;
    left: number;
    right: number;
    text: string;
  }>;
};

async function sitemapPaths(page: Page) {
  const response = await page.request.get("/sitemap.xml");
  expect(response.ok()).toBeTruthy();
  const xml = await response.text();
  const paths = Array.from(xml.matchAll(/<loc>([^<]+)<\/loc>/g), (match) => {
    const value = match[1]
      .replaceAll("&amp;", "&")
      .replaceAll("&quot;", '"')
      .replaceAll("&#39;", "'");
    return new URL(value).pathname;
  });
  return Array.from(new Set(paths));
}

async function auditCurrentPage(page: Page): Promise<LayoutAudit> {
  return page.evaluate(() => {
    const viewportWidth = window.innerWidth;
    const allowsContainedHorizontalScroll = (element: Element) => {
      let current: Element | null = element;
      while (current && current !== document.body) {
        const style = window.getComputedStyle(current);
        if (
          ["auto", "scroll"].includes(style.overflowX) &&
          (current as HTMLElement).scrollWidth > (current as HTMLElement).clientWidth + 1
        ) {
          return true;
        }
        current = current.parentElement;
      }
      return false;
    };

    const offenders = Array.from(document.body.querySelectorAll("*"))
      .flatMap((element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        const isDecorativeLayer =
          element.classList.contains("pointer-events-none") &&
          !(element.textContent || "").trim();
        if (
          style.display === "none" ||
          style.visibility === "hidden" ||
          Number(style.opacity) === 0 ||
          isDecorativeLayer ||
          rect.width < 1 ||
          rect.height < 1 ||
          (rect.left >= -1 && rect.right <= viewportWidth + 1) ||
          allowsContainedHorizontalScroll(element)
        ) {
          return [];
        }
        return [{
          element: `${element.tagName.toLowerCase()}.${Array.from(element.classList).slice(0, 3).join(".")}`,
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          text: (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80),
        }];
      })
      .slice(0, 12);

    const title = document.querySelector<HTMLElement>(".site-title");
    const actions = document.querySelector<HTMLElement>(".site-actions");
    const titleRect = title?.getBoundingClientRect();
    const actionsRect = actions?.getBoundingClientRect();
    const headerCollision = Boolean(
      titleRect && actionsRect &&
      titleRect.left < actionsRect.right &&
      titleRect.right > actionsRect.left &&
      titleRect.top < actionsRect.bottom &&
      titleRect.bottom > actionsRect.top
    );

    return {
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth,
      headerCollision,
      offenders,
    };
  });
}

for (const viewport of viewports) {
  test(`every public sitemap page fits the ${viewport.name} layout`, async ({ page }) => {
    test.setTimeout(360_000);
    await page.setViewportSize(viewport);
    const paths = await sitemapPaths(page);
    expect(paths.length).toBeGreaterThan(15);

    for (const path of paths) {
      const response = await page.goto(path, { waitUntil: "domcontentloaded" });
      expect(response?.status(), path).toBeLessThan(400);
      await expect(page.locator("body"), path).toBeVisible();
      // Allow client-side resize observers (notably the A4 builders) and CSS
      // transitions to settle before measuring final responsive geometry.
      await page.waitForTimeout(250);
      if (await page.locator(".document-preview-stage").count()) {
        await expect.poll(async () => page.evaluate(() => {
          const stage = document.querySelector<HTMLElement>(".document-preview-stage");
          const shell = stage?.parentElement;
          if (!stage || !shell) return false;
          return stage.getBoundingClientRect().width <= shell.clientWidth + 1;
        }), { message: `${path} A4 preview did not finish responsive scaling` }).toBe(true);
      }
      const result = await auditCurrentPage(page);
      if (path === "/tools") {
        const content = await page.locator(".tools-seo-content").evaluate((element) => {
          const blocks = [element, ...element.querySelectorAll("p, h2, h3, article, .tools-seo-guide > div")];
          return blocks.every((block) => {
            const rect = block.getBoundingClientRect();
            return rect.left >= 0 && rect.right <= innerWidth && block.scrollWidth <= block.clientWidth + 1;
          });
        });
        expect(content, "Tools guide must wrap without hidden or clipped text").toBe(true);
      }
      expect(result.documentWidth, `${path} expands the document at ${viewport.width}px`).toBeLessThanOrEqual(result.viewportWidth);
      expect(result.headerCollision, `${path} has overlapping title and navigation at ${viewport.width}px`).toBe(false);
      expect(result.offenders, `${path} clips visible elements at ${viewport.width}px`).toEqual([]);
    }
  });
}

for (const viewport of viewports.filter((item) => item.name !== "tablet landscape")) {
  test(`every admin page fits the ${viewport.name} layout`, async ({ page }) => {
    test.setTimeout(240_000);
    await page.addInitScript(() => {
      localStorage.setItem("pakjobs-admin-token", "e2e-token");
      localStorage.setItem("pakjobs-admin-user", "e2e-admin");
    });
    await page.setViewportSize(viewport);

    for (const path of adminPaths) {
      const response = await page.goto(path, { waitUntil: "domcontentloaded" });
      expect(response?.status(), path).toBeLessThan(400);
      await expect(page.locator(".admin-content"), path).toBeVisible();
      await page.waitForTimeout(250);
      const result = await auditCurrentPage(page);
      expect(result.documentWidth, `${path} expands the document at ${viewport.width}px`).toBeLessThanOrEqual(result.viewportWidth);
      expect(result.offenders, `${path} clips visible elements at ${viewport.width}px`).toEqual([]);
    }
  });
}

test("student API documentation wraps complete content on small phones", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/tools/api");

  const codeBlocks = page.locator(".student-api-docs pre");
  await expect(codeBlocks).toHaveCount(3);
  for (const codeBlock of await codeBlocks.all()) {
    const dimensions = await codeBlock.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
  }

  const titleBox = await page.locator(".site-title").boundingBox();
  const actionsBox = await page.locator(".site-actions").boundingBox();
  expect(titleBox).not.toBeNull();
  expect(actionsBox).not.toBeNull();
  expect(actionsBox!.y).toBeGreaterThanOrEqual(titleBox!.y + titleBox!.height);
});
