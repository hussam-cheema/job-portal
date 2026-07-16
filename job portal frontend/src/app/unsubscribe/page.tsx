"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { unsubscribeEmail } from "@/lib/api";

function UnsubscribeContent() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [message, setMessage] = useState("Processing your request…");
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!token) {
      setMessage("This unsubscribe link is invalid.");
      setError(true);
      return;
    }
    unsubscribeEmail(token).then((result) => setMessage(result.message)).catch((err) => {
      setMessage(err instanceof Error ? err.message : "Unable to unsubscribe.");
      setError(true);
    });
  }, [token]);
  return (
    <div className="site-wrap py-12">
      <section className="card-panel mx-auto max-w-2xl p-7 text-center">
        <h1 className="text-2xl font-semibold text-[var(--navy-100)]">Daily job alerts</h1>
        <p className={`mt-4 text-sm ${error ? "text-[var(--danger)]" : "text-[var(--navy-200)]"}`}>{message}</p>
        <Link href="/" className="btn btn-primary mt-6">Return to jobs</Link>
      </section>
    </div>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={<div className="site-wrap py-12 text-[var(--muted)]">Processing your request…</div>}>
      <UnsubscribeContent />
    </Suspense>
  );
}
