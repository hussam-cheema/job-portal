"use client";

import { useEffect } from "react";

export default function AdminError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    console.error("Admin route failed", error);
  }, [error]);

  return (
    <div className="site-wrap py-12">
      <div className="card-panel p-6">
        <h1 className="text-2xl font-semibold text-[var(--navy-100)]">
          This dashboard page could not be loaded
        </h1>
        <p className="mt-3 text-sm text-[var(--danger)]">
          The page assets or data request may have changed during a deployment. Reload to use the
          latest application version.
        </p>
        <button
          type="button"
          className="btn btn-primary mt-5"
          onClick={() => window.location.reload()}
        >
          Reload dashboard page
        </button>
      </div>
    </div>
  );
}
