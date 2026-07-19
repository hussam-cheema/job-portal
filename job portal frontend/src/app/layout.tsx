import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AdminDashboardLink } from "@/components/AdminDashboardLink";
import { SocialFooterIcons } from "@/components/SocialFooterIcons";
import { VisitTracker } from "@/components/VisitTracker";
import { ClientChunkRecovery } from "@/components/ClientChunkRecovery";
import { ClientErrorReporter } from "@/components/ClientErrorReporter";
import { UiIcon } from "@/components/UiIcon";
import { fetchBranding } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: {
    default: "PakJobs — Jobs in Pakistan",
    template: "%s | PakJobs",
  },
  description:
    "Modern job portal for Pakistan — government and private openings with commonly asked interview QnA.",
  keywords: [
    "Pakistan jobs",
    "government jobs",
    "private jobs",
    "FPSC",
    "PPSC",
    "careers Pakistan",
  ],
  openGraph: {
    title: "PakJobs — Jobs in Pakistan",
    description: "Browse government and private job openings across Pakistan.",
    type: "website",
    siteName: "PakJobs",
  },
  robots: { index: true, follow: true },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const branding = await fetchBranding();
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('pakjobs-theme');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t);}else if(window.matchMedia('(prefers-color-scheme: light)').matches){document.documentElement.setAttribute('data-theme','light');}}catch(e){}})();`,
          }}
        />
      </head>
      <body className="antialiased font-sans">
        <ClientChunkRecovery />
        <ClientErrorReporter />
        <div className="min-h-screen flex flex-col">
          <header className="site-header">
            <div className="site-wrap site-header-inner">
              <Link href="/" className="site-logo group" aria-label={`${branding.site_name} home`}>
                {branding.logo_url ? (
                  <Image
                    src={branding.logo_url}
                    alt={`${branding.site_name} logo`}
                    width={42}
                    height={42}
                    unoptimized
                    className="h-10 w-10 shrink-0 rounded-xl object-contain"
                  />
                ) : (
                  <span className="logo-mark flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#6d9cff] to-[#3658b8] text-sm font-extrabold shadow-lg shadow-blue-900/30">
                    PJ
                  </span>
                )}
              </Link>
              <Link
                href="/"
                className={`${
                  branding.site_title_alignment === "beside_logo"
                    ? "justify-self-start text-left"
                    : branding.site_title_alignment === "right"
                      ? "justify-self-end text-right"
                      : "justify-self-center text-center"
                } site-title min-w-0 truncate whitespace-nowrap`}
              >
                {branding.site_title}
              </Link>
              <nav className="site-actions" aria-label="Primary navigation">
                <AdminDashboardLink />
                <Link href="/blog" className="site-action" title="Read the blog">
                  <span className="site-action-icon"><UiIcon name="blog" /></span>
                  <span className="site-action-label">Blog</span>
                </Link>
                <Link
                  href="/resume-builder"
                  className="site-action"
                  title="Build your resume"
                >
                  <span className="site-action-icon"><UiIcon name="resume" /></span>
                  <span className="site-action-label"><span className="sm:hidden">Resume</span><span className="hidden sm:inline">Resume Builder</span></span>
                </Link>
                <Link
                  href="/cover-letter"
                  className="site-action"
                  title="Build your cover letter"
                >
                  <span className="site-action-icon"><UiIcon name="letter" /></span>
                  <span className="site-action-label"><span className="sm:hidden">Letter</span><span className="hidden sm:inline">Cover Letter</span></span>
                </Link>
                <ThemeToggle />
              </nav>
            </div>
          </header>

          <main className="flex-1">{children}</main>
          <VisitTracker />

          <footer className="border-t border-[var(--border)] mt-10 sm:mt-16 bg-[var(--footer-bg)]">
            <div className="site-wrap py-8 sm:py-10">
              <div className="flex flex-col md:flex-row gap-6 md:items-start md:justify-between">
                <div className="max-w-md">
                  <p className="font-semibold text-[var(--navy-100)]">{branding.site_title}</p>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    {branding.site_description}
                  </p>
                  <SocialFooterIcons />
                </div>
                <nav className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
                  <Link href="/about" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">
                    About us
                  </Link>
                  <Link href="/contact" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">
                    Contact us
                  </Link>
                  <Link href="/privacy" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">
                    Privacy policy
                  </Link>
                  <Link href="/disclaimer" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">
                    Disclaimer
                  </Link>
                </nav>
              </div>
              <p className="mt-8 text-center text-xs text-[var(--navy-500)]">
                {branding.footer_copyright.replace("{year}", String(new Date().getFullYear()))}
              </p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
