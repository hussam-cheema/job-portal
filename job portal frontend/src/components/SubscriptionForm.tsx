"use client";

import { FormEvent, useState } from "react";
import { subscribeEmail } from "@/lib/api";

export function SubscriptionForm() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    const clean = email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(clean)) {
      setError("Enter a valid email address.");
      return;
    }
    setBusy(true);
    try {
      const result = await subscribeEmail(clean);
      setMessage(result.message);
      if (result.status === "subscribed") setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to subscribe right now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card-panel p-5 sm:p-6" aria-labelledby="job-alerts-heading">
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(20rem,1fr)] md:items-center">
        <div>
          <h2 id="job-alerts-heading" className="text-lg font-semibold text-[var(--navy-100)]">
            Subscribe to get daily Job alerts
          </h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Receive newly published PakistanJobs listings every day at 12:00 PM PKT.
          </p>
        </div>
        <form onSubmit={submit} noValidate>
          <div className="flex flex-col gap-2 sm:flex-row">
            <label className="sr-only" htmlFor="daily-alert-email">Email address</label>
            <input id="daily-alert-email" className="input flex-1" type="email" inputMode="email"
              autoComplete="email" maxLength={320} required value={email}
              onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "Subscribing…" : "Subscribe"}
            </button>
          </div>
          {message && <p className="mt-2 text-sm font-medium text-[var(--success)]">{message}</p>}
          {error && <p className="field-error mt-2">{error}</p>}
        </form>
      </div>
    </section>
  );
}
