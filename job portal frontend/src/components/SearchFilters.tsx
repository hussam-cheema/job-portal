"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState, useTransition } from "react";
import type { FiltersResponse } from "@/lib/types";

type Props = {
  filters: FiltersResponse;
};

export function SearchFilters({ filters }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const [q, setQ] = useState(searchParams.get("q") || "");

  const update = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) params.set(key, value);
      else params.delete(key);
      if (key !== "page") params.delete("page");
      startTransition(() => {
        router.push(`/?${params.toString()}`);
      });
    },
    [router, searchParams]
  );

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault();
    update("q", q.trim());
  };

  const clear = () => {
    setQ("");
    startTransition(() => router.push("/"));
  };

  const hasFilters = [...searchParams.keys()].some((k) => k !== "page");

  return (
    <div className="space-y-3">
      <form onSubmit={onSearch} className="flex gap-2">
        <input
          className="input"
          placeholder="Search titles, companies, cities…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search jobs"
        />
        <button type="submit" className="btn btn-primary shrink-0" disabled={pending}>
          Search
        </button>
      </form>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <select
          className="select"
          value={searchParams.get("source_type") || ""}
          onChange={(e) => update("source_type", e.target.value)}
        >
          <option value="">All sources</option>
          {filters.source_types.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={searchParams.get("category") || ""}
          onChange={(e) => update("category", e.target.value)}
        >
          <option value="">All categories</option>
          {filters.categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={searchParams.get("city") || ""}
          onChange={(e) => update("city", e.target.value)}
        >
          <option value="">All cities</option>
          {filters.cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={searchParams.get("employment_type") || ""}
          onChange={(e) => update("employment_type", e.target.value)}
        >
          <option value="">All types</option>
          {filters.employment_types.map((t) => (
            <option key={t} value={t}>
              {t.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      {hasFilters && (
        <button type="button" onClick={clear} className="btn btn-ghost text-xs h-8 px-3">
          Clear filters
        </button>
      )}
    </div>
  );
}
