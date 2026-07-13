"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAdminAuth } from "@/lib/adminAuth";

const LINKS = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/jobs", label: "Job posts" },
  { href: "/admin/jobs/new", label: "Create job" },
  { href: "/admin/pages", label: "Pages" },
  { href: "/admin/pages/new", label: "Create page" },
  { href: "/admin/messages", label: "Messages" },
  { href: "/admin/analytics", label: "Site analytics" },
  { href: "/admin/seo", label: "SEO monitor" },
  { href: "/admin/settings", label: "Settings" },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const { token, username, ready, logout } = useAdminAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [navOpen, setNavOpen] = useState(false);

  // Close mobile nav on route change
  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  if (!ready) {
    return <div className="site-wrap py-10 text-[var(--muted)]">Loading…</div>;
  }

  if (!token && pathname !== "/login") {
    if (typeof window !== "undefined") router.replace("/login");
    return <div className="site-wrap py-10 text-[var(--muted)]">Redirecting to login…</div>;
  }

  function isActive(href: string) {
    if (href === "/admin") return pathname === "/admin";
    if (href === "/admin/jobs") return pathname === "/admin/jobs";
    if (href === "/admin/pages") return pathname === "/admin/pages";
    return pathname === href || pathname.startsWith(href + "/");
  }

  function toggleNav(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setNavOpen((v) => !v);
  }

  return (
    <div className="site-wrap py-4 sm:py-8">
      <div className="mb-4 sm:mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start justify-between gap-3 w-full sm:w-auto">
          <div>
            <h1 className="text-xl sm:text-2xl font-semibold text-[var(--navy-100)]">Admin panel</h1>
            <p className="text-sm text-[var(--muted)]">Signed in as {username || "admin"}</p>
          </div>
          <button
            type="button"
            className="admin-menu-toggle btn btn-ghost shrink-0"
            onClick={toggleNav}
            aria-expanded={navOpen}
            aria-controls="admin-side-nav"
            aria-label={navOpen ? "Close admin menu" : "Open admin menu"}
          >
            {navOpen ? "Close" : "Menu"}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/" className="btn btn-ghost">
            View site
          </Link>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              logout();
              router.push("/login");
            }}
          >
            Logout
          </button>
        </div>
      </div>

      <div className="admin-shell">
        <aside
          id="admin-side-nav"
          className={`admin-nav${navOpen ? " admin-nav-open" : ""}`}
        >
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={isActive(l.href) ? "active" : ""}
              onClick={() => setNavOpen(false)}
            >
              {l.label}
            </Link>
          ))}
        </aside>
        <div className="admin-content min-w-0">{children}</div>
      </div>
    </div>
  );
}
