"use client";

import { useEffect } from "react";

export default function ApplicationError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled application route error", error);
  }, [error]);

  return (
    <section className="site-wrap py-16" role="alert">
      <div className="card-panel mx-auto max-w-2xl p-8 text-center">
        <h1 className="text-2xl font-semibold text-[var(--navy-100)]">
          This page could not be loaded
        </h1>
        <p className="mt-3 text-[var(--muted)]">
          An unexpected error occurred. Your data was not changed. Please try again.
        </p>
        <button type="button" onClick={reset} className="btn-primary mt-6">
          Try again
        </button>
      </div>
    </section>
  );
}
