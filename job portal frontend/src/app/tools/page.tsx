import type { Metadata } from "next";
import Link from "next/link";
import { ToolsConstellation } from "@/components/ToolsConstellation";
import { fetchTools } from "@/lib/api";

// The directory changes infrequently and is safe to serve from Azure's edge.
// Keeping it out of the managed SSR runtime avoids cold-start 503s while the
// short revalidation window still makes admin changes visible promptly.
export const revalidate = 15;

export const metadata: Metadata = {
  title: "Free Online Tools for Pakistan | Pakistan Jobs Market",
  description: "Use free Pakistan salary and tax calculators, student tools, resume and cover-letter builders, and secure document utilities in one practical hub.",
  keywords: [
    "free online tools Pakistan",
    "Pakistan tax calculator",
    "government salary calculator Pakistan",
    "CGPA calculator Pakistan",
    "resume builder Pakistan",
    "PDF DOCX converter",
  ],
  alternates: { canonical: "/tools" },
  robots: { index: true, follow: true },
  openGraph: {
    title: "Free Calculators and Career Tools for Pakistan",
    description: "Practical salary, study, career and document tools built for users in Pakistan.",
    url: "/tools",
    type: "website",
  },
};

export default async function ToolsPage() {
  const categories = await fetchTools();
  return (
    <div className="tools-page-shell">
      <header className="tools-page-hero site-wrap">
        <p className="tool-kicker">Practical utilities · one place</p>
        <h1>Other Tools</h1>
        <p>Pick a branch and open a calculator or utility built for everyday work and study in Pakistan.</p>
      </header>
      <div className="site-wrap">
        {categories.length ? <ToolsConstellation categories={categories} /> : <div className="card-panel p-10 text-center text-[var(--muted)]">No tool categories are published yet.</div>}
      </div>
      <section className="tools-seo-content site-wrap" aria-labelledby="tools-guide-title">
        <div className="tools-seo-intro">
          <p className="tool-kicker">Built for practical decisions</p>
          <h2 id="tools-guide-title">Free calculators and career tools for Pakistan</h2>
          <p>
            Pakistan Jobs Market brings common work, study and document tasks into one free online tools directory. Instead of searching across unrelated websites, you can estimate income tax, review a government salary breakdown, calculate a university CGPA, prepare application documents and convert files from a single, mobile-friendly place. Each calculator explains its assumptions so you can understand the result rather than treating an estimate as official advice.
          </p>
          <p>
            Start with the tool category that matches your goal. Salary tools support job-offer and payscale comparisons; student tools help organize academic and early-career applications; document utilities handle everyday file tasks. The directory is updated as new tools are published, and each tool has its own permanent page that can be bookmarked and shared.
          </p>
        </div>

        {categories.length > 0 && (
          <div className="tools-seo-directory" aria-label="Available tool categories">
            {categories.map((category) => (
              <article key={category.id}>
                <p>{category.tools.length} {category.tools.length === 1 ? "tool" : "tools"}</p>
                <h3><Link href={`/tools/categories/${category.slug}`}>{category.title}</Link></h3>
                {category.content ? (
                  <div className="tools-seo-category-copy" dangerouslySetInnerHTML={{ __html: category.content }} />
                ) : (
                  <span>Explore free utilities in {category.title.toLowerCase()}.</span>
                )}
                {category.tools.length > 0 && (
                  <ul>
                    {category.tools.map((tool) => (
                      <li key={tool.id}><Link href={`/tools/${tool.slug}`}>{tool.title}</Link></li>
                    ))}
                  </ul>
                )}
              </article>
            ))}
          </div>
        )}

        <div className="tools-seo-guide">
          <div>
            <h3>How to use the results responsibly</h3>
            <p>
              Calculator results are estimates based on the information you enter and the published rules or schedules cited on each page. Tax, salary and allowance outcomes can change with a financial year, employer, posting, deductions or an individual appointment. Always compare an estimate with the latest official notification, payslip, university policy or recruiting organization before making a financial or academic decision.
            </p>
          </div>
          <div>
            <h3>Move from calculation to application</h3>
            <p>
              Once you understand the numbers, continue with the <Link href="/tools/resume-builder">Resume Builder</Link> or <Link href="/tools/cover-letter">Cover Letter Builder</Link>. You can also browse <Link href="/">latest jobs in Pakistan</Link>, explore vacancies by <Link href="/jobs-by-cities">city</Link>, or read evidence-based advice in the <Link href="/blog">career guides</Link>. These resources connect practical tools with real opportunities without changing the facts in a job advertisement.
            </p>
          </div>
          <div>
            <h3>Privacy and document safety</h3>
            <p>
              Client-side calculators run from the values entered in your browser. Where a tool must process an uploaded document, its page states the accepted file types, size limit and processing safeguards before upload. Avoid placing unnecessary sensitive information in any document, download the finished file promptly, and review it before submitting it to an employer or institution.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
