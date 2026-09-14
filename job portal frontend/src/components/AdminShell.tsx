"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAdminAuth } from "@/lib/adminAuth";
import { AdminRouteLink } from "@/components/AdminRouteLink";
import { UiIcon, type UiIconName } from "@/components/UiIcon";

const LINKS: Array<{ href: string; label: string; icon: UiIconName; group: string }> = [
  { href: "/admin", label: "Dashboard", icon: "dashboard", group: "Overview" },
  { href: "/admin/jobs", label: "Job posts", icon: "briefcase", group: "Publishing" },
  { href: "/admin/jobs/new", label: "Create job", icon: "plus", group: "Publishing" },
  { href: "/admin/blog", label: "Blog posts", icon: "blog", group: "Publishing" },
  { href: "/admin/blog/new", label: "Create blog post", icon: "plus", group: "Publishing" },
  { href: "/admin/taxonomy", label: "Tags / categories", icon: "tags", group: "Content" },
  { href: "/admin/cities", label: "Cities", icon: "tags", group: "Content" },
  { href: "/admin/tools", label: "Other Tools", icon: "tools", group: "Content" },
  { href: "/admin/tools-analytics", label: "Tools Analytics", icon: "analytics", group: "Content" },
  { href: "/admin/pages", label: "Pages", icon: "page", group: "Content" },
  { href: "/admin/pages/new", label: "Create page", icon: "plus", group: "Content" },
  { href: "/admin/messages", label: "Messages", icon: "mail", group: "Audience" },
  { href: "/admin/analytics", label: "Site analytics", icon: "analytics", group: "Audience" },
  { href: "/admin/infrastructure", label: "Infrastructure analytics", icon: "analytics", group: "System" },
  { href: "/admin/seo", label: "SEO monitor", icon: "search", group: "Growth" },
  { href: "/admin/newsletter", label: "Newsletter subscription", icon: "letter", group: "Growth" },
  { href: "/admin/settings", label: "Settings", icon: "settings", group: "System" },
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
    if (href === "/admin/tools") return pathname === "/admin/tools";
    return pathname === href || pathname.startsWith(href + "/");
  }

  function toggleNav(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setNavOpen((v) => !v);
  }

  return (
    <div className="site-wrap admin-layout py-5 sm:py-8">
      <div className="admin-topbar">
        <div className="flex items-center justify-between gap-3 w-full sm:w-auto">
          <div>
            <p className="admin-eyebrow">Content workspace</p>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--navy-100)]">Admin panel</h1>
              <span className="admin-user-chip"><span aria-hidden="true" />{username || "admin"}</span>
            </div>
          </div>
          <button
            type="button"
            className="admin-menu-toggle admin-icon-button shrink-0"
            onClick={toggleNav}
            aria-expanded={navOpen}
            aria-controls="admin-side-nav"
            aria-label={navOpen ? "Close admin menu" : "Open admin menu"}
          >
            <UiIcon name={navOpen ? "close" : "menu"} />
            <span className="sr-only">{navOpen ? "Close" : "Menu"}</span>
          </button>
        </div>
        <div className="admin-topbar-actions">
          <AdminRouteLink href="/" className="btn btn-ghost">
            <UiIcon name="external" className="h-4 w-4" /> View site
          </AdminRouteLink>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              logout();
              router.push("/login");
            }}
          >
            <UiIcon name="logout" className="h-4 w-4" /> Logout
          </button>
        </div>
      </div>

      <div className="admin-shell">
        <aside
          id="admin-side-nav"
          className={`admin-nav${navOpen ? " admin-nav-open" : ""}`}
        >
          <div className="admin-nav-heading">
            <span className="admin-nav-mark"><UiIcon name="dashboard" /></span>
            <span><strong>Workspace</strong><small>Manage Pakistan Jobs Market</small></span>
          </div>
          {[...new Set(LINKS.map((link) => link.group))].map((group) => (
            <div className="admin-nav-section" key={group}>
              <p className="admin-nav-section-title">{group}</p>
              {LINKS.filter((link) => link.group === group).map((l) => (
                <AdminRouteLink
                  key={l.href}
                  href={l.href}
                  className={isActive(l.href) ? "active" : ""}
                  onClick={() => setNavOpen(false)}
                >
                  <span className="admin-nav-icon"><UiIcon name={l.icon} /></span>
                  <span>{l.label}</span>
                </AdminRouteLink>
              ))}
            </div>
          ))}
        </aside>
        <div className="admin-content min-w-0">{children}</div>
      </div>
    </div>
  );
}
