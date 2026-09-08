import assert from "node:assert/strict";
import { setTimeout } from "node:timers/promises";

// Run against next start, never next dev: development RSC debug records include
// server component inputs that are deliberately absent from release output.
const origin = process.env.HTML_BUDGET_ORIGIN || "http://127.0.0.1:3102";
let response;
for (let attempt = 0; attempt < 30; attempt++) {
  try {
    response = await fetch(`${origin}/?q=html-budget-fixture`, {
      signal: AbortSignal.timeout(10_000),
    });
    if (response.ok) break;
  } catch {}
  await setTimeout(500);
}
assert.ok(response?.ok, "Production test server must return HTTP 200");
const html = await response.text();
const bytes = Buffer.byteLength(html, "utf8");
assert.ok(bytes < 300_000, `Uncompressed HTML ${bytes} bytes exceeds 300,000-byte budget`);
assert.equal((html.match(/<article\b[^>]*class="job-card /g) || []).length, 30);
assert.ok(!html.includes("FULL_DESCRIPTION_PAYLOAD"), "Unused descriptions must stay server-side");
assert.ok(html.includes('href="/jobs/budget-role-29"'));
assert.ok(html.includes('"numberOfItems":30'));
assert.ok(!html.includes('"@type":"JobPosting"'), "List pages must not contain individual JobPosting markup");
assert.ok(html.includes('property="og:image"'));
assert.match(html.match(/<img\b[^>]*>/)?.[0] || "", /loading="eager"/);
console.log(`HTML budget passed: ${bytes} uncompressed bytes, 30 server-rendered cards, SEO and eager logo preserved.`);
