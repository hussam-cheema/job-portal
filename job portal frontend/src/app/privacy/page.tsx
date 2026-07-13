import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy | PakJobs — Pakistan Job Portal",
  description:
    "PakJobs privacy policy: how we handle public job listings, contact messages, and technical logs. We do not sell personal data.",
  keywords: ["PakJobs privacy", "privacy policy", "Pakistan job portal privacy"],
  alternates: { canonical: "/privacy" },
  openGraph: {
    title: "Privacy Policy | PakJobs",
    description: "How PakJobs handles data for job listings and contact messages.",
    type: "website",
    url: "/privacy",
  },
  robots: { index: true, follow: true },
};

export default function PrivacyPage() {
  return (
    <div className="site-wrap max-w-3xl py-12">
      <Link href="/" className="text-sm text-[var(--muted)] hover:text-[var(--navy-200)]">
        ← Jobs
      </Link>
      <article>
        <h1 className="mt-6 text-3xl font-semibold text-[var(--navy-100)]">Privacy policy</h1>
        <div className="mt-6 space-y-4 text-[var(--navy-200)] leading-relaxed text-[0.95rem]">
          <p>
            PakJobs displays publicly available job advertisements collected from third-party
            sources (newspapers, company sites, and government portals).
          </p>
          <p>
            We do not sell personal data. If you contact us by email, we use your message only to
            respond. Server logs may include standard technical data (IP, user agent) for security
            and reliability.
          </p>
          <p>
            Job listings may include employer contact details published by the source. Use those
            details only for legitimate applications.
          </p>
          <p>
            This policy may be updated as the product evolves. Continued use of the site means you
            accept the latest version.
          </p>
          <p>
            Contact:{" "}
            <a className="text-[var(--accent)] hover:underline" href="mailto:coms.copp@gmail.com">
              coms.copp@gmail.com
            </a>
          </p>
        </div>
      </article>
    </div>
  );
}
