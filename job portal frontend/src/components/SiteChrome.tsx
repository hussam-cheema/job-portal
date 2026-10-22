"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { AdminDashboardLink } from "@/components/AdminDashboardLink";
import { SocialFooterIcons } from "@/components/SocialFooterIcons";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UiIcon } from "@/components/UiIcon";
import { VisitTracker } from "@/components/VisitTracker";
import { fetchBranding } from "@/lib/api";
import type { Branding } from "@/lib/types";

type Props = { children: ReactNode; initialBranding: Branding };

export function SiteChrome({ children, initialBranding }: Props) {
  const [branding, setBranding] = useState(initialBranding);

  useEffect(() => {
    let active = true;
    void fetchBranding().then((latestBranding) => {
      if (active) setBranding(latestBranding);
    });
    return () => { active = false; };
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="site-header">
        <div className="site-wrap site-header-inner">
          <Link href="/" className="site-logo group" aria-label={`${branding.site_name} home`}>
            <Image
              src={branding.logo_url || "/pakistan-jobs-market-logo.png"}
              alt={`${branding.site_name} logo`}
              width={42}
              height={42}
              priority
              loading="eager"
              fetchPriority="high"
              unoptimized
              className="h-10 w-10 shrink-0 rounded-xl object-contain"
            />
          </Link>
          <Link
            href="/"
            className={`${
              branding.site_title_alignment === "beside_logo"
                ? "justify-self-start text-left"
                : branding.site_title_alignment === "right"
                  ? "justify-self-end text-right"
                  : "justify-self-center text-center"
            } site-title`}
          >
            {branding.site_title}
          </Link>
          <nav className="site-actions" aria-label="Primary navigation">
            <AdminDashboardLink />
            <Link href="/dashboard" className="site-action" title="Pakistan job market dashboard">
              <span className="site-action-icon"><UiIcon name="analytics" /></span>
              <span className="site-action-label">Dashboard</span>
            </Link>
            <Link href="/blog" className="site-action" title="Read the blog">
              <span className="site-action-icon"><UiIcon name="blog" /></span>
              <span className="site-action-label">Blog</span>
            </Link>
            <Link href="/tools/resume-builder" className="site-action" title="Build your resume">
              <span className="site-action-icon"><UiIcon name="resume" /></span>
              <span className="site-action-label"><span className="sm:hidden">Resume</span><span className="hidden sm:inline">Resume Builder</span></span>
            </Link>
            <Link href="/tools/cover-letter" className="site-action" title="Build your cover letter">
              <span className="site-action-icon"><UiIcon name="letter" /></span>
              <span className="site-action-label"><span className="sm:hidden">Letter</span><span className="hidden sm:inline">Cover Letter</span></span>
            </Link>
            <Link href="/tools" className="site-action" title="Explore other tools">
              <span className="site-action-icon"><UiIcon name="tools" /></span>
              <span className="site-action-label"><span className="sm:hidden">Tools</span><span className="hidden sm:inline">Other Tools</span></span>
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
              <p className="mt-1 text-sm text-[var(--muted)]">{branding.site_description}</p>
              <SocialFooterIcons />
            </div>
            <nav className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
              <Link href="/browse" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">Browse all</Link>
              <Link href="/archive" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">Job archive</Link>
              <Link href="/about" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">About us</Link>
              <Link href="/contact" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">Contact us</Link>
              <Link href="/privacy" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">Privacy policy</Link>
              <Link href="/disclaimer" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">Disclaimer</Link>
              <Link href="/editorial-policy" className="text-[var(--navy-300)] hover:text-[var(--accent)] transition-colors">Editorial policy</Link>
            </nav>
          </div>
          <p className="mt-8 text-center text-xs text-[var(--navy-500)]">
            {branding.footer_copyright.replace("{year}", String(new Date().getFullYear()))}
          </p>
        </div>
      </footer>
    </div>
  );
}
