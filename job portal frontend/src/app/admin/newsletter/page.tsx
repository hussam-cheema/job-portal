"use client";

import { FormEvent, useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import {
  adminSendDigest,
  adminSubscriptionSummary,
  adminUpdateDigestTemplate,
} from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { DigestAdminSummary } from "@/lib/types";

export default function NewsletterSubscriptionPage() {
  const { token } = useAdminAuth();
  const [digest, setDigest] = useState<DigestAdminSummary | null>(null);
  const [form, setForm] = useState({ subject_template: "", body_template: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function reload() {
    if (!token) return;
    const value = await adminSubscriptionSummary(token);
    setDigest(value);
    setForm({
      subject_template: value.subject_template,
      body_template: value.body_template,
    });
  }

  useEffect(() => {
    reload().catch((err) => setError(err instanceof Error ? err.message : "Unable to load newsletter settings."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function saveTemplate(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const value = await adminUpdateDigestTemplate(token, form);
      setDigest(value);
      setMessage("Daily alert email template saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the newsletter template.");
    } finally {
      setBusy(false);
    }
  }

  async function sendNow() {
    if (!token) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await adminSendDigest(token);
      setMessage(result.message);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process the digest.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminShell>
      <div className="space-y-5">
        <section className="card-panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-[var(--navy-100)]">Newsletter subscription</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">
                Manage the daily 12:00 PM PKT job-alert email and subscriber count.
              </p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-semibold text-[var(--navy-100)]">{digest?.active_subscriber_count ?? 0}</div>
              <div className="text-xs text-[var(--muted)]">subscribed emails</div>
            </div>
          </div>
          {error && <p className="field-error mt-3">{error}</p>}
          {message && <p className="mt-3 text-sm font-medium text-[var(--success)]">{message}</p>}
        </section>

        <section className="card-panel p-5 space-y-4">
          <form onSubmit={saveTemplate} className="space-y-3">
            <div>
              <label className="field-label" htmlFor="digest-email-subject">Email subject</label>
              <input id="digest-email-subject" className="input" value={form.subject_template} onChange={(event) => setForm({ ...form, subject_template: event.target.value })} required />
            </div>
            <div>
              <label className="field-label" htmlFor="digest-email-body">Predefined email body text</label>
              <textarea id="digest-email-body" className="input min-h-32" value={form.body_template} onChange={(event) => setForm({ ...form, body_template: event.target.value })} required />
            </div>
            <p className="text-xs text-[var(--muted)]">
              Available placeholders: <code>{"{site_title}"}</code>, <code>{"{date}"}</code>, <code>{"{range_start}"}</code>, <code>{"{range_end}"}</code>. Job links, deadlines, and the personal unsubscribe link are inserted automatically.
            </p>
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-primary" type="submit" disabled={busy}>Save email template</button>
              <button className="btn btn-ghost" type="button" disabled={busy} onClick={sendNow}>Process current digest window</button>
            </div>
          </form>
          <p className="text-xs text-[var(--muted)]">
            Last digest: {digest?.last_digest_status || "not run"}{digest?.last_digest_at ? ` · ${new Date(digest.last_digest_at).toLocaleString("en-PK")}` : ""}
          </p>
        </section>
      </div>
    </AdminShell>
  );
}
