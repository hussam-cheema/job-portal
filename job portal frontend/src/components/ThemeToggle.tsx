"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const stored = (localStorage.getItem("pakjobs-theme") as Theme | null) || null;
      const preferred =
        stored ||
        (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
      apply(preferred);
      setTheme(preferred);
    } catch {
      apply("dark");
    }
    setReady(true);
  }, []);

  function apply(next: Theme) {
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("pakjobs-theme", next);
    } catch {
      /* ignore */
    }
  }

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    apply(next);
  }

  if (!ready) {
    return (
      <button type="button" className="theme-toggle" aria-label="Toggle theme" disabled>
        ··
      </button>
    );
  }

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      title={theme === "dark" ? "Light mode" : "Dark mode"}
    >
      {theme === "dark" ? "☀ Light" : "☾ Dark"}
    </button>
  );
}
