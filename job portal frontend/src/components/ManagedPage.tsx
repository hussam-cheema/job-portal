import Link from "next/link";
import { fetchPage } from "@/lib/api";

type Props = {
  slug: string;
  fallbackTitle: string;
  fallbackContent: string;
};

/** Render an administrator-editable CMS page with a safe built-in fallback. */
export async function ManagedPage({ slug, fallbackTitle, fallbackContent }: Props) {
  const page = await fetchPage(slug);
  const title = page?.title || fallbackTitle;
  const content = page?.content || fallbackContent;

  return (
    <div className="site-wrap max-w-3xl py-12">
      <Link href="/" className="text-sm text-[var(--muted)] hover:text-[var(--navy-200)]">
        ← Jobs
      </Link>
      <article>
        <h1 className="mt-6 text-3xl font-semibold text-[var(--navy-100)]">{title}</h1>
        <div
          className="prose-job mt-6 text-[0.95rem] leading-relaxed text-[var(--navy-200)]"
          dangerouslySetInnerHTML={{ __html: content }}
        />
      </article>
    </div>
  );
}
