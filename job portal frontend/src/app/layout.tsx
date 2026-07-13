import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AdminDashboardLink } from "@/components/AdminDashboardLink";
import { SocialFooterIcons } from "@/components/SocialFooterIcons";
import { VisitTracker } from "@/components/VisitTracker";
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
        <div className="min-h-screen flex flex-col">
          <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--header-bg)] backdrop-blur-xl">
            <div className="site-wrap min-h-14 py-2 flex items-center justify-between gap-2">
              <Link href="/" className="flex items-center gap-2 sm:gap-2.5 group min-w-0">
                {branding.logo_url ? (
                  <Image
                    src={branding.logo_url}
                    alt={`${branding.site_name} logo`}
                    width={32}
                    height={32}
                    unoptimized
                    className="h-8 w-8 shrink-0 rounded object-contain"
                  />
                ) : (
                  <span className="logo-mark flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-[#5b8def] to-[#2f4f9a] text-sm font-bold shadow-md shadow-blue-900/30">
                    PJ
                  </span>
                )}
                <div className="leading-tight min-w-0">
                  <div className="font-semibold tracking-tight text-[var(--navy-100)] group-hover:text-[var(--accent)] transition-colors truncate">
                    {branding.site_name}
                  </div>
                  <div className="text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] hidden xs:block sm:block">
                    Jobs in Pakistan
                  </div>
                </div>
              </Link>
              <nav className="flex items-center gap-1.5 sm:gap-2 text-sm shrink-0">
                <AdminDashboardLink />
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
                  <p className="font-semibold text-[var(--navy-100)]">PakJobs</p>
                  <p className="mt-1 text-sm text-[var(--muted)]">
                    Government & private job openings across Pakistan — curated manually with interview QnA.
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
                </nav>
              </div>
              <p className="mt-8 text-xs text-[var(--navy-500)]">
                © {new Date().getFullYear()} PakJobs
              </p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
