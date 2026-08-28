import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import type { Metadata } from "next";
import { fetchBlogPosts, fetchBranding, fetchDirectoryPages, fetchJob, fetchJobs, fetchPublicSeo } from "@/lib/api";
import { JobShareButtons } from "@/components/JobShareButtons";
import {
  decodeHtmlEntities,
  formatDate,
  formatSalary,
  isDeadlinePast,
  labelSource,
  sourceBadgeClass,
  stripHtml,
  tagColorClass,
} from "@/lib/format";
import { toSeoSlug } from "@/lib/slug";
import { rewriteJobDescriptionImages } from "@/lib/media";
import { wrapRichTextTables } from "@/lib/richText";
import {
  compactSocialDescription,
  firstRichTextImage,
  selectSocialImage,
} from "@/lib/socialMetadata";
import { canonicalSiteUrl } from "@/lib/siteUrl";
import { buildJobPostingStructuredData } from "@/lib/jobStructuredData";
import { findDirectoryPage, publicPagePath } from "@/lib/pagePath";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Props = {
  params: Promise<{ id: string }>;
};

function externalHref(value: string) {
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const job = await fetchJob(id);
  if (!job) return { title: "Job | Pakistan Jobs Market" };
  const [branding, seo] = await Promise.all([
    fetchBranding(),
    fetchPublicSeo("job", job.id),
  ]);
  const canonicalPath = `/jobs/${job.slug || job.id}`;
  const fallbackDescription =
    compactSocialDescription(stripHtml(job.description || "")) ||
    `${decodeHtmlEntities(job.title)} at ${decodeHtmlEntities(job.company || job.source || "Pakistan Jobs Market")}`;
  const description =
    compactSocialDescription(seo?.meta_description || "") || fallbackDescription;
  const pageTitle =
    decodeHtmlEntities(seo?.meta_title?.trim() || `${job.title} | ${branding.site_name}`);
  const socialTitle =
    decodeHtmlEntities(seo?.og_title?.trim() || seo?.meta_title?.trim() || job.title);
  const renderedDescription = rewriteJobDescriptionImages(job.description || "");
  const inlineAttachment = (job.attachments || []).find(
    (attachment) =>
      attachment.is_inline_image &&
      /^image\//i.test(attachment.file_type || "") &&
      attachment.public_url,
  );
  const socialImage = selectSocialImage(
    seo?.og_image,
    firstRichTextImage(renderedDescription),
    inlineAttachment?.public_url,
    branding.logo_url,
  );

  return {
    title: { absolute: pageTitle },
    description,
    keywords: seo?.meta_keywords
      ?.split(",")
      .map((keyword) => keyword.trim())
      .filter(Boolean),
    alternates: { canonical: canonicalPath },
    robots: { index: true, follow: true },
    openGraph: {
      title: socialTitle,
      description: compactSocialDescription(seo?.og_description || "") || description,
      type: "article",
      url: canonicalPath,
      siteName: branding.site_name,
      publishedTime: job.published_date || job.created_at || undefined,
      images: [{ url: socialImage, alt: decodeHtmlEntities(job.title) }],
    },
    twitter: {
      card: "summary_large_image",
      title: socialTitle,
      description: compactSocialDescription(seo?.og_description || "") || description,
      images: [{ url: socialImage, alt: decodeHtmlEntities(job.title) }],
    },
  };
}

export default async function JobDetailPage({ params }: Props) {
  const { id } = await params;
  const job = await fetchJob(id);
  if (!job) notFound();
  if (job.slug && id !== job.slug) permanentRedirect(`/jobs/${job.slug}`);

  const discoveryTerm = job.category || job.tags?.[0] || job.cities?.[0];
  const [relatedResult, companyResult, articleResult, directoryPages] = await Promise.all([
    fetchJobs({ tag: discoveryTerm, page: 1, page_size: 6 }),
    job.source ? fetchJobs({ company: job.source, page: 1, page_size: 6 }) : Promise.resolve({ items: [], total: 0, page: 1, page_size: 6, pages: 0 }),
    fetchBlogPosts({ q: discoveryTerm || job.title.split(" ").slice(0, 2).join(" "), page: 1, page_size: 4 }),
    fetchDirectoryPages(),
  ]);
  const relatedJobs = relatedResult.items.filter((item) => item.id !== job.id).slice(0, 4);
  const companyJobs = companyResult.items.filter((item) => item.id !== job.id).slice(0, 4);
  const categoryPage = findDirectoryPage(directoryPages, "category", job.category);
  const companyPage = findDirectoryPage(directoryPages, "organization", job.source);

  const salary =
    job.salary_range ||
    formatSalary(job.salary_min, job.salary_max, job.currency, job.salary_range);
  const tags = Array.from(
    new Set(
      [
        ...(job.tags || []),
        ...(job.nationwide ? ["Pakistan"] : [...(job.provinces || []), ...(job.cities || [])]),
        ...(!job.tags?.length
          ? [
              labelSource(job.source_type || job.job_type || "private"),
              job.category,
              ...(job.skills || []),
            ]
          : []),
      ].filter(Boolean) as string[]
    )
  );

  const attachments = (job.attachments || []).filter((a) => !a.is_inline_image);
  const referenceUrl =
    job.reference_url ||
    (job.source_url && job.source_url !== job.application_url ? job.source_url : "");
  const applicationsClosed =
    job.applications_closed || isDeadlinePast(job.deadline_date || job.application_deadline);
  const jobUrl = `${canonicalSiteUrl()}/jobs/${job.slug || job.id}`;
  const structuredData = buildJobPostingStructuredData(job, jobUrl);

  return (
    <div className="site-wrap py-10">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(structuredData).replace(/</g, "\\u003c"),
        }}
      />
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--navy-200)] mb-8 transition-colors"
      >
        ← All jobs
      </Link>

      <article className="card-panel">
        <header className="px-5 sm:px-8 py-7 border-b border-[var(--border)]">
          <div className="flex flex-wrap gap-2 mb-4 relative z-10">
            <span className={`tag ${sourceBadgeClass(job.source_type || job.job_type || "")}`}>
              {labelSource(job.source_type || job.job_type || "private")}
            </span>
            {job.category && categoryPage ? (
              <Link
                href={publicPagePath(categoryPage)}
                className={`tag job-tag-link ${tagColorClass(job.category)}`}
              >
                {decodeHtmlEntities(job.category)}
              </Link>
            ) : job.category ? (
              <span className={`tag ${tagColorClass(job.category)}`}>
                {decodeHtmlEntities(job.category)}
              </span>
            ) : null}
            {tags
              .filter(
                (t) =>
                  t.toLowerCase() !==
                    labelSource(job.source_type || job.job_type || "").toLowerCase() &&
                  t.toLowerCase() !== (job.category || "").toLowerCase()
              )
              .map((t) => {
                const cityPage = findDirectoryPage(directoryPages, "city", t);
                const provincePage = findDirectoryPage(directoryPages, "province", t);
                const locationPage = cityPage || provincePage;
                const isLocation = [...(job.cities || []), ...(job.provinces || [])].includes(t);
                const href = isLocation
                  ? locationPage
                    ? publicPagePath(locationPage)
                    : null
                  : `/tags/${toSeoSlug(t)}`;
                return href ? (
                  <Link
                    key={t}
                    href={href}
                    className={`tag job-tag-link ${tagColorClass(t)}`}
                  >
                    {decodeHtmlEntities(t)}
                  </Link>
                ) : (
                  <span key={t} className={`tag ${tagColorClass(t)}`}>
                    {decodeHtmlEntities(t)}
                  </span>
                );
              })}
          </div>
          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[var(--navy-100)] leading-snug">
            {decodeHtmlEntities(job.title)}
          </h1>
          {applicationsClosed && (
            <div className="mt-4 inline-flex rounded-full border-2 border-red-500 bg-red-500/10 px-4 py-2 text-sm font-bold uppercase tracking-wide text-red-500">
              Applications Closed
            </div>
          )}
          <p className="mt-3 text-[var(--navy-300)] text-lg">
            {decodeHtmlEntities(job.company || job.source || "Unknown company")}
            {job.location ? (
              <span className="text-[var(--muted)]"> · {decodeHtmlEntities(job.location)}</span>
            ) : null}
          </p>
          <div className="mt-5 flex flex-wrap gap-x-6 gap-y-2 text-sm text-[var(--muted)]">
            <Meta label="Published" value={formatDate(job.published_date || job.created_at)} />
            <Meta
              label="Deadline"
              value={formatDate(job.deadline_date || job.application_deadline)}
              emphasize
            />
            {salary && <Meta label="Salary" value={salary} />}
            {(job.source_name || job.source) && (
              <Meta label="Source Organization" value={job.source_name || job.source || ""} />
            )}
            {job.newspaper && <Meta label="Newspaper" value={job.newspaper} />}
          </div>
          {(referenceUrl || (!applicationsClosed && job.application_url)) && (
            <div className="mt-4 space-y-2 border-t border-[var(--border)] pt-4 text-sm">
              {referenceUrl && (
                <div className="grid gap-1 sm:grid-cols-[14rem_minmax(0,1fr)]">
                  <span className="font-semibold text-[var(--navy-300)]">
                    Job Advertisement Reference URL:
                  </span>
                  <a
                    href={externalHref(referenceUrl)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all text-[var(--accent)] hover:underline"
                  >
                    {referenceUrl}
                  </a>
                </div>
              )}
              {!applicationsClosed && job.application_url && (
                <div className="grid gap-1 sm:grid-cols-[14rem_minmax(0,1fr)]">
                  <span className="font-semibold text-[var(--navy-300)]">Apply Here:</span>
                  <a
                    href={externalHref(job.application_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all text-[var(--accent)] hover:underline"
                  >
                    {job.application_url}
                  </a>
                </div>
              )}
            </div>
          )}
          <JobShareButtons
            path={`/jobs/${job.slug || job.id}`}
            title={decodeHtmlEntities(job.title)}
          />
        </header>

        <div className="px-5 sm:px-8 py-7">
          <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--navy-400)] mb-3">
            Description
          </h2>
          <div
            className="prose-job text-[0.95rem]"
            dangerouslySetInnerHTML={{
              __html: wrapRichTextTables(
                rewriteJobDescriptionImages(
                  job.description || "<p>No description provided.</p>"
                ),
              ),
            }}
          />

          {attachments.length > 0 && (
            <div className="mt-8">
              <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--navy-400)] mb-3">
                Attachments
              </h2>
              <ul className="space-y-2">
                {attachments.map((a) => (
                  <li key={a.id}>
                    <a
                      href={a.public_url || "#"}
                      download={a.original_name || true}
                      className="text-sm text-[var(--accent)] hover:underline"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {a.original_name || a.s3_path} ({Math.round((a.file_size || 0) / 1024)} KB)
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(job.experience_required || job.education_required) && (
            <div className="mt-8 grid sm:grid-cols-2 gap-4">
              {job.experience_required && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4">
                  <div className="text-xs uppercase tracking-wider text-[var(--muted)]">
                    Experience
                  </div>
                  <div className="mt-1 text-[var(--navy-100)]">{decodeHtmlEntities(job.experience_required)}</div>
                </div>
              )}
              {job.education_required && (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4">
                  <div className="text-xs uppercase tracking-wider text-[var(--muted)]">
                    Education
                  </div>
                  <Link href={`/qualifications/${toSeoSlug(job.education_required)}`} className="mt-1 block text-[var(--accent)] hover:underline">{decodeHtmlEntities(job.education_required)}</Link>
                </div>
              )}
            </div>
          )}

          {job.skills?.length > 0 && (
            <div className="mt-8">
              <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--navy-400)] mb-3">
                Skills
              </h2>
              <div className="flex flex-wrap gap-2">
                {job.skills.map((s) => (
                  <span key={s} className="badge badge-muted normal-case tracking-normal">
                    {decodeHtmlEntities(s)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {job.qna?.length > 0 && (
            <section className="mt-10 border-t border-[var(--border)] pt-8">
              <h2 className="text-xl font-semibold text-[var(--navy-100)]">
                Commonly asked Questions and Answers
              </h2>
              <div className="mt-5 space-y-4">
                {job.qna.map((item) => (
                  <article
                    key={item.id}
                    className="rounded-lg border border-[var(--border)] bg-[var(--navy-850)] p-4"
                  >
                    <h3 className="font-medium text-[var(--navy-100)]">{decodeHtmlEntities(item.question)}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-[var(--navy-200)]">
                      {decodeHtmlEntities(item.answer)}
                    </p>
                    {item.youtube_url && (
                      <a
                        href={item.youtube_url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-3 block break-all text-xs text-[var(--accent)] hover:underline"
                      >
                        YouTube reference: {item.youtube_url}
                      </a>
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}

          <section className="mt-10 border-t border-[var(--border)] pt-8" aria-labelledby="explore-related">
            <h2 id="explore-related" className="text-xl font-semibold text-[var(--navy-100)]">Explore related opportunities</h2>
            <div className="mt-5 grid gap-5 lg:grid-cols-2">
              {relatedJobs.length > 0 && <div><h3 className="font-semibold text-[var(--navy-200)]">Related vacancies</h3><ul className="mt-3 space-y-2">{relatedJobs.map((item) => <li key={item.id}><Link href={`/jobs/${item.slug || item.id}`} className="text-sm text-[var(--accent)] hover:underline">{decodeHtmlEntities(item.title)}</Link></li>)}</ul></div>}
              {companyJobs.length > 0 && <div><h3 className="font-semibold text-[var(--navy-200)]">More from {decodeHtmlEntities(job.source || "")}</h3><ul className="mt-3 space-y-2">{companyJobs.map((item) => <li key={item.id}><Link href={`/jobs/${item.slug || item.id}`} className="text-sm text-[var(--accent)] hover:underline">{decodeHtmlEntities(item.title)}</Link></li>)}</ul>{job.source && companyPage && <Link href={publicPagePath(companyPage)} className="mt-3 inline-flex text-sm text-[var(--muted)] hover:text-[var(--accent)]">View all {decodeHtmlEntities(job.source)} jobs →</Link>}</div>}
              {articleResult.items.length > 0 && <div><h3 className="font-semibold text-[var(--navy-200)]">Relevant career guides</h3><ul className="mt-3 space-y-2">{articleResult.items.map((post) => <li key={post.id}><Link href={`/blog/${post.slug}`} className="text-sm text-[var(--accent)] hover:underline">{decodeHtmlEntities(post.title)}</Link></li>)}</ul></div>}
              <div><h3 className="font-semibold text-[var(--navy-200)]">Application tools</h3><div className="mt-3 flex flex-wrap gap-2"><Link href="/tools/resume-builder" className="btn btn-ghost">ATS Resume Builder</Link><Link href="/tools/cover-letter" className="btn btn-ghost">Cover Letter Builder</Link><Link href="/browse" className="btn btn-ghost">Browse all</Link></div></div>
            </div>
          </section>
        </div>
      </article>
    </div>
  );
}

function Meta({
  label,
  value,
  emphasize = false,
}: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <div className={emphasize ? "font-bold text-red-500" : ""}>
      <span className={emphasize ? "text-red-500" : "text-[var(--navy-500)]"}>
        {label}:{" "}
      </span>
      <span className={emphasize ? "text-red-500" : "text-[var(--navy-200)]"}>
        {decodeHtmlEntities(value)}
      </span>
    </div>
  );
}
