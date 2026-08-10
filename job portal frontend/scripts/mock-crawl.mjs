const base = new URL(process.env.CRAWL_BASE_URL || "http://127.0.0.1:3100");
const concurrency = Math.max(1, Number(process.env.CRAWL_CONCURRENCY || 6));
const googlebot =
  "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)";

function decodeXml(value) {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&apos;", "'");
}

function normalize(value) {
  const url = new URL(value, base);
  url.hash = "";
  url.search = "";
  if (url.pathname !== "/") url.pathname = url.pathname.replace(/\/+$/, "");
  return url.href;
}

function attribute(html, tagPattern, name) {
  const match = html.match(tagPattern);
  if (!match) return null;
  const value = match[0].match(new RegExp(`${name}=["']([^"']+)["']`, "i"));
  return value?.[1] || null;
}

function visibleTextLength(html) {
  return html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim().length;
}

async function fetchAsGooglebot(url) {
  return fetch(url, {
    redirect: "follow",
    headers: { "User-Agent": googlebot, Accept: "text/html,application/xhtml+xml" },
    signal: AbortSignal.timeout(30_000),
  });
}

async function mapLimit(values, limit, callback) {
  const results = new Array(values.length);
  let cursor = 0;
  async function worker() {
    while (cursor < values.length) {
      const index = cursor++;
      results[index] = await callback(values[index], index);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, values.length) }, worker));
  return results;
}

const sitemapUrl = new URL("/sitemap.xml", base);
const sitemapResponse = await fetchAsGooglebot(sitemapUrl);
if (!sitemapResponse.ok) {
  throw new Error(`Sitemap returned ${sitemapResponse.status}: ${sitemapUrl}`);
}
if (normalize(sitemapResponse.url) !== normalize(sitemapUrl)) {
  throw new Error(`Public sitemap redirected to ${sitemapResponse.url}`);
}
const sitemapXml = await sitemapResponse.text();
const sitemapLocations = Array.from(
  sitemapXml.matchAll(/<loc>([^<]+)<\/loc>/g),
  (match) => normalize(decodeXml(match[1])),
);
const uniqueLocations = [...new Set(sitemapLocations)];
if (!uniqueLocations.length) throw new Error("Sitemap contains no URLs");
if (uniqueLocations.length !== sitemapLocations.length) {
  throw new Error(`Sitemap contains ${sitemapLocations.length - uniqueLocations.length} duplicates`);
}
const foreignLocations = uniqueLocations.filter(
  (location) => new URL(location).origin !== base.origin,
);
if (foreignLocations.length) {
  throw new Error(`Sitemap contains foreign origins:\n${foreignLocations.join("\n")}`);
}

const browseResponse = await fetchAsGooglebot(new URL("/browse", base));
if (!browseResponse.ok) throw new Error(`/browse returned ${browseResponse.status}`);
const browseHtml = await browseResponse.text();
const browseLinks = new Set(
  Array.from(
    browseHtml.matchAll(/<a\b[^>]*href=["']([^"']+)["']/gi),
    (match) => {
      try {
        return normalize(match[1]);
      } catch {
        return null;
      }
    },
  ).filter(Boolean),
);

const failures = [];
await mapLimit(uniqueLocations, concurrency, async (location) => {
  try {
    const response = await fetchAsGooglebot(location);
    const html = await response.text();
    if (response.status !== 200) failures.push(`${location}: HTTP ${response.status}`);
    if (normalize(response.url) !== location) {
      failures.push(`${location}: redirects to ${response.url}`);
    }
    if (!/<title(?:\s[^>]*)?>[\s\S]*?<\/title>/i.test(html)) {
      failures.push(`${location}: missing server-rendered title`);
    }
    const robots = attribute(html, /<meta\b[^>]*name=["']robots["'][^>]*>/i, "content");
    if (robots && /noindex/i.test(robots)) failures.push(`${location}: marked noindex`);
    const canonical = attribute(
      html,
      /<link\b[^>]*rel=["']canonical["'][^>]*>/i,
      "href",
    );
    if (!canonical) {
      failures.push(`${location}: missing canonical link`);
    } else if (normalize(canonical) !== location) {
      failures.push(`${location}: canonical points to ${canonical}`);
    }
    if (visibleTextLength(html) < 120) {
      failures.push(`${location}: thin initial HTML (${visibleTextLength(html)} characters)`);
    }
  } catch (error) {
    failures.push(`${location}: ${error instanceof Error ? error.message : String(error)}`);
  }
});

const orphans = uniqueLocations.filter((location) => !browseLinks.has(location));
if (orphans.length) {
  failures.push(`/browse does not link ${orphans.length} sitemap URL(s):\n${orphans.join("\n")}`);
}

if (failures.length) {
  console.error(`Mock crawl failed with ${failures.length} issue(s):`);
  for (const failure of failures) console.error(`- ${failure}`);
  process.exitCode = 1;
} else {
  console.log(
    `Mock crawl passed: ${uniqueLocations.length} canonical pages, 1 sitemap, 0 redirects, 0 noindex pages, 0 orphans.`,
  );
}
