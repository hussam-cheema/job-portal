"use client";

import { AdminShell } from "@/components/AdminShell";
import { AdminRouteLink } from "@/components/AdminRouteLink";
import { UiIcon, type UiIconName } from "@/components/UiIcon";

const ACTIONS: Array<{ href: string; label: string; description: string; icon: UiIconName; primary?: boolean }> = [
  { href: "/admin/jobs/new", label: "Create job post", description: "Publish a new opportunity", icon: "briefcase", primary: true },
  { href: "/admin/blog/new", label: "Create blog post", description: "Write an SEO-ready article", icon: "blog", primary: true },
  { href: "/admin/pages/new", label: "Create page", description: "Add a public CMS page", icon: "page", primary: true },
  { href: "/admin/jobs", label: "Manage jobs", description: "Review, edit or remove jobs", icon: "briefcase" },
  { href: "/admin/blog", label: "Manage blog posts", description: "Organize published articles", icon: "article" },
  { href: "/admin/pages", label: "Manage pages", description: "Maintain website content", icon: "page" },
  { href: "/admin/messages", label: "Contact messages", description: "Read audience enquiries", icon: "mail" },
  { href: "/admin/analytics", label: "Site analytics", description: "Track real-time visitors", icon: "analytics" },
  { href: "/admin/infrastructure", label: "Infrastructure analytics", description: "Monitor capacity and cloud costs", icon: "analytics" },
  { href: "/admin/seo", label: "SEO monitor", description: "Improve search visibility", icon: "search" },
  { href: "/admin/newsletter", label: "Newsletter subscription", description: "Manage job-alert subscribers", icon: "letter" },
  { href: "/admin/taxonomy", label: "Tags / categories", description: "Keep taxonomy consistent", icon: "tags" },
  { href: "/admin/cities", label: "Cities", description: "Manage job city options", icon: "tags" },
  { href: "/admin/tools", label: "Other Tools", description: "Manage tool categories and pages", icon: "tools" },
  { href: "/admin/tools-analytics", label: "Tools Analytics", description: "See monthly use of every tool", icon: "analytics" },
  { href: "/admin/settings", label: "Settings", description: "Branding and account options", icon: "settings" },
];

export default function AdminHome() {
  return (
    <AdminShell>
      <div className="admin-dashboard-home space-y-6">
        <section className="admin-welcome">
          <div>
            <span className="admin-welcome-kicker"><span /> Control center</span>
            <h2>Dashboard</h2>
            <p>Create content, monitor growth and manage the complete Pakistan Jobs Market experience.</p>
          </div>
          <div className="admin-welcome-art" aria-hidden="true"><UiIcon name="dashboard" /></div>
        </section>

        <section>
          <div className="admin-section-heading">
            <div><p>Everything in one place</p><h3>Quick actions</h3></div>
            <span>{ACTIONS.length} tools</span>
          </div>
          <div className="admin-action-grid">
            {ACTIONS.map((action) => (
              <AdminRouteLink key={action.href} href={action.href} aria-label={action.label} className={`admin-action-card${action.primary ? " admin-action-primary" : ""}`}>
                <span className="admin-action-icon"><UiIcon name={action.icon} /></span>
                <span className="admin-action-copy"><strong>{action.label}</strong><small>{action.description}</small></span>
                <span className="admin-action-arrow" aria-hidden="true">→</span>
              </AdminRouteLink>
            ))}
          </div>
        </section>
      </div>
    </AdminShell>
  );
}
