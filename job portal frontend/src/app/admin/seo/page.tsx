"use client";

import { FormEvent, useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import {
  adminSeoAction,
  adminSeoDashboard,
  adminSendDigest,
  adminSubscriptionSummary,
  adminUpdateDigestTemplate,
} from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { DigestAdminSummary, SEODashboard } from "@/lib/types";

export default function AdminSeoPage() {
  const { token } = useAdminAuth();
  const [data, setData] = useState<SEODashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [social, setSocial] = useState({ facebook_url: "", youtube_url: "", x_url: "" });
  const [backlink, setBacklink] = useState({ source_url: "", anchor_text: "" });
  const [busy, setBusy] = useState(false);
  const [digest, setDigest] = useState<DigestAdminSummary | null>(null);
  const [digestForm, setDigestForm] = useState({ subject_template: "", body_template: "" });

  async function reload() {
    if (!token) return;
    const d = await adminSeoDashboard(token);
    setData(d);
    if (d?.social) {
      setSocial({
        facebook_url: d.social.facebook_url || "",
        youtube_url: d.social.youtube_url || "",
        x_url: d.social.x_url || "",
      });
    }
  }

  useEffect(() => {
    if (!token) return;
    reload().catch((e) => setError(e instanceof Error ? e.message : "Failed"));
    adminSubscriptionSummary(token).then((value) => {
      setDigest(value);
      setDigestForm({ subject_template: value.subject_template, body_template: value.body_template });
    }).catch((e) => setError(e instanceof Error ? e.message : "Subscription settings failed"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function saveDigestTemplate(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true); setError(null); setMsg(null);
    try {
      const value = await adminUpdateDigestTemplate(token, digestForm);
      setDigest(value); setMsg("Daily alert email template saved.");
    } catch (err) { setError(err instanceof Error ? err.message : "Save failed"); }
    finally { setBusy(false); }
  }

  async function sendDigestNow() {
    if (!token) return;
    setBusy(true); setError(null); setMsg(null);
    try {
      const value = await adminSendDigest(token);
      setMsg(value.message);
      setDigest(await adminSubscriptionSummary(token));
    } catch (err) { setError(err instanceof Error ? err.message : "Send failed"); }
    finally { setBusy(false); }
  }

  async function run(path: string, method = "POST", body?: unknown) {
    if (!token) return;
    setBusy(true);
    setMsg(null);
    setError(null);
    try {
      const res = await adminSeoAction(token, path, method, body);
      setMsg(res.message || "Done");
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveSocial(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    try {
      await adminSeoAction(token, "/api/admin/seo/social", "PUT", social);
      setMsg("Social media URLs saved.");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function addBacklink(e: FormEvent) {
    e.preventDefault();
    if (!token || !backlink.source_url) return;
    await run("/api/admin/seo/backlinks", "POST", backlink);
    setBacklink({ source_url: "", anchor_text: "" });
  }

  const speed = Number(data?.pagespeed?.score ?? data?.performance?.load_score_pct ?? 0);
  const authority = Number(data?.authority?.score ?? 0);

  return (
    <AdminShell>
      <div className="space-y-5">
        <div className="card-panel p-5">
          <h2 className="text-xl font-semibold text-[var(--navy-100)]">SEO command center</h2>
          <p className="text-sm text-[var(--muted)] mt-1">
            Search Console, sitemaps, page speed, rankings, authority, backlinks & social profiles.
          </p>
          {error && <p className="field-error mt-3">{error}</p>}
          {msg && <p className="text-sm text-[var(--success)] mt-3 font-medium">{msg}</p>}
        </div>

        {data && (
          <>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <Metric label="Total jobs" value={data.total_jobs} />
              <Metric label="Open SEO coverage" value={data.jobs_with_seo} />
              <Metric label="Load speed /100" value={Math.round(speed)} />
              <Metric label="Authority score" value={Math.round(authority)} />
            </div>

            <section className="card-panel p-5 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-[var(--navy-100)]">Daily job alert subscriptions</h3>
                  <p className="mt-1 text-sm text-[var(--muted)]">Scheduled for 12:00 PM PKT. Job links and deadlines are inserted automatically.</p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-semibold text-[var(--navy-100)]">{digest?.active_subscriber_count ?? 0}</div>
                  <div className="text-xs text-[var(--muted)]">active of {digest?.subscriber_count ?? 0} total</div>
                </div>
              </div>
              <form onSubmit={saveDigestTemplate} className="space-y-3">
                <div><label className="field-label" htmlFor="digest-email-subject">Email subject</label><input id="digest-email-subject" className="input" value={digestForm.subject_template} onChange={(e) => setDigestForm({ ...digestForm, subject_template: e.target.value })} required /></div>
                <div><label className="field-label" htmlFor="digest-email-body">Predefined email body text</label><textarea id="digest-email-body" className="input min-h-32" value={digestForm.body_template} onChange={(e) => setDigestForm({ ...digestForm, body_template: e.target.value })} required /></div>
                <p className="text-xs text-[var(--muted)]">Available placeholders: <code>{"{site_title}"}</code>, <code>{"{date}"}</code>, <code>{"{range_start}"}</code>, <code>{"{range_end}"}</code>.</p>
                <div className="flex flex-wrap gap-2">
                  <button className="btn btn-primary" type="submit" disabled={busy}>Save email template</button>
                  <button className="btn btn-ghost" type="button" disabled={busy} onClick={sendDigestNow}>Process current digest window</button>
                </div>
              </form>
              <p className="text-xs text-[var(--muted)]">Last digest: {digest?.last_digest_status || "not run"}{digest?.last_digest_at ? ` · ${new Date(digest.last_digest_at).toLocaleString("en-PK")}` : ""}</p>
            </section>

            {/* GSC */}
            <section className="card-panel p-5 space-y-3">
              <h3 className="font-semibold text-[var(--navy-100)]">Google Search Console</h3>
              <p className="text-sm text-[var(--muted)]">
                {(data.gsc?.message as string) || "Not connected"}
              </p>
              <div className="text-xs text-[var(--navy-300)] space-y-1">
                <p>
                  Site: {(data.gsc?.site_url as string) || "—"} · Last sync:{" "}
                  {(data.gsc?.last_sync as string) || "never"}
                </p>
                <p>
                  Env: <code>GSC_SITE_URL</code> + <code>GOOGLE_APPLICATION_CREDENTIALS</code>{" "}
                  (service account JSON with Search Console access).
                </p>
              </div>
              <button
                type="button"
                className="btn btn-primary"
                disabled={busy}
                onClick={() => run("/api/admin/seo/gsc/sync")}
              >
                Sync Search Console
              </button>
            </section>

            {/* Sitemap + robots */}
            <section className="card-panel p-5 space-y-3">
              <h3 className="font-semibold text-[var(--navy-100)]">Sitemaps & robots.txt</h3>
              <div className="flex flex-wrap gap-3 text-sm">
                <a
                  className="text-[var(--accent)] hover:underline"
                  href={data.sitemap_url || "/sitemap.xml"}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open sitemap.xml
                </a>
                <a
                  className="text-[var(--accent)] hover:underline"
                  href={data.robots_url || "/robots.txt"}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open robots.txt
                </a>
                <a
                  className="text-[var(--accent)] hover:underline"
                  href="/sitemap.xml"
                  target="_blank"
                  rel="noreferrer"
                >
                  Frontend sitemap
                </a>
              </div>
              <pre className="text-xs bg-[var(--navy-850)] border border-[var(--border)] rounded-lg p-3 overflow-x-auto text-[var(--navy-200)]">
                {data.robots_preview || "User-agent: *\nAllow: /"}
              </pre>
            </section>

            {/* Page speed */}
            <section className="card-panel p-5 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-semibold text-[var(--navy-100)]">Website load speed</h3>
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={busy}
                  onClick={() => run("/api/admin/seo/pagespeed")}
                >
                  Re-measure
                </button>
              </div>
              <div className="flex items-end gap-4">
                <div className="text-4xl font-semibold text-[var(--accent)] tabular-nums">
                  {Math.round(speed)}
                  <span className="text-base text-[var(--muted)]">/100</span>
                </div>
                <div className="text-sm text-[var(--muted)]">
                  Source: {String(data.pagespeed?.source || "—")}
                  {data.pagespeed?.ttfb_ms != null && (
                    <> · TTFB {String(data.pagespeed.ttfb_ms)} ms</>
                  )}
                  {data.pagespeed?.note != null && (
                    <div className="mt-1">{String(data.pagespeed.note)}</div>
                  )}
                </div>
              </div>
              <div className="h-2 rounded-full bg-[var(--navy-800)] overflow-hidden">
                <div
                  className="h-full bg-[var(--accent)]"
                  style={{ width: `${Math.min(100, Math.max(0, speed))}%` }}
                />
              </div>
            </section>

            {/* URL ranks */}
            <section className="card-panel p-5 space-y-3">
              <h3 className="font-semibold text-[var(--navy-100)]">
                Job/page Google search page ranks
              </h3>
              <p className="text-xs text-[var(--muted)]">
                From Search Console sync: which URL appears on which Google results page.
              </p>
              {(data.url_ranks || []).length === 0 ? (
                <p className="text-sm text-[var(--muted)]">No ranking data yet — sync GSC.</p>
              ) : (
                <div className="overflow-x-auto -mx-1 px-1">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-[var(--muted)]">
                        <th className="py-2 pr-3">URL</th>
                        <th className="py-2 pr-3">Type</th>
                        <th className="py-2 pr-3">Best pos</th>
                        <th className="py-2">Google page</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data.url_ranks || []).map((r, i) => (
                        <tr key={i} className="border-t border-[var(--border)]">
                          <td className="py-2 pr-3 max-w-xs truncate text-[var(--navy-100)]">
                            {String(r.url)}
                          </td>
                          <td className="py-2 pr-3">{String(r.entity_type || "—")}</td>
                          <td className="py-2 pr-3">{Number(r.best_position).toFixed(1)}</td>
                          <td className="py-2">Page {String(r.search_page)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Keyword ranks */}
            <section className="card-panel p-5 space-y-3">
              <h3 className="font-semibold text-[var(--navy-100)]">Keyword rankings</h3>
              {(data.keyword_ranks || []).length === 0 ? (
                <p className="text-sm text-[var(--muted)]">No keywords yet — sync GSC.</p>
              ) : (
                <div className="overflow-x-auto -mx-1 px-1">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-[var(--muted)]">
                        <th className="py-2 pr-3">Keyword</th>
                        <th className="py-2 pr-3">URL</th>
                        <th className="py-2 pr-3">Pos</th>
                        <th className="py-2 pr-3">Page</th>
                        <th className="py-2">Clicks</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data.keyword_ranks || []).slice(0, 40).map((r, i) => (
                        <tr key={i} className="border-t border-[var(--border)]">
                          <td className="py-2 pr-3 text-[var(--navy-100)]">{String(r.keyword)}</td>
                          <td className="py-2 pr-3 max-w-[200px] truncate">{String(r.url)}</td>
                          <td className="py-2 pr-3">{Number(r.position).toFixed(1)}</td>
                          <td className="py-2 pr-3">{String(r.search_page)}</td>
                          <td className="py-2">{String(r.clicks)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Authority */}
            <section className="card-panel p-5 space-y-2">
              <h3 className="font-semibold text-[var(--navy-100)]">Website authority score</h3>
              <div className="text-3xl font-semibold text-[var(--navy-100)]">
                {Math.round(authority)}
                <span className="text-sm text-[var(--muted)]"> / 100</span>
              </div>
              <p className="text-xs text-[var(--muted)]">
                Composite of on-page SEO avg, SEO coverage, and backlink count (
                {String(data.authority?.method || "composite")}).
              </p>
            </section>

            {/* Backlinks */}
            <section className="card-panel p-5 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="font-semibold text-[var(--navy-100)]">Backlinks</h3>
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={busy}
                  onClick={() => run("/api/admin/seo/backlinks/discover")}
                >
                  Discover from social
                </button>
              </div>
              <form onSubmit={addBacklink} className="grid sm:grid-cols-3 gap-2">
                <input
                  className="input"
                  placeholder="Source URL (linking site)"
                  value={backlink.source_url}
                  onChange={(e) => setBacklink({ ...backlink, source_url: e.target.value })}
                  required
                />
                <input
                  className="input"
                  placeholder="Anchor text"
                  value={backlink.anchor_text}
                  onChange={(e) => setBacklink({ ...backlink, anchor_text: e.target.value })}
                />
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  Add backlink
                </button>
              </form>
              {(data.backlinks || []).length === 0 ? (
                <p className="text-sm text-[var(--muted)]">No backlinks recorded yet.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {(data.backlinks || []).map((b) => (
                    <li
                      key={String(b.id)}
                      className="border border-[var(--border)] rounded-lg p-3 bg-[var(--navy-850)]"
                    >
                      <a
                        href={String(b.source_url)}
                        className="text-[var(--accent)] hover:underline break-all"
                        target="_blank"
                        rel="noreferrer"
                      >
                        {String(b.source_url)}
                      </a>
                      <div className="text-xs text-[var(--muted)] mt-1">
                        {String(b.domain || "")} · {String(b.anchor_text || "—")}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* Social */}
            <section className="card-panel p-5 space-y-3">
              <h3 className="font-semibold text-[var(--navy-100)]">Social media (footer icons)</h3>
              <form onSubmit={saveSocial} className="space-y-3">
                <div>
                  <label className="field-label">Facebook URL</label>
                  <input
                    className="input"
                    value={social.facebook_url}
                    onChange={(e) => setSocial({ ...social, facebook_url: e.target.value })}
                    placeholder="https://facebook.com/..."
                  />
                </div>
                <div>
                  <label className="field-label">YouTube URL</label>
                  <input
                    className="input"
                    value={social.youtube_url}
                    onChange={(e) => setSocial({ ...social, youtube_url: e.target.value })}
                    placeholder="https://youtube.com/..."
                  />
                </div>
                <div>
                  <label className="field-label">X (Twitter) URL</label>
                  <input
                    className="input"
                    value={social.x_url}
                    onChange={(e) => setSocial({ ...social, x_url: e.target.value })}
                    placeholder="https://x.com/..."
                  />
                </div>
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  Save social URLs
                </button>
              </form>
            </section>

            {data.issues?.length > 0 && (
              <div className="card-panel p-5">
                <h3 className="font-semibold text-[var(--navy-100)] mb-3">On-page issues</h3>
                <ul className="list-disc list-inside space-y-1 text-sm text-[var(--danger)]">
                  {data.issues.map((issue, i) => (
                    <li key={i}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </AdminShell>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-card">
      <div className="text-2xl font-semibold text-[var(--navy-100)]">{value}</div>
      <div className="text-xs uppercase tracking-wider text-[var(--muted)] mt-1">{label}</div>
    </div>
  );
}
