"use client";

import { FormEvent, useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import {
  adminResendLatestJobAlert,
  adminSubscriptionSummary,
  adminUpdateDigestTemplate,
} from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { DigestAdminSummary } from "@/lib/types";

const RAILWAY_DELIVERY_SETUP =
  "Railway email delivery is not configured. Set EMAIL_DELIVERY_PROVIDER=resend, RESEND_API_KEY, and EMAIL_FROM_EMAIL on both backend-api and newsletter-retry, then redeploy both services.";

function deliveryFailureMessage(error: string) {
  if (/\bOSError\b/i.test(error)) {
    return "The previous SMTP connection was blocked by the hosting network. Configure Resend HTTPS, then resend the latest alert.";
  }
  return error;
}

export default function NewsletterSubscriptionPage() {
  const { token } = useAdminAuth();
  const [digest, setDigest] = useState<DigestAdminSummary | null>(null);
  const [form, setForm] = useState({ subject_template: "", body_template: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const deliveryReady = digest?.delivery_ready === true;
  const deliveryConfigurationMessage =
    digest?.delivery_configuration_message?.trim() || RAILWAY_DELIVERY_SETUP;
  const displayedDigestStatus =
    digest?.last_digest_status && !deliveryReady
      ? "configuration required"
      : digest?.last_digest_status || "not sent";

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
      setMessage("New-job alert email template saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save the newsletter template.");
    } finally {
      setBusy(false);
    }
  }

  async function resendLatest() {
    if (!token) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await adminResendLatestJobAlert(token);
      setMessage(
        `${result.job_title || "Latest job"}: ${result.message}`
      );
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to resend the latest job alert.");
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
                Manage the automatic email sent whenever a new job is published.
              </p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-semibold text-[var(--navy-100)]">{digest?.active_subscriber_count ?? 0}</div>
              <div className="text-xs text-[var(--muted)]">subscribed emails</div>
            </div>
          </div>
          {error && <p className="field-error mt-3">{error}</p>}
          {message && <p className="mt-3 text-sm font-medium text-[var(--success)]">{message}</p>}
          {digest && !deliveryReady && (
            <p className="mt-3 rounded-xl border border-amber-400/40 bg-amber-400/10 p-3 text-sm text-amber-700 dark:text-amber-300">
              <strong>Email delivery setup required.</strong>{" "}
              {deliveryConfigurationMessage}
            </p>
          )}
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
              Available placeholders: <code>{"{site_title}"}</code>, <code>{"{date}"}</code>, <code>{"{job_title}"}</code>, <code>{"{job_url}"}</code>, <code>{"{deadline}"}</code>, and <code>{"{published_date}"}</code>. The linked job, deadline, and personal unsubscribe link are inserted automatically.
            </p>
            <button className="btn btn-primary" type="submit" disabled={busy}>Save email template</button>
          </form>
          <p className="text-xs text-[var(--muted)]">
            Last job alert: {displayedDigestStatus}
            {digest?.last_digest_job_title ? ` · ${digest.last_digest_job_title}` : ""}
            {digest?.last_digest_at ? ` · ${new Date(digest.last_digest_at).toLocaleString("en-PK")}` : ""}
          </p>
          {digest?.last_digest_status && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--navy-850)] p-4 text-sm">
              <p className="text-[var(--navy-200)]">
                Accepted by email provider: <strong>{digest.last_digest_sent_count}</strong> /{" "}
                {digest.last_digest_recipients_count}; failed:{" "}
                <strong>{digest.last_digest_failed_count}</strong>
              </p>
              {digest.last_digest_error && (
                <p className="mt-2 break-words text-xs text-[var(--danger)]">
                  {deliveryFailureMessage(digest.last_digest_error)}
                </p>
              )}
              <p className="mt-2 text-xs text-[var(--muted)]">
                Provider acceptance cannot guarantee Inbox placement; also check Spam, Promotions,
                and recipient filters.
              </p>
            </div>
          )}
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy || !digest?.active_subscriber_count || !deliveryReady}
            onClick={resendLatest}
          >
            {busy ? "Sending…" : "Resend latest job alert"}
          </button>
        </section>
      </div>
    </AdminShell>
  );
}
