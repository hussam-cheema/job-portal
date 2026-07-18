"use client";

import { useEffect, useMemo, useState } from "react";

type Props = {
  path: string;
  title: string;
};

type ShareTarget = {
  label: string;
  href: (url: string, title: string) => string;
  icon: React.ReactNode;
};

const targets: ShareTarget[] = [
  {
    label: "WhatsApp",
    href: (url, title) =>
      `https://wa.me/?text=${encodeURIComponent(`${title}\n${url}`)}`,
    icon: <span aria-hidden="true" className="font-bold">WA</span>,
  },
  {
    label: "Facebook",
    href: (url) =>
      `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,
    icon: <span aria-hidden="true" className="font-bold">f</span>,
  },
  {
    label: "X",
    href: (url, title) =>
      `https://x.com/intent/post?text=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`,
    icon: <span aria-hidden="true" className="font-bold">X</span>,
  },
];

function initialShareUrl(path: string): string {
  try {
    const configuredBase = (process.env.NEXT_PUBLIC_SITE_URL || "").replace(/\/$/, "");
    return configuredBase ? `${configuredBase}${path}` : path;
  } catch (error) {
    console.error("Unable to build the configured job share URL", error);
    return path;
  }
}

export function JobShareButtons({ path, title }: Props) {
  const [shareUrl, setShareUrl] = useState(() => initialShareUrl(path));

  useEffect(() => {
    try {
      const currentUrl = new URL(window.location.href);
      currentUrl.hash = "";
      setShareUrl(currentUrl.toString());
    } catch (error) {
      // The configured canonical URL remains usable when browser URL parsing fails.
      console.error("Unable to read the current job URL for sharing", error);
    }
  }, []);

  const links = useMemo(
    () =>
      targets.map((target) => ({
        ...target,
        shareHref: target.href(shareUrl, title),
      })),
    [shareUrl, title]
  );

  return (
    <section className="mt-5 border-t border-[var(--border)] pt-4" aria-labelledby="share-job-title">
      <h2
        id="share-job-title"
        className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--navy-400)]"
      >
        Share this job
      </h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {links.map((target) => (
          <a
            key={target.label}
            href={target.shareHref}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Share on ${target.label}`}
            className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--navy-850)] px-4 py-2 text-sm font-medium text-[var(--navy-200)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
          >
            <span className="flex h-5 min-w-5 items-center justify-center text-xs">
              {target.icon}
            </span>
            {target.label}
          </a>
        ))}
      </div>
    </section>
  );
}
