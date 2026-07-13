"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState, useTransition } from "react";
import type { FiltersResponse } from "@/lib/types";

type Props = {
  filters: FiltersResponse;
  basePath?: string;
};

export function JobFilters({ filters, basePath = "/" }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();
  const [q, setQ] = useState(searchParams.get("q") || "");

  const update = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      // migrate away from old range params
      params.delete("date_from");
      params.delete("date_to");
      if (value) params.set(key, value);
      else params.delete(key);
      if (key !== "page") params.delete("page");
      const qs = params.toString();
      startTransition(() => {
        router.push(qs ? `${basePath}?${qs}` : basePath);
      });
    },
    [router, searchParams, basePath]
  );

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault();
    update("q", q.trim());
  };

  const clear = () => {
    setQ("");
    startTransition(() => router.push(basePath));
  };

  const hasFilters = [...searchParams.keys()].some((k) => k !== "page");
  const day =
    searchParams.get("date") ||
    searchParams.get("date_from") ||
    "";

  return (
    <div className="space-y-3">
      <form onSubmit={onSearch} className="flex flex-col sm:flex-row gap-2">
        <input
          className="input"
          placeholder="Filter titles, companies, skills…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search jobs"
        />
        <button type="submit" className="btn btn-primary sm:shrink-0 w-full sm:w-auto" disabled={pending}>
          Search
        </button>
      </form>

      <div className="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        <select
          className="select"
          value={searchParams.get("city") || ""}
          onChange={(e) => update("city", e.target.value)}
          aria-label="City"
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
          value={searchParams.get("sector") || ""}
          onChange={(e) => update("sector", e.target.value)}
          aria-label="Sector"
        >
          <option value="">Govt & Private</option>
          <option value="govt">Government</option>
          <option value="private">Private</option>
        </select>

        <select
          className="select"
          value={searchParams.get("category") || ""}
          onChange={(e) => update("category", e.target.value)}
          aria-label="Category"
        >
          <option value="">All categories</option>
          {filters.categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        <input
          type="date"
          className="input"
          value={day}
          onChange={(e) => update("date", e.target.value)}
          aria-label="Filter by day"
          title="Filter by day"
        />
      </div>

      {hasFilters && (
        <button type="button" onClick={clear} className="btn btn-ghost text-xs h-8 px-3">
          Clear filters
        </button>
      )}
    </div>
  );
}
