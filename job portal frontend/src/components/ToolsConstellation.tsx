"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import type { ToolCategory } from "@/lib/types";

function hueFor(index: number) {
  return Math.round((index * 137.508 + 252) % 360);
}

function CategoryGlyph({ name }: { name: string }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (name === "coins") return <svg viewBox="0 0 24 24" {...common}><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v5c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 11v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/></svg>;
  if (name === "graduation") return <svg viewBox="0 0 24 24" {...common}><path d="m2 9 10-5 10 5-10 5Z"/><path d="M6 11v5c3 3 9 3 12 0v-5M22 9v7"/></svg>;
  if (name === "image") return <svg viewBox="0 0 24 24" {...common}><rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m4 17 5-5 4 4 2-2 5 5"/></svg>;
  if (name === "document") return <svg viewBox="0 0 24 24" {...common}><path d="M6 3h9l4 4v14H6zM15 3v5h5M9 12h6M9 16h6"/></svg>;
  return <svg viewBox="0 0 24 24" {...common}><path d="m12 2 1.4 5.1L18 4l-3.1 4.6L20 10l-5.1 1.4L18 16l-4.6-3.1L12 18l-1.4-5.1L6 16l3.1-4.6L4 10l5.1-1.4L6 4l4.6 3.1Z"/></svg>;
}

export function ToolsConstellation({ categories }: { categories: ToolCategory[] }) {
  const count = Math.max(categories.length, 1);
  const points = categories.map((category, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / count;
    return {
      category,
      x: 50 + Math.cos(angle) * 39,
      y: 50 + Math.sin(angle) * 38,
      hue: hueFor(category.color_index),
    };
  });

  return (
    <section className="tools-constellation" aria-label="Tools by category">
      <svg className="tools-constellation-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <circle cx="50" cy="50" r="17" className="tools-orbit-ring" />
        <circle cx="50" cy="50" r="13" className="tools-orbit-ring tools-orbit-dashed" />
        {points.map(({ category, x, y, hue }, index) => {
          const bendX = (50 + x) / 2 + (index % 2 ? 3 : -3);
          const bendY = (50 + y) / 2;
          return <path key={category.id} d={`M50 50 Q${bendX} ${bendY} ${x} ${y}`} style={{ stroke: `hsl(${hue} 88% 58%)` }} />;
        })}
      </svg>

      <div className="tools-hub-center"><span>TOOLS</span><small>Made for Pakistan</small></div>

      {points.map(({ category, x, y, hue }) => (
        <article
          key={category.id}
          className="tool-branch-card"
          style={{
            "--branch-x": `${x}%`,
            "--branch-y": `${y}%`,
            "--branch-hue": hue,
          } as CSSProperties}
        >
          <div className="tool-branch-icon"><CategoryGlyph name={category.icon_key} /></div>
          <div className="tool-branch-copy">
            <Link href={`/tools/categories/${category.slug}`} className="tool-branch-title">
              {category.title}
            </Link>
            <div className="tool-branch-links">
              {category.tools.length ? category.tools.map((tool) => (
                <Link key={tool.id} href={`/tools/${tool.slug}`}><span aria-hidden="true">•</span>{tool.title}</Link>
              )) : <span className="tool-coming-soon">Tools coming soon</span>}
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}
