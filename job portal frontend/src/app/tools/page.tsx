import type { Metadata } from "next";
import { ToolsConstellation } from "@/components/ToolsConstellation";
import { fetchTools } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Free Online Tools for Pakistan | Pakistan Jobs Market",
  description: "Explore salary, tax, student, image and document tools made for people in Pakistan.",
  alternates: { canonical: "/tools" },
  robots: { index: true, follow: true },
};

export default async function ToolsPage() {
  const categories = await fetchTools();
  return (
    <div className="tools-page-shell">
      <header className="tools-page-hero site-wrap">
        <p className="tool-kicker">Practical utilities · one place</p>
        <h1>Other Tools</h1>
        <p>Pick a branch and open a calculator or utility built for everyday work and study in Pakistan.</p>
      </header>
      <div className="site-wrap">
        {categories.length ? <ToolsConstellation categories={categories} /> : <div className="card-panel p-10 text-center text-[var(--muted)]">No tool categories are published yet.</div>}
      </div>
    </div>
  );
}
