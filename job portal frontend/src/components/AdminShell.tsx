"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAdminAuth } from "@/lib/adminAuth";
import { AdminRouteLink } from "@/components/AdminRouteLink";

const LINKS = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/jobs", label: "Job posts" },
  { href: "/admin/jobs/new", label: "Create job" },
  { href: "/admin/blog", label: "Blog posts" },
  { href: "/admin/blog/new", label: "Create blog post" },
  { href: "/admin/taxonomy", label: "Tags / categories" },
  { href: "/admin/pages", label: "Pages" },
  { href: "/admin/pages/new", label: "Create page" },
  { href: "/admin/messages", label: "Messages" },
  { href: "/admin/analytics", label: "Site analytics" },
  { href: "/admin/seo", label: "SEO monitor" },
  { href: "/admin/newsletter", label: "Newsletter subscription" },
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

  useEffect(() => {
    if (ready && !token && pathname !== "/login") {
      router.replace("/login");
    }
  }, [pathname, ready, router, token]);

  if (!ready) {
    return <div className="site-wrap py-10 text-[var(--muted)]">Loading…</div>;
  }

  if (!token && pathname !== "/login") {
    return <div className="site-wrap py-10 text-[var(--muted)]">Redirecting to login…</div>;
  }

  function isActive(href: string) {
    if (href === "/admin") return pathname === "/admin";
    if (href === "/admin/jobs") return pathname === "/admin/jobs";
    if (href === "/admin/pages") return pathname === "/admin/pages";
    if (href === "/admin/blog") return pathname === "/admin/blog";
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
          <AdminRouteLink href="/" className="btn btn-ghost">
            View site
          </AdminRouteLink>
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
            <AdminRouteLink
              key={l.href}
              href={l.href}
              className={isActive(l.href) ? "active" : ""}
              onClick={() => setNavOpen(false)}
            >
              {l.label}
            </AdminRouteLink>
          ))}
        </aside>
        <div className="admin-content min-w-0">{children}</div>
      </div>
    </div>
  );
}
