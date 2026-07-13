import Link from "next/link";

type Props = {
  page: number;
  pages: number;
  total: number;
  query: Record<string, string | undefined>;
  basePath?: string;
};

export function Pagination({ page, pages, total, query, basePath = "/" }: Props) {
  const hrefFor = (p: number) => {
    const params = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    params.set("page", String(p));
    return `${basePath}?${params.toString()}`;
  };

  return (
    <div className="px-4 py-4 flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-[var(--border)] text-sm">
      <span className="text-[var(--muted)]">
        {total} job{total === 1 ? "" : "s"}
        {pages > 1 ? ` · Page ${page} of ${pages}` : ""}
      </span>
      {pages > 1 && (
        <div className="flex gap-2">
          {page > 1 ? (
            <Link href={hrefFor(page - 1)} className="btn btn-ghost h-8 px-3 text-xs">
              ← Prev
            </Link>
          ) : (
            <span className="btn btn-ghost h-8 px-3 text-xs opacity-40 pointer-events-none">
              ← Prev
            </span>
          )}
          {page < pages ? (
            <Link href={hrefFor(page + 1)} className="btn btn-ghost h-8 px-3 text-xs">
              Next →
            </Link>
          ) : (
            <span className="btn btn-ghost h-8 px-3 text-xs opacity-40 pointer-events-none">
              Next →
            </span>
          )}
        </div>
      )}
    </div>
  );
}
